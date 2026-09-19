import re

import pyte

# pyte has no notion of the Kitty/xterm "progressive keyboard enhancement"
# protocol: CSI > flags u (push), CSI < [Pn] u (pop), CSI = flags [; mode] u
# (set), CSI ? u (query). Modern TUI frameworks push it on startup and pop
# it on exit (e.g. Ink, which Claude Code's own CLI is built on) -- entirely
# harmless to a terminal that doesn't support it, PROVIDED the terminal at
# least recognizes and discards the whole sequence. pyte's CSI parser
# handles the '>'/'?' forms fine, but doesn't accept '<'/'=' as a private-
# marker byte before a 'u' final byte, so for those two it falls through
# and treats the whole parameter string plus the trailing "u" as literal
# printable characters instead (e.g. "CSI < u" -> prints "u"; "CSI = 1;2 u"
# -> prints "1;2u") -- e.g. quitting a nested Claude Code session leaves a
# stray "u" sitting on screen. Strip all four forms before pyte ever sees
# them (harmless to also strip the two it already handles correctly); we
# don't implement (or need) that protocol regardless. Parameters can
# contain ';' as well as digits (e.g. "=1;2u"), not just digits alone.
_KITTY_KEYBOARD_PROTOCOL_RE = re.compile(r"\x1b\[[<>=?][\d;]*u")


class TerminalScreen:
    def __init__(self, columns: int, lines: int, history: int = 2000):
        self._screen = pyte.HistoryScreen(columns, lines, history=history)
        self._stream = pyte.Stream(self._screen)

    def feed(self, text: str) -> None:
        text = _KITTY_KEYBOARD_PROTOCOL_RE.sub("", text)
        self._stream.feed(text)

    def resize(self, columns: int, lines: int) -> None:
        self._screen.resize(lines=lines, columns=columns)

    @property
    def columns(self) -> int:
        return self._screen.columns

    @property
    def lines(self) -> int:
        return self._screen.lines

    @property
    def cursor(self):
        return self._screen.cursor

    def get_cell(self, x: int, y: int):
        return self._screen.buffer[y][x]

    def get_line_text(self, y: int) -> str:
        return "".join(self._screen.buffer[y][x].data for x in range(self._screen.columns)).rstrip()
