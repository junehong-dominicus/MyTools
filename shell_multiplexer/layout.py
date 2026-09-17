LAYOUT_MODES = ["1", "2", "2V", "3", "3T", "4"]

_ROWS_BY_MODE = {
    "1": [[1]],
    "2": [[1, 2]],
    "2V": [[1], [2]],
    "3": [[1, 2], [3]],
    "3T": [[1], [2, 3]],
    "4": [[1, 2], [3, 4]],
}


def compute_grid_rows(mode: str) -> list[list[int]]:
    """Return the pane-id rows for a layout mode, matching the Serial
    Monitor's original 1/2/3/4 shapes plus two stacked variants: "2V" (two
    panes stacked instead of side-by-side) and "3T" (one full-width pane on
    top of two, instead of two on top of one)."""
    if mode not in _ROWS_BY_MODE:
        raise ValueError(f"unknown layout mode: {mode!r}")
    return _ROWS_BY_MODE[mode]


def pane_count_for_mode(mode: str) -> int:
    return sum(len(row) for row in compute_grid_rows(mode))
