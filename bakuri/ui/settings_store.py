"""QSettings channel isolation and legacy migration; main-thread only."""

from PySide6.QtCore import QSettings
from build_channel import DEVELOPMENT, DEFAULT_HOTKEY


def initialize_settings(self):
    first_run = not self.settings.allKeys() and not QSettings("Bakuri", "Python Trial").allKeys()
    if not DEVELOPMENT and not self.settings.value("settings_migrated", False, type=bool):
        legacy = QSettings("Bakuri", "Python Trial")
        for key in legacy.allKeys():
            if not self.settings.contains(key):
                self.settings.setValue(key, legacy.value(key))
        self.settings.setValue("settings_migrated", True)
        self.settings.sync()
    if DEVELOPMENT and not self.settings.value("development_hotkey_ready", False, type=bool):
        self.settings.setValue("hotkey", DEFAULT_HOTKEY)
        self.settings.setValue("development_hotkey_ready", True)
    return first_run
