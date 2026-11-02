"""Choice cancellation, one-batch remember and main/quick shared entry points."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtWidgets import QApplication, QDialog
from PySide6.QtCore import QSettings
from bakuri.domain.models import InputFile
from bakuri.ui.multi_image import choose_multi_images, MultiImageDialog
from bakuri.conversion.multi_image import inspect_multi_image
from test_multi_image import make_mpo, patch_entries
from app import Window

APP = QApplication.instance() or QApplication([])


class MultiImageUiTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.paths = [make_mpo(root / f"사진{i}.jpg") for i in range(2)]
        self.files = tuple(InputFile(str(p)) for p in self.paths)
        self.w = Window()
        self.w.settings = QSettings(str(root / "prefs.ini"), QSettings.IniFormat)

    def tearDown(self):
        self.w.popup.hide()
        self.w.results.toast.hide()
        self.w.tray.hide()
        self.w.hide()
        self.w.deleteLater()

    def test_remember_applies_only_within_batch_and_auxiliary_remains_primary(self):
        seen = []

        def all_images(dialog):
            seen.append(dialog)
            dialog.apply_remaining.setChecked(True)
            dialog.choice = "all"
            return QDialog.Accepted

        with patch.object(MultiImageDialog, "exec", all_images):
            choices = choose_multi_images(self.files, self.w)
            self.assertEqual([x.mode for x in choices], ["all", "all"])
            self.assertEqual(len(seen), 1)
            choose_multi_images(self.files, self.w)
            self.assertEqual(len(seen), 2)
            patch_entries(self.paths[1], [(1, 0, 0x010001)])
            choices = choose_multi_images(self.files, self.w)
            self.assertEqual([x.mode for x in choices], ["all", "primary"])
            self.assertTrue(choices[1].auxiliary)

    def test_cancel_second_dialog_starts_no_job(self):
        count = []

        def cancel(dialog):
            count.append(1)
            dialog.choice = "primary"
            return QDialog.Accepted if len(count) == 1 else QDialog.Rejected

        with (
            patch.object(MultiImageDialog, "exec", cancel),
            patch.object(self.w, "begin_job") as begin,
        ):
            self.w.start_conversion([str(p) for p in self.paths], "pdf", False)
            begin.assert_not_called()
        self.assertFalse(list(self.paths[0].parent.glob("*.pdf")))

    def test_conversion_and_compression_capture_frozen_choices(self):
        def primary(dialog):
            dialog.choice = "primary"
            return QDialog.Accepted

        with (
            patch.object(MultiImageDialog, "exec", primary),
            patch.object(self.w, "begin_job") as begin,
        ):
            self.w.start_conversion([str(self.paths[0])], "pdf", False)
            conversion = begin.call_args.args[0]
            self.w.start_compression([str(self.paths[0])])
            compression = begin.call_args.args[0]
        self.assertEqual(conversion.multi_images, compression.multi_images)
        self.assertEqual(conversion.multi_images[0].count, 2)
        self.assertEqual(conversion.multi_images[0], inspect_multi_image(self.paths[0]))

    def test_auxiliary_does_not_show_dialog_and_notes_reach_completion(self):
        patch_entries(self.paths[0], [(1, 0, 0x010001)])
        with patch.object(MultiImageDialog, "exec") as dialog:
            choices = choose_multi_images(self.files[:1], self.w)
            dialog.assert_not_called()
        self.assertTrue(choices[0].auxiliary)
        from bakuri.domain.models import JobReport, JobKind, JobOutcome

        self.w.finished(JobReport(JobKind.CONVERT, JobOutcome.DONE, notes=("대표 이미지만 선택",)))
        self.assertIn("대표 이미지만 선택", self.w.last_result["summary"])
