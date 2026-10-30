"""Executable entrypoint. Implementation lives in bakuri.ui."""

import sys
from build_channel import DEVELOPMENT
from user_messages import friendly_error


def startup_error(kind, value, tb):
    """Stay available even when importing Qt or another startup dependency fails."""
    widgets = sys.modules.get("PySide6.QtWidgets")
    application = getattr(widgets, "QApplication", None)
    running = application is not None and application.instance() is not None
    message = friendly_error(value, "conversion" if running else "startup")
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, "바꾸리 안내", 16)


if __name__ == "__main__":
    sys.excepthook = startup_error

if __name__ == "__main__" and not DEVELOPMENT:
    from velopack_bootstrap import bootstrap

    bootstrap()

from bakuri.ui.main_window import Window
from bakuri.ui.quick_popup import QuickPopup
from bakuri.ui.startup import main
from file_list import Files
from settings_ui import SettingsDialog

if __name__ == "__main__":
    main()

__all__ = ["Window", "QuickPopup", "main", "startup_error", "Files", "SettingsDialog"]
