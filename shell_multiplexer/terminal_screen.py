import pyte


class TerminalScreen:
    def __init__(self, columns: int, lines: int, history: int = 2000):
        self._screen = pyte.HistoryScreen(columns, lines, history=history)
        self._stream = pyte.Stream(self._screen)

    def feed(self, text: str) -> None:
        self._stream.feed(text)

    def resize(self, columns: int, lines: int) -> None:
        screen = self._screen
        if (columns, lines) == (screen.columns, screen.lines):
            return
        old_x, old_y = screen.cursor.x, screen.cursor.y
        # Discard unused bottom rows before removing content from the top.
        # pyte's default shrink always drops top rows, including a fresh prompt.
        offset = max(0, old_y - lines + 1) if lines < screen.lines else 0
        rows = {y - offset: row.copy() for y, row in screen.buffer.items()
                if offset <= y < offset + lines}
        if offset:
            screen.history.top.extend(screen.buffer[y].copy() for y in range(offset))
        screen.resize(lines=lines, columns=columns)
        screen.buffer.clear()
        for y, row in rows.items():
            target = screen.buffer[y]
            target.update({x: cell for x, cell in row.items() if x < columns})
        screen.cursor.y = min(old_y - offset, lines - 1)
        # A cursor at columns denotes a pending autowrap, which pyte supports.
        screen.cursor.x = min(old_x, columns)

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
