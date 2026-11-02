"""Checked-file eligibility and the shared split/extract interaction."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch
import fitz
from PySide6.QtCore import Qt, QSettings
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox
from PySide6.QtTest import QTest
from app import Window, QuickPopup
from bakuri.ui.pdf_split import PdfSplitDialog
from bakuri.domain.models import PdfPagesRequest

APP = QApplication.instance() or QApplication([])


class PdfSplitUiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.w = Window()
        self.w.settings = QSettings(str(Path(self.temp.name) / "settings.ini"), QSettings.IniFormat)
        self.paths = []
        for name in ["one.pdf", "two.pdf"]:
            path = Path(self.temp.name) / name
            with fitz.open() as doc:
                for _ in range(10):
                    doc.new_page()
                doc.save(path)
            self.paths.append(str(path))
        self.w.show()

    def tearDown(self):
        self.w.popup.hide()
        self.w.results.toast.hide()
        self.w.tray.hide()
        self.w.hide()
        self.w.deleteLater()
        self.temp.cleanup()

    def test_main_uses_checked_files_and_only_pdf_output(self):
        w = self.w
        w.files.add_paths(self.paths)
        w.fmt.setCurrentText("PDF")
        APP.processEvents()
        self.assertTrue(w.merge.isVisible())
        self.assertFalse(w.pdf_pages.isVisible())
        w.files.item(1).setCheckState(0, Qt.Unchecked)
        APP.processEvents()
        self.assertTrue(w.pdf_pages.isVisible())
        self.assertFalse(w.merge.isVisible())
        self.assertEqual(w.individual.text(), "전체 저장")
        w.fmt.setCurrentText("PNG")
        APP.processEvents()
        self.assertFalse(w.pdf_pages.isVisible())
        w.fmt.setCurrentText("PDF")
        w.busy = True
        w.output_changed("PDF")
        self.assertFalse(w.pdf_pages.isEnabled())
        w.busy = False

    def test_popup_selects_split_for_one_and_merge_for_multiple(self):
        popup = QuickPopup()
        self.addCleanup(popup.hide)
        popup.present(self.paths[:1])
        self.assertEqual(popup.actions["pdf"], "pdf_split")
        self.assertEqual(popup.buttons["pdf"].accessibleName(), "페이지 나누기")
        popup.present(self.paths)
        self.assertEqual(popup.actions["pdf"], "pdf_merge")
        self.assertEqual(popup.buttons["pdf"].accessibleName(), "PDF 합치기")

    def test_dialog_summary_and_invalid_ranges(self):
        dialog = PdfSplitDialog(self.paths[0], 10, self.w)
        dialog.every.setValue(3)
        self.assertIn("PDF 4개", dialog.summary.text())
        dialog.mode.setCurrentIndex(1)
        self.assertFalse(dialog.buttons.button(QDialogButtonBox.Ok).isEnabled())
        dialog.selection.setText("8-10, 1-3, 5")
        self.assertIn("PDF 1개", dialog.summary.text())
        self.assertIn("7페이지", dialog.summary.text())
        dialog.separate.setChecked(True)
        self.assertIn("PDF 3개", dialog.summary.text())
        for text in ("0", "11", "3-1", "1-3, 3"):
            dialog.selection.setText(text)
            self.assertFalse(dialog.buttons.button(QDialogButtonBox.Ok).isEnabled())
        dialog.reject()

    def test_both_entry_points_freeze_the_same_request_and_cancel_does_nothing(self):
        w = self.w
        w.quick_paths = self.paths[:1]

        def configure(dialog):
            dialog.mode.setCurrentIndex(1)
            dialog.selection.setText("1-3, 5")
            return QDialog.Accepted

        with patch.object(PdfSplitDialog, "exec", configure), patch.object(w, "begin_job") as begin:
            w.quick_selected("pdf_split")
            request = begin.call_args.args[0]
            self.assertIsInstance(request, PdfPagesRequest)
            self.assertEqual(request.selection, "1-3, 5")
            self.assertEqual(request.file.path, self.paths[0])
            w.start_pdf_pages(self.paths[:1])
            self.assertEqual(begin.call_count, 2)
        with (
            patch.object(PdfSplitDialog, "exec", return_value=QDialog.Rejected),
            patch.object(w, "begin_job") as begin,
        ):
            w.start_pdf_pages(self.paths[:1])
            begin.assert_not_called()
