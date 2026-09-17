from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent

_ARROW_AND_NAV = {
    Qt.Key_Up: "\x1b[A",
    Qt.Key_Down: "\x1b[B",
    Qt.Key_Right: "\x1b[C",
    Qt.Key_Left: "\x1b[D",
    Qt.Key_Home: "\x1b[H",
    Qt.Key_End: "\x1b[F",
    Qt.Key_Insert: "\x1b[2~",
    Qt.Key_Delete: "\x1b[3~",
    Qt.Key_PageUp: "\x1b[5~",
    Qt.Key_PageDown: "\x1b[6~",
}

_FUNCTION_KEYS = {
    Qt.Key_F1: "\x1bOP",
    Qt.Key_F2: "\x1bOQ",
    Qt.Key_F3: "\x1bOR",
    Qt.Key_F4: "\x1bOS",
    Qt.Key_F5: "\x1b[15~",
    Qt.Key_F6: "\x1b[17~",
    Qt.Key_F7: "\x1b[18~",
    Qt.Key_F8: "\x1b[19~",
    Qt.Key_F9: "\x1b[20~",
    Qt.Key_F10: "\x1b[21~",
    Qt.Key_F11: "\x1b[23~",
    Qt.Key_F12: "\x1b[24~",
}

_SIMPLE_KEYS = {
    Qt.Key_Return: "\r",
    Qt.Key_Enter: "\r",
    Qt.Key_Tab: "\t",
    Qt.Key_Backspace: "\x7f",
    Qt.Key_Escape: "\x1b",
    # Qt delivers Shift+Tab as its own key code (Key_Backtab) rather than
    # Key_Tab + ShiftModifier, so it needs its own mapping or it falls
    # through to event.text() (empty for this key) and PSReadLine's reverse
    # tab-completion never receives anything.
    Qt.Key_Backtab: "\x1b[Z",
}


def translate_key_event(event: QKeyEvent) -> str:
    """Return the text to write to the pty for this key event ("" if
    nothing should be sent)."""
    key = event.key()
    modifiers = event.modifiers()

    if modifiers & Qt.ControlModifier and Qt.Key_A <= key <= Qt.Key_Z:
        return chr(key - Qt.Key_A + 1)  # Ctrl+A -> 0x01 ... Ctrl+Z -> 0x1a

    if key in _ARROW_AND_NAV:
        return _ARROW_AND_NAV[key]
    if key in _FUNCTION_KEYS:
        return _FUNCTION_KEYS[key]
    if key in _SIMPLE_KEYS:
        return _SIMPLE_KEYS[key]

    return event.text()
