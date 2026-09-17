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
    TerminalWidget,
    compute_grid_size,
    resolve_color,
)


def test_compute_grid_size_basic():
    assert compute_grid_size(800, 600, 10, 20) == (80, 30)


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

    # Drain the deferred singleShot(0, ...) correction this test's start()
    # scheduled, so it doesn't fire during a later test sharing this
    # session-scoped qapp's event queue.
    qapp.processEvents()

    widget._repaint_timer.stop()
    widget._blink_timer.stop()


def test_start_defers_size_correction_to_widgets_real_size(qapp, tmp_path, monkeypatch):
    # After the event loop gets a chance to run (e.g. once the window is
    # shown and layout has settled), the terminal should be corrected to
    # match the widget's real, current size -- whether this is the initial
    # launch or a Restart of an already-visible, already-correctly-sized pane.
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
    assert (widget.screen.columns, widget.screen.lines) == (80, 24)

    qapp.processEvents()  # let the singleShot(0, ...) correction run

    cell_w, cell_h = widget._cell_size()
    expected = compute_grid_size(801, 601, cell_w, cell_h)
    assert resize_calls == [expected]
    assert (widget.screen.columns, widget.screen.lines) == expected

    widget._repaint_timer.stop()
    widget._blink_timer.stop()


def test_sync_size_to_widget_survives_widget_deleted_before_it_runs(qapp, tmp_path, monkeypatch):
    # Regression test: MainWindow.build_panes() tears panes down via
    # deleteLater() whenever the user changes the SHELL COUNT combo. If that
    # teardown -- or any other deletion of the widget's underlying C++
    # object -- happens after start() schedules the deferred
    # QTimer.singleShot(0, self._sync_size_to_widget) correction but before
    # that callback actually runs, the callback must not blow up. Without a
    # validity guard, touching self.width()/self.screen on an
    # already-deleted widget raises RuntimeError -- but PySide6 routes an
    # exception raised inside a slot/callback to sys.excepthook rather than
    # letting it propagate out of processEvents(), so a bare
    # "processEvents() doesn't raise" assertion would pass even with the bug
    # present. Install a temporary excepthook to actually observe whether
    # the callback raised.
    monkeypatch.setattr(PtyBackend, "spawn", lambda self, cwd, columns=80, lines=24: None)
    monkeypatch.setattr(PtyBackend, "resize", lambda self, columns, lines: None)

    widget = TerminalWidget()
    widget.start(str(tmp_path))  # schedules the deferred singleShot(0, ...)

    widget._repaint_timer.stop()
    widget._blink_timer.stop()

    assert shiboken6.isValid(widget)
    shiboken6.delete(widget)  # simulate teardown completing before the callback fires
    assert not shiboken6.isValid(widget)

    uncaught = []
    original_excepthook = sys.excepthook
    sys.excepthook = lambda *exc_info: uncaught.append(exc_info)
    try:
        qapp.processEvents()  # runs the pending _sync_size_to_widget callback
    finally:
        sys.excepthook = original_excepthook

    assert uncaught == []
