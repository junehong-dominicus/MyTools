from PySide6.QtCore import QEvent, Qt
from PySide6.QtGui import QKeyEvent

from input_translator import translate_key_event


def make_key_event(key, modifiers=Qt.NoModifier, text=""):
    return QKeyEvent(QEvent.KeyPress, key, modifiers, text)


def test_plain_character_passes_through(qapp):
    event = make_key_event(Qt.Key_A, text="a")
    assert translate_key_event(event) == "a"


def test_up_arrow_maps_to_escape_sequence(qapp):
    event = make_key_event(Qt.Key_Up)
    assert translate_key_event(event) == "\x1b[A"


def test_left_arrow_maps_to_escape_sequence(qapp):
    event = make_key_event(Qt.Key_Left)
    assert translate_key_event(event) == "\x1b[D"


def test_ctrl_c_maps_to_etx(qapp):
    event = make_key_event(Qt.Key_C, modifiers=Qt.ControlModifier)
    assert translate_key_event(event) == "\x03"


def test_ctrl_z_maps_to_0x1a(qapp):
    event = make_key_event(Qt.Key_Z, modifiers=Qt.ControlModifier)
    assert translate_key_event(event) == "\x1a"


def test_enter_maps_to_carriage_return(qapp):
    event = make_key_event(Qt.Key_Return, text="\r")
    assert translate_key_event(event) == "\r"


def test_backspace_maps_to_del(qapp):
    event = make_key_event(Qt.Key_Backspace)
    assert translate_key_event(event) == "\x7f"


def test_f5_maps_to_xterm_sequence(qapp):
    event = make_key_event(Qt.Key_F5)
    assert translate_key_event(event) == "\x1b[15~"


def test_shift_tab_maps_to_reverse_tab_sequence(qapp):
    # Qt delivers Shift+Tab as Key_Backtab (not Key_Tab + ShiftModifier).
    event = make_key_event(Qt.Key_Backtab, modifiers=Qt.ShiftModifier)
    assert translate_key_event(event) == "\x1b[Z"
