"""Completion cards stay visible for hidden main windows and respect opt-out."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import QApplication, QFormLayout, QLineEdit
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

    def test_progress_card_displays_percent_and_completion_restores_actions(self):
        w = self.window
        toast = w.results.toast
        toast.start_progress("0% · 작업 준비", w.tray.geometry())
        w.busy = True
        w.update_progress(37, "처리 중")
        self.assertTrue(toast.summary.text().startswith("37% · 처리 중"))
        self.assertIn("남은 시간 계산 중", toast.summary.text())
        self.assertEqual(toast.progress_bar.value(), 37)
        self.assertEqual(toast.progress_bar.text(), "37%")
        self.assertFalse(toast.actions.isVisible())
        self.assertFalse(toast.timer.isActive())
        w.results.finished(
            dict(
                paths=[],
                outcome="done",
                kind="compress",
                rows=[
                    {"status": "축소 효과 없음", "detail": "크기가 줄지 않았습니다."},
                    {"status": "건너뜀", "detail": "보호된 파일입니다."},
                    {"status": "실패", "detail": "처리 중 오류가 발생했습니다."},
                ],
            )
        )
        self.assertEqual(toast.summary.text(), "0개 저장 완료 · 실패 3개")
        self.assertEqual(w.last_result["rows"][1]["status"], "건너뜀")
        self.assertTrue(toast.actions.isVisible())
        self.assertTrue(toast.timer.isActive())

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

    def test_multiline_compression_footer_renders_links_and_escapes_notes(self):
        w = self.window
        row = dict(
            source="photo.jpg",
            output=str(Path(self.temp.name) / "photo_용량축소.jpeg"),
            before=6_850_000,
            after=2_090_000,
            status="저장 완료",
        )
        w.finished(
            dict(
                paths=[row["output"]],
                rows=[row],
                kind="compress",
                outcome="done",
                error="",
                notes=['<a href="unexpected">파일 이름 & 안내</a>'],
            )
        )
        w.status.setTextInteractionFlags(Qt.TextSelectableByMouse | Qt.LinksAccessibleByMouse)
        rendered = w.last_result["summary"] + " · 저장 폴더 열기 · 상세 결과"
        w.status.setSelection(0, len(rendered))
        visible = w.status.selectedText()
        self.assertIn("4.76 MB 절감", visible)
        self.assertIn("저장 폴더 열기", visible)
        self.assertIn("상세 결과", visible)
        self.assertNotIn('style="', visible)
        self.assertIn('<a href="unexpected">파일 이름 & 안내</a>', visible)
        with patch.object(w, "open_folders") as open_folder:
            w.status.linkActivated.emit("open")
            open_folder.assert_called_once_with([self.temp.name])
        with patch("bakuri.ui.results.CompressionResults") as details:
            w.status.linkActivated.emit("details")
            details.assert_called_once_with([row], w)
            details.return_value.exec.assert_called_once()
        w.status.setText("작업 준비 중")
        w.status.setSelection(0, len(w.status.text()))
        self.assertEqual(w.status.selectedText(), "작업 준비 중")

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

    def test_repeated_failure_after_progress_stays_inside_work_area(self):
        from PySide6.QtCore import QRect
        from bakuri.application.runner import run_job
        from bakuri.application.control import JobControl
        from bakuri.conversion.cad import CadError
        from user_messages import friendly_error

        screen = APP.primaryScreen().availableGeometry()
        tray = QRect(screen.right() - 20, screen.bottom() - 20, 16, 16)
        w = self.window
        toast = w.results.toast
        message = "DWG를 변환하려면 ODA File Converter를 설치하거나 DXF로 저장해 주세요."

        def fail(control):
            raise CadError(message)

        report = run_job(fail, JobControl(), "convert", friendly_error)
        with patch.object(w.tray, "geometry", return_value=tray):
            for _ in range(3):
                toast.start_progress("0% · 작업 준비", tray)
                w.results.finished(report)
                APP.processEvents()
                self.assertIn(message, toast.summary.text())
                self.assertTrue(screen.contains(toast.geometry()))
                self.assertTrue(
                    toast.rect().contains(
                        toast.actions.geometry().translated(toast.actions.parentWidget().pos())
                    )
                )

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

    def test_rename_counts_distinguish_entire_list_changes_and_errors(self):
        w = self.window
        panel = w.rename_panel
        panel.journal = Path(self.temp.name) / "rename.json"
        w.mode_tabs.setCurrentIndex(1)
        paths = [Path(self.temp.name) / name for name in ("a.pdf", "b.pdf")]
        for path in paths:
            path.write_bytes(b"original")
        w.files.add_paths(list(map(str, paths)))
        self.assertEqual(panel.message.text(), "변경 예정 0개 / 오류 0개")
        panel.string.setText("새_")
        self.assertEqual(panel.message.text(), "변경 예정 2개 / 오류 0개")
        w.files.item(0).setCheckState(0, Qt.Unchecked)
        self.assertEqual(panel.message.text(), "변경 예정 1개 / 오류 0개")
        w.files.item(0).setCheckState(0, Qt.Checked)
        for i in range(2):
            w.files.item(i).setText(4, "중복.pdf")
        self.assertEqual(panel.message.text(), "변경 예정 0개 / 오류 2개")
        w.files.item(0).setCheckState(0, Qt.Unchecked)
        self.assertEqual(panel.message.text(), "변경 예정 1개 / 오류 0개")
        panel.execute()
        self.assertEqual(panel.message.text(), "변경 예정 0개 / 오류 0개")
        panel.undo()
        self.assertEqual(panel.message.text(), "변경 예정 0개 / 오류 0개")
        w.files.clear()
        self.assertEqual(panel.message.text(), "변경 예정 0개 / 오류 0개")

    def test_completed_names_settle_until_settings_or_file_text_are_edited(self):
        w = self.window
        p = w.rename_panel
        p.journal = Path(self.temp.name) / "rename.json"
        w.mode_tabs.setCurrentIndex(1)
        paths = [Path(self.temp.name) / name for name in ["a.pdf", "b.pdf"]]
        for path in paths:
            path.write_bytes(b"original")
        w.files.add_paths(list(map(str, paths)))
        p.string.setText("새_")
        self.assertEqual(p.message.text(), "변경 예정 2개 / 오류 0개")
        p.execute()
        self.assertEqual(p.message.text(), "변경 예정 0개 / 오류 0개")
        self.assertFalse(p.run.isEnabled())
        p.refresh()
        w.files.sort_names()
        w.files.check_all(Qt.Unchecked)
        w.files.check_all(Qt.Checked)
        self.assertEqual(p.message.text(), "변경 예정 0개 / 오류 0개")
        p.undo()
        self.assertEqual(p.message.text(), "변경 예정 0개 / 오류 0개")
        p.string.setText("다시_")
        self.assertEqual(p.message.text(), "변경 예정 2개 / 오류 0개")
        p.execute()
        self.assertEqual(p.message.text(), "변경 예정 0개 / 오류 0개")
        p.text_enabled.setChecked(True)
        p.assign_values(["서울", "부산"])
        self.assertEqual(p.message.text(), "변경 예정 2개 / 오류 0개")
        p.execute()
        self.assertEqual(p.message.text(), "변경 예정 0개 / 오류 0개")
        p.assign_values(["대전", "광주"])
        self.assertEqual(p.message.text(), "변경 예정 2개 / 오류 0개")

    def test_summary_shares_button_line_and_uses_status_color_on_white_panel(self):
        from PySide6.QtCore import QPoint
        from PySide6.QtGui import QPalette

        w = self.window
        w.show()
        w.mode_tabs.setCurrentIndex(1)
        QTest.qWait(20)
        p = w.rename_panel
        self.assertEqual(p.message.palette().color(QPalette.WindowText).name(), "#718096")
        self.assertLessEqual(
            abs(p.message.geometry().center().y() - p.run.geometry().center().y()), 1
        )
        self.assertLess(p.message.geometry().right(), p.run.geometry().left())
        image = p.grab().toImage()
        self.assertEqual(image.pixelColor(QPoint(5, 5)).name(), "#ffffff")
        self.assertNotIn("목록", p.message.text())

    def test_number_parameters_keep_caption_close_and_numbers_centered(self):
        w = self.window
        w.show()
        w.mode_tabs.setCurrentIndex(1)
        p = w.rename_panel
        for width in (1100, 1250):
            w.resize(width, w.height())
            QTest.qWait(20)
            self.assertEqual(p.start.alignment(), Qt.AlignCenter)
            self.assertEqual(p.digits.alignment(), Qt.AlignCenter)
            self.assertEqual(p.start.width(), p.digits.width())
            for control, name in [
                (p.start, "시작 번호"),
                (p.digits, "자릿수"),
                (p.number_position, "추가할 위치"),
                (p.separator, "구분자"),
            ]:
                caption = control.parentWidget().layout().itemAt(0).widget()
                self.assertEqual(caption.text(), name)
                gap = control.geometry().left() - caption.geometry().right()
                self.assertGreater(gap, 0)
                self.assertLessEqual(gap, 8)

    def test_single_click_edits_both_text_columns_without_underlying_text(self):
        w = self.window
        path = Path(self.temp.name) / "original.pdf"
        path.write_bytes(b"fixture")
        w.files.add_paths([str(path)])
        w.show()
        w.mode_tabs.setCurrentIndex(1)
        w.rename_panel.text_enabled.setChecked(True)
        QTest.qWait(30)
        files = w.files
        for column in (4, 6):
            item = files.item(0)
            item.setText(6, "existing text")
            files.scrollToItem(item)
            index = files.model().index(0, column)
            files.scrollTo(index)
            QTest.qWait(20)
            QTest.mouseClick(files.viewport(), Qt.LeftButton, pos=files.visualRect(index).center())
            APP.processEvents()
            editor = APP.focusWidget()
            self.assertIsInstance(editor, QLineEdit)
            self.assertIn("background:#FFFFFF", editor.styleSheet())
            with patch("file_names.FileNameDelegate.paint", autospec=True) as underlying:
                files.viewport().repaint()
                APP.processEvents()
                self.assertNotIn(
                    column, [call.args[3].column() for call in underlying.call_args_list]
                )
            editor.setText("edited")
            QTest.keyClick(editor, Qt.Key_Return)
            APP.processEvents()
            self.assertTrue(item.text(column).startswith("edited"))
