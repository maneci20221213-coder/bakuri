"""Qt signal boundary: workers never access widgets."""

from PySide6.QtCore import QObject, Signal


class Events(QObject):
    message = Signal(str)
    done = Signal(object)
    error = Signal(str)
    selected = Signal(object)
    clicked = Signal(object)
    dismiss = Signal()
    popup_key = Signal(int)
    progress = Signal(int, str)
