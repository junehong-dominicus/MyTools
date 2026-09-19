import shiboken6
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QGuiApplication, QPainter
from PySide6.QtWidgets import QWidget

from input_translator import translate_key_event
from pty_backend import PtyBackend
from terminal_screen import TerminalScreen

ANSI_COLORS = {
    "black": "#000000", "red": "#cd3131", "green": "#0dbc79",
    "brown": "#e5e510", "blue": "#2472c8",
    "magenta": "#bc3fbc", "cyan": "#11a8cd", "white": "#e5e5e5",
}

ANSI_BRIGHT_COLORS = {
    "black": "#666666", "red": "#f14c4c", "green": "#23d18b",
    "brown": "#f5f543", "yellow": "#f5f543", "blue": "#3b8eea",
    "magenta": "#d670d6", "cyan": "#29b8db", "white": "#e5e5e5",
}

DEFAULT_FG = "#d4d4d4"
DEFAULT_BG = "#1e1e1e"
# Translucent overlay (not a flat fill) so a selected cell's own fg/bg still
# show through underneath -- same technique already used for the cursor
# below, just a different tint (the app's accent blue) so the two are never
# confused for one another.
SELECTION_OVERLAY = QColor(52, 152, 219, 90)

# How long to wait for widget geometry to stop changing before actually
# resizing the terminal. Building a multi-pane layout (e.g. switching SHELL
# COUNT, or the initial window show) fires several real resizeEvents in quick
# succession as Qt's splitters settle. Debouncing collapses that churn into
# one final size, rather than reacting to each transient intermediate size.
_RESIZE_DEBOUNCE_MS = 150

# How many typed command lines to remember per pane (see keyPressEvent).
# Also duplicated as settings.MAX_HISTORY_ENTRIES for capping on load --
# settings.py has no Qt/pyte dependency and must stay that way.
MAX_HISTORY_ENTRIES = 200


def compute_grid_size(widget_width: int, widget_height: int, cell_width: int, cell_height: int) -> tuple[int, int]:
    cols = max(1, widget_width // cell_width)
    rows = max(1, widget_height // cell_height)
    return cols, rows


def compute_visible_window(buffer_lines: int, buffer_columns: int, visible_rows: int, visible_cols: int, cursor_row: int) -> tuple[int, int, int]:
    """Return (top_row, rows_to_render, cols_to_render): the window of a
    pyte buffer -- which only ever grows, see
    TerminalWidget._sync_size_to_widget -- that corresponds to what the
    widget can currently actually show.

    The row window ends at the *cursor's* current row, not simply the
    bottom of the buffer: pyte's own auto-scroll only triggers once its own
    (possibly much taller, padded) line count is filled, not the widget's
    smaller current visible size, so new output can sit well above the
    buffer's bottom for a long time (e.g. right after a shrink, before the
    pane has been used enough to fill even its old, larger size). Anchoring
    on the cursor keeps whatever was most recently written in view either
    way, and naturally matches "bottom of buffer" once pyte's own
    scrolling *has* kicked in (cursor sits at buffer_lines - 1 then).

    Columns don't need the same treatment: unlike rows, pyte has no
    left/right auto-scroll -- a line either wraps into a new row or is
    truncated -- so content always starts at column 0."""
    rows_to_render = min(buffer_lines, visible_rows)
    cols_to_render = min(buffer_columns, visible_cols)
    max_top_row = buffer_lines - rows_to_render
    top_row = max(0, min(cursor_row - rows_to_render + 1, max_top_row))
    return top_row, rows_to_render, cols_to_render


def resolve_color(name, bold: bool, is_fg: bool) -> QColor:
    if name in (None, "default"):
        return QColor(DEFAULT_FG if is_fg else DEFAULT_BG)
    if isinstance(name, str) and name.startswith("#"):
        return QColor(name)
    if isinstance(name, str) and name.startswith("bright"):
        # pyte's aixterm SGR codes (90-97 fg / 100-107 bg) emit "bright<color>"
        # names directly, independent of the bold flag used by the separate
        # bold+base-name convention (e.g. bold=True, fg="red") handled below.
        base_name = name[len("bright"):]
        if base_name in ANSI_BRIGHT_COLORS:
            return QColor(ANSI_BRIGHT_COLORS[base_name])
    if isinstance(name, str) and name.isdigit():
        return QColor(DEFAULT_FG if is_fg else DEFAULT_BG)  # 256-color: out of scope, fall back

    palette = ANSI_BRIGHT_COLORS if (bold and is_fg) else ANSI_COLORS
    hexval = palette.get(name)
    return QColor(hexval if hexval else (DEFAULT_FG if is_fg else DEFAULT_BG))


class TerminalWidget(QWidget):
    exited = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.backend = PtyBackend(self)
        self.screen: TerminalScreen | None = None
        # The pty's/shell's real, current column/row count -- distinct from
        # self.screen.columns/lines, which only ever grows (see
        # _sync_size_to_widget). Used to render just the bottom-left window
        # of the (possibly taller/wider) pyte buffer that corresponds to
        # what the widget can actually show right now.
        self._visible_cols = 80
        self._visible_rows = 24
        self._history: list[str] = []
        self._font = QFont("Menlo", 10)
        self._metrics = QFontMetrics(self._font)

        self.backend.output_received.connect(self._on_output)
        self.backend.exited.connect(self._on_exited)

        self._dirty = False
        self._repaint_timer = QTimer(self)
        self._repaint_timer.setInterval(33)
        self._repaint_timer.timeout.connect(self._flush_repaint)

        self._cursor_visible = True
        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(500)
        self._blink_timer.timeout.connect(self._toggle_cursor)
        self._blink_timer.start()

        self._resize_debounce_timer = QTimer(self)
        self._resize_debounce_timer.setSingleShot(True)
        self._resize_debounce_timer.setInterval(_RESIZE_DEBOUNCE_MS)
        self._resize_debounce_timer.timeout.connect(self._sync_size_to_widget)

        # Mouse drag-to-select. Both are (col, row) in *buffer* coordinates
        # (see compute_visible_window -- not necessarily the same as the
        # widget's currently-visible row/col, since the buffer only ever
        # grows). None means no selection has been started yet; start ==
        # end means a plain click with no drag, which paints/copies as
        # empty (see _normalized_selection).
        self._selection_start: tuple[int, int] | None = None
        self._selection_end: tuple[int, int] | None = None
        self._selecting = False

        self.setFocusPolicy(Qt.StrongFocus)

    def _cell_size(self) -> tuple[int, int]:
        return self._metrics.horizontalAdvance("W"), self._metrics.height()

    def start(self, cwd: str) -> None:
        # Spawn with the conventional terminal default size — the widget may
        # not yet be shown/laid out at this point (e.g. panes are started
        # before the main window is shown), so self.width()/height() can't
        # be trusted yet.
        cols, rows = 80, 24
        self._visible_cols, self._visible_rows = cols, rows
        self.screen = TerminalScreen(columns=cols, lines=rows)
        self.backend.spawn(cwd, columns=cols, lines=rows)
        self._repaint_timer.start()
        # Correct the size to the widget's real, current geometry once
        # layout has settled — whether this is the initial launch or a
        # Restart of an already-visible pane.
        self._resize_debounce_timer.start()

    def _sync_size_to_widget(self) -> None:
        # Fires once geometry has been quiet for _RESIZE_DEBOUNCE_MS (see
        # start()/resizeEvent(), which (re)start the debounce timer rather
        # than applying a resize immediately). The widget (and its
        # underlying C++ object) may already be gone by the time this
        # deferred callback runs -- e.g. the user changes the SHELL COUNT
        # combo and MainWindow.build_panes() tears down this pane's widgets
        # via deleteLater() before the timer fires. Touching
        # self.width()/self.screen on a deleted widget raises RuntimeError
        # from inside the Qt event loop, so bail out early if that's
        # happened.
        if not shiboken6.isValid(self) or self.screen is None:
            return
        self._apply_size_from_geometry()

    def _apply_size_from_geometry(self) -> None:
        cell_w, cell_h = self._cell_size()
        cols, rows = compute_grid_size(self.width(), self.height(), cell_w, cell_h)
        self._visible_cols, self._visible_rows = cols, rows

        # Never shrink pyte's own buffer: pyte's Screen.resize() drops rows
        # from the *top* (and crops columns from the *right*) when shrinking
        # -- correct behavior for trimming real scrollback, but a freshly
        # spawned shell's only output so far (its first prompt) sits at the
        # very top of an otherwise-empty buffer, so shrinking to the pane's
        # real (often smaller, once split across multiple panes) size would
        # wipe it out. Only ever grow the pyte-side buffer; paintEvent then
        # renders just the bottom-left _visible_rows x _visible_cols window
        # of it, which is always where the shell's *current* output is,
        # since new content is written at increasing row numbers as before.
        buffer_cols = max(self.screen.columns, cols)
        buffer_rows = max(self.screen.lines, rows)
        self.screen.resize(columns=buffer_cols, lines=buffer_rows)

        # The real pty/shell must still be told its actual, current size --
        # for correct wrapping, progress bars, $Host.UI.RawUI.WindowSize,
        # tab-completion menu placement, etc.
        self.backend.resize(cols, rows)

    def set_font_size(self, size: int) -> None:
        # Changing the font changes cell metrics, so the same pixel area
        # now fits a different number of columns/rows -- recompute and
        # apply immediately (not debounced: this is a single deliberate
        # user action, not layout churn from a splitter rebuild).
        self._font = QFont("Menlo", size)
        self._metrics = QFontMetrics(self._font)
        if self.screen is not None:
            self._apply_size_from_geometry()
        self.update()

    def _cell_at(self, pos) -> tuple[int, int] | None:
        """Map a widget-local pixel position to (col, row) in *buffer*
        coordinates (see compute_visible_window), clamped to whatever is
        currently rendered. None if there's nothing to select yet."""
        if self.screen is None:
            return None
        cell_w, cell_h = self._cell_size()
        top_row, rows_to_render, visible_cols = compute_visible_window(
            self.screen.lines, self.screen.columns, self._visible_rows, self._visible_cols,
            cursor_row=self.screen.cursor.y,
        )
        col = max(0, min(visible_cols - 1, int(pos.x() // cell_w)))
        row = top_row + max(0, min(rows_to_render - 1, int(pos.y() // cell_h)))
        return col, row

    def _normalized_selection(self) -> tuple[tuple[int, int], tuple[int, int]] | None:
        """(start, end) in reading order (top-to-bottom, left-to-right), or
        None if nothing is actually selected -- either no drag has happened
        yet, or start == end (a plain click, not a drag)."""
        start, end = self._selection_start, self._selection_end
        if start is None or end is None or start == end:
            return None
        # Compare (row, col), not (col, row): a selection spanning rows
        # must order by row first regardless of which column either point
        # landed on.
        return (start, end) if (start[1], start[0]) <= (end[1], end[0]) else (end, start)

    def _cell_is_selected(self, x: int, y: int, selection) -> bool:
        (sx, sy), (ex, ey) = selection
        if y < sy or y > ey:
            return False
        if sy == ey:
            return sx <= x <= ex
        if y == sy:
            return x >= sx
        if y == ey:
            return x <= ex
        return True  # a fully-enclosed row in the middle of a multi-row selection

    def selected_text(self) -> str:
        selection = self._normalized_selection()
        if selection is None or self.screen is None:
            return ""
        (sx, sy), (ex, ey) = selection
        lines = []
        for y in range(sy, ey + 1):
            col_start = sx if y == sy else 0
            col_end = ex if y == ey else self.screen.columns - 1
            line = "".join(self.screen.get_cell(x, y).data for x in range(col_start, col_end + 1))
            lines.append(line.rstrip())
        return "\n".join(lines)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            cell = self._cell_at(event.position())
            # Both ends start at the same cell -- a plain click with no
            # drag stays a "no selection" (see _normalized_selection), and
            # dragging from here grows a real one.
            self._selection_start = cell
            self._selection_end = cell
            self._selecting = cell is not None
            self.update()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._selecting:
            cell = self._cell_at(event.position())
            if cell is not None:
                self._selection_end = cell
                self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.LeftButton:
            self._selecting = False
        super().mouseReleaseEvent(event)

    def get_history(self) -> list[str]:
        return list(self._history)

    def load_history(self, entries: list[str]) -> None:
        self._history = list(entries)[-MAX_HISTORY_ENTRIES:]

    def _on_output(self, text: str) -> None:
        if self.screen:
            self.screen.feed(text)
            self._dirty = True

    def _flush_repaint(self) -> None:
        if self._dirty:
            self._dirty = False
            self.update()

    def _toggle_cursor(self) -> None:
        self._cursor_visible = not self._cursor_visible
        self.update()

    def _on_exited(self, code: int) -> None:
        self._repaint_timer.stop()
        self._blink_timer.stop()
        self.exited.emit(code)

    def resizeEvent(self, event) -> None:
        # Don't apply the resize immediately: a multi-pane layout rebuild
        # (e.g. changing SHELL COUNT) fires several real resizeEvents in
        # quick succession as Qt's splitters settle, and a shrink applied
        # mid-settle can wipe already-rendered content (see
        # _RESIZE_DEBOUNCE_MS). Restarting the debounce timer here means
        # only the final, settled size actually gets applied.
        if self.screen:
            self._resize_debounce_timer.start()
        super().resizeEvent(event)

    def keyPressEvent(self, event) -> None:
        # Cmd+V. Checked explicitly (Qt.MetaModifier -- Cmd is reported that
        # way, see main.py's AA_MacDontSwapCtrlAndMeta) rather than via
        # event.matches(QKeySequence.Paste): the latter resolves through
        # QPlatformTheme's per-OS standard-key table, which under the
        # "offscreen" QPA platform (used for headless tests) doesn't know
        # it's "supposed to be macOS" and answers Ctrl+V instead -- an
        # explicit check matches this app's own Cmd/Ctrl contract exactly,
        # in tests and the real app alike. Without either path, a Cmd-held
        # key press never reaches translate_key_event's Ctrl+<letter>
        # handling and reports empty event.text() (same as any other
        # OS-level shortcut), so paste needs its own path regardless.
        if event.key() == Qt.Key_V and event.modifiers() & Qt.MetaModifier:
            clipboard_text = QGuiApplication.clipboard().text()
            if clipboard_text:
                # A real Enter key sends "\r" (see _SIMPLE_KEYS below), not
                # "\n" -- translate a multi-line paste the same way so each
                # line actually submits instead of just inserting a newline.
                self.backend.write(clipboard_text.replace("\r\n", "\r").replace("\n", "\r"))
            return

        # Cmd+C. Ctrl+C (SIGINT) is untouched -- that's the ordinary
        # Ctrl+<letter> path below (modifiers & Qt.ControlModifier), a
        # completely different key given AA_MacDontSwapCtrlAndMeta. Cmd+C
        # with no active selection intentionally does nothing (matching
        # Terminal.app/iTerm2) rather than falling through to
        # translate_key_event -- Cmd-held key presses report empty
        # event.text() anyway, so there'd be nothing to send regardless.
        if event.key() == Qt.Key_C and event.modifiers() & Qt.MetaModifier:
            selected = self.selected_text()
            if selected:
                QGuiApplication.clipboard().setText(selected)
            return

        text = translate_key_event(event)
        if text == "\r" and self.screen is not None:
            # Known limitation: only the cursor's current visual row is
            # read here. A command line that wraps across more than one
            # visual row (narrow pane + long prompt/command) is captured
            # truncated -- the prompt and start of the command are lost --
            # since pyte exposes no per-line wrap flag to reconstruct the
            # full logical line. See the design spec's "Capture mechanism"
            # section; accepted, not a bug to chase.
            line = self.screen.get_line_text(self.screen.cursor.y).strip()
            if line:
                self._history.append(line)
                self._history = self._history[-MAX_HISTORY_ENTRIES:]
        if text:
            self.backend.write(text)

    def focusNextPrevChild(self, next: bool) -> bool:
        # Qt intercepts Tab/Shift+Tab for focus traversal before they ever
        # reach keyPressEvent unless a widget opts out here — without this,
        # Tab never reaches translate_key_event and the shell's
        # tab-completion is silently dead.
        return False

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(DEFAULT_BG))

        if self.screen is None:
            painter.end()
            return

        painter.setFont(self._font)
        cell_w, cell_h = self._cell_size()
        ascent = self._metrics.ascent()

        # self.screen may be *taller*/*wider* than what currently fits in
        # the widget (see _sync_size_to_widget: it only ever grows, to avoid
        # losing content on shrink) -- render just the window (ending at the
        # cursor's row) that corresponds to the pane's actual current size,
        # which is always where the shell's current output is.
        top_row, rows_to_render, visible_cols = compute_visible_window(
            self.screen.lines, self.screen.columns, self._visible_rows, self._visible_cols,
            cursor_row=self.screen.cursor.y,
        )
        selection = self._normalized_selection()

        for y in range(top_row, top_row + rows_to_render):
            screen_y = y - top_row
            for x in range(visible_cols):
                cell = self.screen.get_cell(x, y)
                fg, bg = cell.fg, cell.bg
                if cell.reverse:
                    fg, bg = bg, fg
                if bg not in (None, "default"):
                    painter.fillRect(x * cell_w, screen_y * cell_h, cell_w, cell_h, resolve_color(bg, cell.bold, is_fg=False))
                if cell.data != " ":
                    painter.setPen(resolve_color(fg, cell.bold, is_fg=True))
                    painter.drawText(x * cell_w, screen_y * cell_h + ascent, cell.data)
                if selection is not None and self._cell_is_selected(x, y, selection):
                    painter.fillRect(x * cell_w, screen_y * cell_h, cell_w, cell_h, SELECTION_OVERLAY)

        cursor = self.screen.cursor
        if not cursor.hidden and self._cursor_visible and cursor.y >= top_row and cursor.x < visible_cols:
            painter.fillRect(cursor.x * cell_w, (cursor.y - top_row) * cell_h, cell_w, cell_h, QColor(255, 255, 255, 120))

        painter.end()
