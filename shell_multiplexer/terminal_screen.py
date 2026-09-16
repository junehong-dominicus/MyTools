import pyte


class TerminalScreen:
    def __init__(self, columns: int, lines: int, history: int = 2000):
        self._screen = pyte.HistoryScreen(columns, lines, history=history)
        self._stream = pyte.Stream(self._screen)

    def feed(self, text: str) -> None:
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
