import pytest

from layout import compute_grid_rows


def test_count_1_is_single_row():
    assert compute_grid_rows(1) == [[1]]


def test_count_2_is_side_by_side():
    assert compute_grid_rows(2) == [[1, 2]]


def test_count_3_is_two_over_one():
    assert compute_grid_rows(3) == [[1, 2], [3]]


def test_count_4_is_two_by_two():
    assert compute_grid_rows(4) == [[1, 2], [3, 4]]


def test_count_out_of_range_raises():
    with pytest.raises(ValueError):
        compute_grid_rows(0)
    with pytest.raises(ValueError):
        compute_grid_rows(5)
