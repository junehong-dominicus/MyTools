def compute_grid_rows(count: int) -> list[list[int]]:
    """Group pane ids 1..count into rows of at most 2, matching the
    Serial Monitor's layout: 1->single, 2->side-by-side, 3->2-over-1,
    4->2x2."""
    if not (1 <= count <= 4):
        raise ValueError(f"count must be between 1 and 4, got {count}")

    rows = []
    pane_id = 1
    remaining = count
    while remaining > 0:
        row_size = min(2, remaining)
        rows.append(list(range(pane_id, pane_id + row_size)))
        pane_id += row_size
        remaining -= row_size
    return rows
