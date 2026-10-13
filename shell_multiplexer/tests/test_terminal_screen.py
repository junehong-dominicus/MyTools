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


def test_get_line_text_returns_typed_content():
    screen = TerminalScreen(columns=10, lines=2)
    screen.feed("hi")
    assert screen.get_line_text(0) == "hi"


def test_get_line_text_strips_trailing_padding():
    screen = TerminalScreen(columns=10, lines=2)
    screen.feed("hi")
    assert len(screen.get_line_text(0)) == len("hi")


def test_get_line_text_on_second_row():
    screen = TerminalScreen(columns=10, lines=2)
    screen.feed("ab\r\ncd")
    assert screen.get_line_text(1) == "cd"


def test_shrink_preserves_prompt_and_wraps_at_new_width():
    screen = TerminalScreen(columns=80, lines=24)
    screen.feed("prompt> ")
    screen.resize(columns=10, lines=3)
    assert screen.get_line_text(0) == "prompt>"
    screen.feed("abcdefghijk")
    assert screen.columns == 10 and screen.lines == 3
    assert screen.get_line_text(0) == "prompt> ab"
    assert screen.get_line_text(1) == "cdefghijk"
    assert screen.cursor.y == 1


def test_shrink_keeps_cursor_row_and_moves_old_rows_into_history():
    screen = TerminalScreen(columns=20, lines=6)
    screen.feed("one\r\ntwo\r\nthree\r\nfour\r\nfive")
    screen.resize(columns=20, lines=2)
    assert screen.get_line_text(0) == "four"
    assert screen.get_line_text(1) == "five"
    assert screen.cursor.y == 1
    assert len(screen._screen.history.top) == 3
