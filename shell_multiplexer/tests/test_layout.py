import pytest

from layout import LAYOUT_MODES, compute_grid_rows, pane_count_for_mode


def test_mode_1_is_single_row():
    assert compute_grid_rows("1") == [[1]]


def test_mode_2_is_side_by_side():
    assert compute_grid_rows("2") == [[1, 2]]


def test_mode_2v_is_stacked():
    assert compute_grid_rows("2V") == [[1], [2]]


def test_mode_3_is_one_over_two():
    assert compute_grid_rows("3") == [[1], [2, 3]]


def test_mode_3t_is_two_over_one():
    assert compute_grid_rows("3T") == [[1, 2], [3]]


def test_mode_4_is_two_by_two():
    assert compute_grid_rows("4") == [[1, 2], [3, 4]]


def test_unknown_mode_raises():
    with pytest.raises(ValueError):
        compute_grid_rows("5")
    with pytest.raises(ValueError):
        compute_grid_rows("2v")  # case-sensitive, not "2V"


def test_layout_modes_lists_all_six_in_order():
    assert LAYOUT_MODES == ["1", "2", "2V", "3", "3T", "4"]


def test_pane_count_for_mode():
    assert pane_count_for_mode("1") == 1
    assert pane_count_for_mode("2") == 2
    assert pane_count_for_mode("2V") == 2
    assert pane_count_for_mode("3") == 3
    assert pane_count_for_mode("3T") == 3
    assert pane_count_for_mode("4") == 4
