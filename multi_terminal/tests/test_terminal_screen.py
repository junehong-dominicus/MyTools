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


def test_kitty_keyboard_protocol_pop_sequence_does_not_leak_a_literal_u():
    # Regression test: pyte's CSI parser doesn't accept '<' as a private-
    # marker byte before a bare 'u' final byte (the Kitty/xterm keyboard
    # protocol's "pop" sequence, CSI < u) -- it falls through and prints
    # the trailing "u" as a literal character instead of discarding the
    # whole (unknown, harmless) sequence. Reproduced against a real Claude
    # Code CLI session's exit sequence (built on Ink, which pushes/pops
    # this protocol) -- quitting one running inside a pane left a stray
    # "u" sitting on screen right where the prompt should have been clean.
    screen = TerminalScreen(columns=40, lines=5)
    screen.feed("before")
    screen.feed("\x1b[<u")
    screen.feed("after")
    assert screen.get_line_text(0) == "beforeafter"


def test_kitty_keyboard_protocol_all_forms_are_stripped():
    # pyte itself already handles the '>' (push) and '?' (query) forms
    # without leaking -- only '<' (pop) and '=' (set) leak their parameter
    # string plus the trailing 'u' as literal text (verified directly
    # against pyte: "\x1b[<3u" -> "3u", "\x1b[=1;2u" -> "1;2u"). All four
    # are stripped regardless, since harmlessly stripping an already-fine
    # sequence costs nothing and keeps this test agnostic to pyte's exact
    # per-form quirks.
    screen = TerminalScreen(columns=40, lines=5)
    screen.feed("a\x1b[>4ub\x1b[<3uc\x1b[=1;2ud\x1b[?ue")
    assert screen.get_line_text(0) == "abcde"
