from PySide6.QtGui import QColor

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
