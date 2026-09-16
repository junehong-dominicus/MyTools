from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter
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


def compute_grid_size(widget_width: int, widget_height: int, cell_width: int, cell_height: int) -> tuple[int, int]:
    cols = max(1, widget_width // cell_width)
    rows = max(1, widget_height // cell_height)
    return cols, rows


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
        self._font = QFont("Consolas", 10)
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

        self.setFocusPolicy(Qt.StrongFocus)

    def _cell_size(self) -> tuple[int, int]:
        return self._metrics.horizontalAdvance("W"), self._metrics.height()

    def start(self, cwd: str) -> None:
        cell_w, cell_h = self._cell_size()
        cols, rows = compute_grid_size(self.width(), self.height(), cell_w, cell_h)
        self.screen = TerminalScreen(columns=cols, lines=rows)
        self.backend.spawn(cwd, columns=cols, lines=rows)
        self._repaint_timer.start()

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
        if self.screen:
            cell_w, cell_h = self._cell_size()
            cols, rows = compute_grid_size(self.width(), self.height(), cell_w, cell_h)
            self.screen.resize(columns=cols, lines=rows)
            self.backend.resize(cols, rows)
        super().resizeEvent(event)

    def keyPressEvent(self, event) -> None:
        text = translate_key_event(event)
        if text:
            self.backend.write(text)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(DEFAULT_BG))

        if self.screen is None:
            painter.end()
            return

        painter.setFont(self._font)
        cell_w, cell_h = self._cell_size()
        ascent = self._metrics.ascent()

        for y in range(self.screen.lines):
            for x in range(self.screen.columns):
                cell = self.screen.get_cell(x, y)
                fg, bg = cell.fg, cell.bg
                if cell.reverse:
                    fg, bg = bg, fg
                if bg not in (None, "default"):
                    painter.fillRect(x * cell_w, y * cell_h, cell_w, cell_h, resolve_color(bg, cell.bold, is_fg=False))
                if cell.data != " ":
                    painter.setPen(resolve_color(fg, cell.bold, is_fg=True))
                    painter.drawText(x * cell_w, y * cell_h + ascent, cell.data)

        cursor = self.screen.cursor
        if not cursor.hidden and self._cursor_visible:
            painter.fillRect(cursor.x * cell_w, cursor.y * cell_h, cell_w, cell_h, QColor(255, 255, 255, 120))

        painter.end()
