"""Completion cards stay visible for hidden main windows and respect opt-out."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication, QFormLayout
from PySide6.QtTest import QTest
from app import Window

APP = QApplication.instance() or QApplication([])


class CompletionUiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.window = Window()
        self.window.settings = QSettings(
            str(Path(self.temp.name) / "prefs.ini"), QSettings.IniFormat
        )

    def tearDown(self):
        self.window.results.toast.hide()
        self.window.tray.hide()
        self.window.hide()
        self.window.deleteLater()
        self.temp.cleanup()

    def test_hidden_main_window_shows_nonmodal_completion_and_auto_dismisses(self):
        w = self.window
        with patch.object(w.tray, "showMessage") as os_alert:
            w.show_completion("3개 저장 완료", [self.temp.name])
            APP.processEvents()
            toast = w.results.toast
            self.assertTrue(toast.isVisible())
            self.assertFalse(w.isVisible())
            self.assertEqual(toast.summary.text(), "3개 저장 완료")
            self.assertTrue(toast.windowFlags() & Qt.WindowDoesNotAcceptFocus)
            self.assertTrue(toast.testAttribute(Qt.WA_ShowWithoutActivating))
            self.assertTrue(toast.folder.isEnabled())
            os_alert.assert_not_called()
            toast.timer.start(1)
            QTest.qWait(20)
            self.assertFalse(toast.isVisible())

    def test_disabled_alert_keeps_recent_result_without_any_popup(self):
        w = self.window
        w.settings.setValue("notify", False)
        with (
            patch.object(w.results.toast, "present") as popup,
            patch.object(w.tray, "showMessage") as os_alert,
        ):
            w.show_completion("1개 저장 완료", [])
            popup.assert_not_called()
            os_alert.assert_not_called()
            self.assertEqual(w.last_result["summary"], "1개 저장 완료")
            self.assertTrue(w.tray_result_action.isEnabled())

    def test_repeated_completion_refreshes_one_card_and_folder_action(self):
        w = self.window
        w.show_completion("첫 결과", [])
        toast = w.results.toast
        self.assertFalse(toast.folder.isEnabled())
        w.show_completion("최신 결과", [self.temp.name], warning=True)
        self.assertIs(w.results.toast, toast)
        self.assertEqual(toast.summary.text(), "최신 결과")
        with patch.object(w.results, "open_folders") as open_folder:
            toast.folder.click()
            open_folder.assert_called_once_with([self.temp.name])
        self.assertFalse(toast.isVisible())

    def test_rename_titles_are_evenly_spaced_and_placeholder_removed(self):
        w = self.window
        w.show()
        w.mode_tabs.setCurrentIndex(1)
        APP.processEvents()
        panel = w.rename_panel
        form = panel.layout().itemAt(0).layout()
        labels = [form.itemAt(i, QFormLayout.LabelRole).widget() for i in range(3)]
        self.assertEqual(
            [label.text() for label in labels], ["찾아 바꾸기", "문자열 추가", "파일명 새로 쓰기"]
        )
        self.assertEqual(panel.base.placeholderText(), "")
        centers = [label.geometry().center().y() for label in labels]
        self.assertLessEqual(abs((centers[1] - centers[0]) - (centers[2] - centers[1])), 2)

    def test_six_rows_visible_and_undo_button_tracks_completed_change(self):
        w = self.window
        panel = w.rename_panel
        panel.journal = Path(self.temp.name) / "rename.json"
        paths = [Path(self.temp.name) / f"자료_{i}.pdf" for i in range(6)]
        for path in paths:
            path.write_bytes(b"unchanged")
        w.files.add_paths(list(map(str, paths)))
        w.show()
        w.mode_tabs.setCurrentIndex(1)
        panel.refresh()
        QTest.qWait(50)
        self.assertLessEqual(
            w.files.visualItemRect(w.files.item(5)).bottom(), w.files.viewport().height()
        )
        self.assertEqual(panel.restore.text(), "실행 취소")
        self.assertEqual(panel.restore.size(), panel.run.size())
        self.assertGreater(panel.restore.x(), panel.run.geometry().right())
        self.assertFalse(panel.restore.isEnabled())
        panel.string.setText("새_")
        panel.run.click()
        self.assertTrue(panel.restore.isEnabled())
        panel.restore.click()
        self.assertFalse(panel.restore.isEnabled())
        self.assertTrue(all(path.is_file() for path in paths))

    def test_help_separates_tasks_and_excludes_developer_patch_notes(self):
        from help_ui import HelpDialog

        dialog = HelpDialog(self.window)
        self.assertEqual(
            [dialog.tabs.tabText(i) for i in range(3)],
            ["파일 형식 변환", "파일명 변경", "패치노트"],
        )
        self.assertIn("실행 취소", dialog.rename_text.toPlainText())
        self.assertNotIn("개발용", dialog.notes.toPlainText())
        self.assertNotIn("dev.", dialog.notes.toPlainText())
        dialog.reject()
