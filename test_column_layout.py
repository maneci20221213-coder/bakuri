"""Initial full-width columns and manual widths saved independently per tab."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["BAKURI_DISABLE_SHELL_INTEGRATION"] = "1"
import tempfile
import unittest
from pathlib import Path
from PySide6.QtCore import QSettings, QEvent, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication
from app import Window

APP = QApplication.instance() or QApplication([])


class ColumnLayoutTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.windows = []
        self.settings = QSettings(str(Path(self.temp.name) / "prefs.ini"), QSettings.IniFormat)

    def tearDown(self):
        for window in self.windows:
            window.tray.hide()
            window.hide()
            window.deleteLater()
        self.temp.cleanup()

    def window(self):
        window = Window()
        self.windows.append(window)
        window.settings = self.settings
        window.files.use_column_layout(lambda: window.settings, "convert")
        window.show()
        for _ in range(3):
            APP.processEvents()
        return window

    def drag_width(self, files, column, width):
        viewport = files.header().viewport()
        for kind, buttons in (
            (QEvent.MouseButtonPress, Qt.LeftButton),
            (QEvent.MouseButtonRelease, Qt.NoButton),
        ):
            event = QMouseEvent(
                kind, QPointF(100, 10), QPointF(100, 10), Qt.LeftButton, buttons, Qt.NoModifier
            )
            files.eventFilter(viewport, event)
            if kind == QEvent.MouseButtonPress:
                files.header().resizeSection(column, width)
        APP.processEvents()

    def test_default_columns_fill_window_after_resize(self):
        window = self.window()
        for width in (840, 1050):
            window.resize(width, 700)
            for _ in range(3):
                APP.processEvents()
            files = window.files
            total = sum(
                files.columnWidth(c)
                for c in range(files.columnCount())
                if not files.isColumnHidden(c)
            )
            self.assertLessEqual(abs(files.viewport().width() - total), 2)

    def test_user_widths_survive_new_window_and_tabs_without_shrinking_neighbors(self):
        window = self.window()
        files = window.files
        before = [files.columnWidth(c) for c in range(4)]
        self.drag_width(files, 2, before[2] + 100)
        self.assertEqual([files.columnWidth(c) for c in (0, 1, 3)], [before[c] for c in (0, 1, 3)])
        window.mode_tabs.setCurrentIndex(1)
        APP.processEvents()
        self.drag_width(files, 2, 280)
        window.mode_tabs.setCurrentIndex(0)
        APP.processEvents()
        self.assertEqual(files.columnWidth(2), before[2] + 100)
        other = self.window()
        self.assertEqual(other.files.columnWidth(2), before[2] + 100)
        other.mode_tabs.setCurrentIndex(1)
        APP.processEvents()
        self.assertEqual(other.files.columnWidth(2), 280)

    def test_broken_saved_widths_do_not_break_window(self):
        self.settings.setValue("file_columns/convert", '{"2": -50, "99": 200}')
        window = self.window()
        self.assertFalse(window.files.saved_sizing)
        self.assertGreater(window.files.columnWidth(2), 0)
