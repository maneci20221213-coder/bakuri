"""Executable entrypoint. Implementation lives in bakuri.ui."""

import sys
from build_channel import DEVELOPMENT

if __name__ == "__main__" and not DEVELOPMENT:
    from velopack_bootstrap import bootstrap

    bootstrap()

from bakuri.ui.main_window import Window
from bakuri.ui.quick_popup import QuickPopup
from bakuri.ui.startup import main, startup_error
from file_list import Files
from settings_ui import SettingsDialog

if __name__ == "__main__":
    sys.excepthook = startup_error
    main()

__all__ = ["Window", "QuickPopup", "main", "startup_error", "Files", "SettingsDialog"]
