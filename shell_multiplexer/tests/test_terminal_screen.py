from terminal_screen import TerminalScreen


def test_feed_plain_text_updates_display():
    screen = TerminalScreen(columns=10, lines=2)
    screen.feed("hi")
    assert screen.get_cell(0, 0).data == "h"
    assert screen.get_cell(1, 0).data == "i"


def test_resize_changes_dimensions():
    screen = TerminalScreen(columns=10, lines=2)
    screen.resize(columns=20, lines=5)
    assert screen.columns == 20
    assert screen.lines == 5


def test_sgr_red_foreground_is_captured():
    screen = TerminalScreen(columns=10, lines=2)
    screen.feed("\x1b[31mred\x1b[0m")
    assert screen.get_cell(0, 0).fg == "red"


def test_cursor_advances_with_input():
    screen = TerminalScreen(columns=10, lines=2)
    screen.feed("ab")
    assert screen.cursor.x == 2
    assert screen.cursor.y == 0


def test_carriage_return_and_newline_move_cursor_to_next_line():
    screen = TerminalScreen(columns=10, lines=2)
    screen.feed("ab\r\ncd")
    assert screen.get_cell(0, 1).data == "c"
