import sys

import shiboken6
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

from pty_backend import PtyBackend
from terminal_screen import TerminalScreen
from terminal_widget import (
    ANSI_BRIGHT_COLORS,
    ANSI_COLORS,
    DEFAULT_FG,
    _RESIZE_DEBOUNCE_MS,
    TerminalWidget,
    compute_grid_size,
    compute_visible_window,
    resolve_color,
)


def test_compute_grid_size_basic():
    assert compute_grid_size(800, 600, 10, 20) == (80, 30)


def test_compute_visible_window_buffer_matches_visible_size():
    # No padding has ever been needed -- the whole buffer is the window.
    assert compute_visible_window(
        buffer_lines=24, buffer_columns=80, visible_rows=24, visible_cols=80, cursor_row=5,
    ) == (0, 24, 80)


def test_compute_visible_window_buffer_taller_but_content_not_yet_scrolled():
    # Buffer grew past the widget's real (smaller) size, but nothing has
    # actually filled it yet (cursor is still near the top) -- the window
    # must start at the top, not the bottom, since that's where the
    # (only) real content actually is. Rendering a fixed "bottom of
    # buffer" slice here would show nothing: pyte's own auto-scroll only
    # triggers once *its* line count (24) is filled, not the widget's
    # smaller visible size (10), so content sitting at rows 0-5 would be
    # completely missed by a naive bottom-anchored window.
    assert compute_visible_window(
        buffer_lines=24, buffer_columns=80, visible_rows=10, visible_cols=80, cursor_row=5,
    ) == (0, 10, 80)


def test_compute_visible_window_buffer_taller_and_content_has_scrolled():
    # Once real usage has filled the pane enough that pyte's own scrolling
    # kicked in (cursor sits at the buffer's last row), the window matches
    # the bottom of the buffer -- the same result a naive fixed-bottom
    # window would give, but derived correctly via the cursor.
    assert compute_visible_window(
        buffer_lines=24, buffer_columns=80, visible_rows=10, visible_cols=80, cursor_row=23,
    ) == (14, 10, 80)


def test_compute_visible_window_buffer_wider_than_visible_shows_left():
    assert compute_visible_window(
        buffer_lines=24, buffer_columns=80, visible_rows=24, visible_cols=40, cursor_row=5,
    ) == (0, 24, 40)


def test_compute_grid_size_clamps_to_at_least_one():
    assert compute_grid_size(5, 5, 10, 20) == (1, 1)


def test_resolve_color_default_fg():
    assert resolve_color("default", bold=False, is_fg=True) == QColor(DEFAULT_FG)


def test_resolve_color_named():
    assert resolve_color("red", bold=False, is_fg=True) == QColor(ANSI_COLORS["red"])


def test_resolve_color_bold_uses_bright_variant():
    assert resolve_color("red", bold=True, is_fg=True) == QColor(ANSI_BRIGHT_COLORS["red"])


def test_resolve_color_hex_passthrough():
    assert resolve_color("#112233", bold=False, is_fg=True) == QColor("#112233")


def test_resolve_color_bright_name_from_aixterm_code():
    # pyte emits "brightred" directly for aixterm SGR codes (90-97/100-107),
    # with bold=False -- a separate convention from bold=True + fg="red".
    assert resolve_color("brightred", bold=False, is_fg=True) == QColor(ANSI_BRIGHT_COLORS["red"])


def test_widget_renders_fed_screen_without_error(qapp):
    widget = TerminalWidget()
    widget.resize(400, 300)
    widget.screen = TerminalScreen(columns=40, lines=15)
    widget.screen.feed("hello")

    pixmap = widget.grab()

    assert pixmap.width() == 400
    assert pixmap.height() == 300


def test_tab_and_shift_tab_reach_key_press_event_instead_of_stealing_focus(qapp):
    # Regression test: by default, Qt intercepts Tab/Shift+Tab for keyboard
    # focus traversal before they ever reach keyPressEvent, unless a widget
    # overrides focusNextPrevChild() to opt out. Without that override, Tab
    # never reaches translate_key_event and PowerShell's tab-completion is
    # silently dead -- pressing Tab just moves focus to the next widget (e.g.
    # another pane, or a Browse/Restart button) instead of sending a byte to
    # the shell. Verified with a real sibling focusable widget and real Qt
    # event dispatch (QTest.keyClick), not just the pure translate_key_event
    # function, since that's exactly the layer the original bug lived in.
    received_keys = []

    class ProbeTerminalWidget(TerminalWidget):
        def keyPressEvent(self, event):
            received_keys.append(event.key())
            super().keyPressEvent(event)

    container = QWidget()
    layout = QVBoxLayout(container)
    term = ProbeTerminalWidget()
    other = QPushButton("other focusable widget")
    layout.addWidget(term)
    layout.addWidget(other)
    container.show()

    term.setFocus()
    qapp.processEvents()
    QTest.keyClick(term, Qt.Key_Tab)
    qapp.processEvents()

    assert qapp.focusWidget() is term
    assert received_keys == [Qt.Key_Tab]

    received_keys.clear()
    term.setFocus()
    qapp.processEvents()
    QTest.keyClick(term, Qt.Key_Backtab)
    qapp.processEvents()

    assert qapp.focusWidget() is term
    assert received_keys == [Qt.Key_Backtab]

    term._repaint_timer.stop()
    term._blink_timer.stop()


def test_start_spawns_with_safe_default_size_not_widgets_unshown_size(qapp, tmp_path, monkeypatch):
    # Regression test: before layout/show, an un-shown widget's width()/height()
    # report a tiny placeholder size (commonly ~100x30px in the real app, where
    # panes are built before the main window is shown). Spawning the shell at
    # the grid size derived from that placeholder produces a degenerate (e.g.
    # 1-row) buffer that irrecoverably mangles the initial prompt, since
    # pyte's resize() only pads/clips going forward -- it never reflows
    # already-corrupted content. `start()` must always spawn at the safe
    # conventional default (80x24) regardless of the widget's current size.
    spawn_calls = []
    monkeypatch.setattr(
        PtyBackend, "spawn",
        lambda self, cwd, columns=80, lines=24: spawn_calls.append((columns, lines)),
    )

    widget = TerminalWidget()
    widget.resize(96, 29)  # mimics the ~100x30px pre-layout placeholder size

    widget.start(str(tmp_path))

    assert spawn_calls == [(80, 24)]
    assert widget.screen.columns == 80
    assert widget.screen.lines == 24

    # Drain the debounced size-correction this test's start() scheduled, so
    # it doesn't fire during a later test sharing this session-scoped qapp's
    # event queue.
    QTest.qWait(_RESIZE_DEBOUNCE_MS + 100)

    widget._repaint_timer.stop()
    widget._blink_timer.stop()


def test_start_defers_size_correction_to_widgets_real_size(qapp, tmp_path, monkeypatch):
    # After the event loop gets a chance to run (e.g. once the window is
    # shown and layout has settled), the terminal's real, reported size
    # (_visible_cols/_visible_rows, and what's told to the backend/shell)
    # should be corrected to match the widget's actual current geometry --
    # whether this is the initial launch or a Restart of an already-visible,
    # already-correctly-sized pane.
    spawn_calls = []
    resize_calls = []
    monkeypatch.setattr(
        PtyBackend, "spawn",
        lambda self, cwd, columns=80, lines=24: spawn_calls.append((columns, lines)),
    )
    monkeypatch.setattr(
        PtyBackend, "resize",
        lambda self, columns, lines: resize_calls.append((columns, lines)),
    )

    widget = TerminalWidget()
    widget.resize(801, 601)  # a realistic, already-laid-out size

    widget.start(str(tmp_path))

    # Immediately after start() returns, the safe default is still in effect --
    # the correction has only been scheduled, not yet applied.
    assert spawn_calls == [(80, 24)]
    assert resize_calls == []
    assert (widget._visible_cols, widget._visible_rows) == (80, 24)

    QTest.qWait(_RESIZE_DEBOUNCE_MS + 100)  # let the debounced correction run

    cell_w, cell_h = widget._cell_size()
    expected = compute_grid_size(801, 601, cell_w, cell_h)
    assert resize_calls == [expected]
    # The real/reported size always matches the widget's actual geometry...
    assert (widget._visible_cols, widget._visible_rows) == expected
    # ...but pyte's own buffer only ever grows, never shrinks, in each
    # dimension independently (columns here happens to already be >=
    # expected, so it's untouched; lines grew to match).
    assert widget.screen.columns == max(80, expected[0])
    assert widget.screen.lines == max(24, expected[1])

    widget._repaint_timer.stop()
    widget._blink_timer.stop()


def test_sync_size_to_widget_survives_widget_deleted_before_it_runs(qapp, tmp_path, monkeypatch):
    # Regression test: MainWindow.build_panes() tears panes down via
    # deleteLater() whenever the user changes the SHELL COUNT combo. If that
    # teardown -- or any other deletion of the widget's underlying C++
    # object -- happens after start() schedules the debounced
    # _sync_size_to_widget correction but before that callback actually
    # runs, the callback must not blow up. Without a validity guard,
    # touching self.width()/self.screen on an already-deleted widget raises
    # RuntimeError -- but PySide6 routes an exception raised inside a
    # slot/callback to sys.excepthook rather than letting it propagate out
    # of processEvents(), so a bare "processEvents() doesn't raise"
    # assertion would pass even with the bug present. Install a temporary
    # excepthook to actually observe whether the callback raised.
    monkeypatch.setattr(PtyBackend, "spawn", lambda self, cwd, columns=80, lines=24: None)
    monkeypatch.setattr(PtyBackend, "resize", lambda self, columns, lines: None)

    widget = TerminalWidget()
    widget.start(str(tmp_path))  # schedules the debounced correction

    widget._repaint_timer.stop()
    widget._blink_timer.stop()

    assert shiboken6.isValid(widget)
    shiboken6.delete(widget)  # simulate teardown completing before the callback fires
    assert not shiboken6.isValid(widget)

    uncaught = []
    original_excepthook = sys.excepthook
    sys.excepthook = lambda *exc_info: uncaught.append(exc_info)
    try:
        QTest.qWait(_RESIZE_DEBOUNCE_MS + 100)  # runs the pending _sync_size_to_widget callback
    finally:
        sys.excepthook = original_excepthook

    assert uncaught == []


def test_rapid_resize_churn_does_not_wipe_already_rendered_content(qapp, tmp_path, monkeypatch):
    # Regression test: building a multi-pane layout (e.g. switching SHELL
    # COUNT to "2V") fires several real resizeEvents in quick succession as
    # Qt's splitters settle -- including shrinks partway through, even when
    # the final settled size is no smaller than an earlier one. Applying
    # each resize immediately would tell pyte to drop lines from the *top*
    # of its buffer on every shrink (pyte's own, correct behavior for real
    # scrollback) -- but a freshly spawned shell's only output so far (its
    # first prompt) sits at the very top of an otherwise-empty buffer, so an
    # immediately-applied mid-settle shrink silently destroys it before the
    # user ever sees it. Confirmed independently: feeding "PS C:/Users> "
    # into a real TerminalScreen and then calling .resize() to fewer lines
    # wipes row 0 outright. This test drives real resizeEvents (via
    # widget.resize()), not just compute_grid_size in isolation, since
    # that's the layer the bug lived in.
    monkeypatch.setattr(PtyBackend, "spawn", lambda self, cwd, columns=80, lines=24: None)
    monkeypatch.setattr(PtyBackend, "resize", lambda self, columns, lines: None)

    # A never-shown top-level widget doesn't get real QResizeEvents at all
    # under Qt's offscreen test platform -- show() it first so widget.resize()
    # calls below genuinely drive resizeEvent()/the debounce restart, the
    # same as a real, visible pane.
    widget = TerminalWidget()
    widget.show()
    qapp.processEvents()
    widget.resize(800, 600)
    qapp.processEvents()
    widget.start(str(tmp_path))

    # Simulate real shell output landing before layout has settled -- e.g.
    # a very fast-starting shell, or a slow layout pass.
    widget._on_output("PS C:/Users> ")
    assert "PS C:/Users>" in widget.screen._screen.display[0]

    # Simulate the kind of resize churn a splitter rebuild produces: several
    # quick, real resizes -- some shrinks, ending back at a size that easily
    # fits the one line already written.
    widget.resize(800, 300)
    qapp.processEvents()
    widget.resize(800, 150)
    qapp.processEvents()
    widget.resize(800, 300)
    qapp.processEvents()

    # Nothing should have applied yet -- still within the debounce window.
    assert "PS C:/Users>" in widget.screen._screen.display[0]

    QTest.qWait(_RESIZE_DEBOUNCE_MS + 100)  # let geometry "settle"

    assert "PS C:/Users>" in widget.screen._screen.display[0]

    widget._repaint_timer.stop()
    widget._blink_timer.stop()


def test_new_output_stays_visible_once_it_exceeds_the_shrunk_row_count(qapp, tmp_path, monkeypatch):
    # Regression test for the risk a naive "never shrink" fix would create:
    # if pyte's buffer only ever grows but rendering always showed the *top*
    # of it, new output written past a small pane's real row count would
    # never appear -- the visible area would look frozen on whatever content
    # happened to occupy the first few rows. Rendering the *bottom*
    # _visible_rows of the buffer (compute_visible_window) instead means new
    # output -- which pyte always appends at increasing row numbers -- stays
    # visible no matter how much the buffer has grown beyond the pane's
    # current real size.
    monkeypatch.setattr(PtyBackend, "spawn", lambda self, cwd, columns=80, lines=24: None)
    monkeypatch.setattr(PtyBackend, "resize", lambda self, columns, lines: None)

    # A never-shown top-level widget doesn't get real QResizeEvents at all
    # under Qt's offscreen test platform -- show() it first so the resizes
    # below genuinely drive resizeEvent()/the debounce restart.
    widget = TerminalWidget()
    widget.show()
    qapp.processEvents()
    widget.resize(800, 600)
    qapp.processEvents()
    widget.start(str(tmp_path))
    QTest.qWait(_RESIZE_DEBOUNCE_MS + 100)

    # Shrink the pane to a small real size (e.g. after splitting into
    # several panes) -- pyte's buffer stays at its prior (taller) size.
    widget.resize(800, 150)
    QTest.qWait(_RESIZE_DEBOUNCE_MS + 100)
    small_visible_rows = widget._visible_rows
    assert small_visible_rows < widget.screen.lines  # buffer is padded taller than visible

    # Write more lines than fit in the small visible area.
    line_count = small_visible_rows + 5
    for i in range(line_count):
        widget._on_output(f"line {i}\r\n")
    last_line = f"line {line_count - 1}"

    top_row, rows_to_render, cols_to_render = compute_visible_window(
        widget.screen.lines, widget.screen.columns, widget._visible_rows, widget._visible_cols,
        cursor_row=widget.screen.cursor.y,
    )
    rendered_rows = [
        "".join(widget.screen.get_cell(x, y).data for x in range(cols_to_render))
        for y in range(top_row, top_row + rows_to_render)
    ]

    # The most recently written line must be inside the rendered window --
    # not scrolled off past the (invisible) bottom of a "frozen" top view.
    assert any(last_line in row for row in rendered_rows)

    widget._repaint_timer.stop()
    widget._blink_timer.stop()
