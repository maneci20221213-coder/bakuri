"""Cross-layer contracts: frozen requests, partial outcomes, stable file IDs."""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("BAKURI_DISABLE_SHELL_INTEGRATION", "1")
from dataclasses import FrozenInstanceError
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

from PIL import Image
import fitz
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication
from bakuri.application.control import JobControl
from bakuri.application.runner import run_job
from bakuri.application.settings import conversion_options, compression_options
from bakuri.domain.models import (
    InputFile,
    ConversionRequest,
    CompressionRequest,
    CompressionOptions,
    RenameOptions,
    JobOutcome,
    JobKind,
)
from bakuri.ui.main_window import Window

APP = QApplication.instance() or QApplication([])


class RequestTests(unittest.TestCase):
    def test_startup_error_remains_friendly_without_imported_qt(self):
        import app
        import ctypes

        notice = types.SimpleNamespace(MessageBoxW=lambda *args: None)
        with (
            patch.dict("sys.modules", {"PySide6.QtWidgets": None}),
            patch("app.sys.platform", "win32"),
            patch("app.friendly_error", return_value="사용자 안내") as friendly,
            patch.object(ctypes, "windll", types.SimpleNamespace(user32=notice), create=True),
            patch.object(notice, "MessageBoxW") as message,
        ):
            app.startup_error(ImportError, ImportError("private dependency details"), None)
            self.assertEqual(friendly.call_args.args[1], "startup")
            self.assertEqual(message.call_args.args[1], "사용자 안내")

    def test_request_copies_order_and_rejects_field_mutation(self):
        inputs = [InputFile("b.png"), InputFile("a.png")]
        request = ConversionRequest(inputs, "JPG")
        inputs.clear()
        self.assertEqual([Path(x.path).name for x in request.files], ["b.png", "a.png"])
        self.assertEqual(request.output.value, "jpeg")
        with self.assertRaises(FrozenInstanceError):
            request.merge = True
        texts = {"a": "before"}
        options = RenameOptions(text_by_source=texts)
        texts["a"] = "after"
        self.assertEqual(options.text_by_source["a"], "before")
        with self.assertRaises(TypeError):
            options.text_by_source["a"] = "mutated"

    def test_settings_snapshot_does_not_follow_later_changes(self):
        with tempfile.TemporaryDirectory() as d:
            settings = QSettings(str(Path(d) / "prefs.ini"), QSettings.IniFormat)
            settings.setValue("dpi", 300)
            settings.setValue("compress_profile", "p50")
            conversion = conversion_options(settings)
            compression = compression_options(settings)
            settings.setValue("dpi", 96)
            settings.setValue("compress_profile", "p10")
            self.assertEqual(conversion.dpi, 300)
            self.assertEqual(compression.profile, "p50")
            settings.setValue("dpi", 99999)
            settings.setValue("image_mode", "invalid")
            self.assertEqual(conversion_options(settings).dpi, 150)
            self.assertEqual(conversion_options(settings).image_mode, "background")

    def test_native_adapter_returns_typed_report_and_preserves_pixels(self):
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / "한글.png"
            Image.new("RGBA", (37, 59), (20, 90, 180, 255)).save(source)
            original = source.read_bytes()
            report = run_job(
                ConversionRequest((InputFile(str(source)),), "pdf"),
                JobControl(),
                JobKind.CONVERT,
                lambda e, c: "safe error",
            )
            self.assertEqual(report.outcome, JobOutcome.DONE)
            self.assertEqual(len(report.paths), 1)
            with fitz.open(report.paths[0]) as document:
                self.assertEqual(len(document), 1)
                self.assertAlmostEqual(document[0].rect.width, 37 * 72 / 150, places=3)
            self.assertEqual(source.read_bytes(), original)

    def test_typed_compression_rows_and_skipped_result(self):
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / "small.jpeg"
            Image.new("RGB", (10, 20), "red").save(source)
            request = CompressionRequest((InputFile(str(source)),), CompressionOptions("size"))
            report = run_job(request, JobControl(), "compress", lambda e, c: "safe error")
            self.assertEqual(report.outcome, JobOutcome.DONE)
            self.assertEqual(report.paths, ())
            self.assertEqual(report.rows[0].status, "건너뜀")
            self.assertEqual(Path(report.rows[0].source).resolve(), source.resolve())

    def test_failure_retains_published_outputs_and_sanitizes_error(self):
        with tempfile.TemporaryDirectory() as d:
            source = Path(d) / "source.txt"
            source.write_bytes(b"original")

            def operation(control):
                control.publish(source, Path(d) / "result.txt")
                raise RuntimeError("private internal details")

            calls = []

            def error_message(exc, context):
                calls.append(context)
                return "사용자 안내"

            report = run_job(operation, JobControl(), "convert", error_message)
            self.assertEqual(report.outcome, JobOutcome.FAILED)
            self.assertEqual(report.error, "사용자 안내")
            self.assertEqual(calls, ["conversion"])
            self.assertEqual(Path(report.paths[0]).read_bytes(), b"original")

    def test_cancelled_report_is_detached_from_mutable_control(self):
        control = JobControl()

        def operation(job):
            job.outputs.append("completed.pdf")
            job.cancel()
            job.check()

        report = run_job(operation, control, "convert", lambda e, c: "unexpected")
        control.outputs.clear()
        self.assertEqual(report.outcome, JobOutcome.CANCELLED)
        self.assertEqual(report.paths, ("completed.pdf",))
        self.assertEqual(report.error, "")


class GuiBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.window = Window()
        self.window.settings = QSettings(str(self.root / "settings.ini"), QSettings.IniFormat)
        self.window.settings.setValue("notify", False)
        self.window.rename_panel.journal = self.root / "rename.json"

    def tearDown(self):
        self.window.tray.hide()
        self.window.hide()
        self.window.deleteLater()
        self.temp.cleanup()

    def test_ui_freezes_paths_and_settings_before_worker(self):
        source = self.root / "a.png"
        Image.new("RGB", (5, 8)).save(source)
        w = self.window
        w.files.add_paths([str(source)])
        identifier = w.files.inputs_for([str(source)])[0].file_id
        paths = [str(source)]
        w.settings.setValue("dpi", 300)
        with patch.object(w, "begin_job") as begin:
            w.start_conversion(paths, "pdf", False)
        request = begin.call_args.args[0]
        paths.clear()
        w.files.clear()
        w.settings.setValue("dpi", 96)
        self.assertEqual(request.files[0].path, str(source))
        self.assertEqual(request.files[0].file_id, identifier)
        self.assertEqual(request.options.dpi, 300)

    def test_file_id_survives_sort_rename_and_undo(self):
        sources = [self.root / "b.txt", self.root / "a.txt"]
        for source in sources:
            source.write_text("original")
        w = self.window
        w.mode_tabs.setCurrentIndex(1)
        w.files.add_paths([str(p) for p in sources])
        before = {Path(x.path).name: x.file_id for x in w.files.inputs_for(map(str, sources))}
        w.files.sort_names()
        w.rename_panel.string.setText("new_")
        w.rename_panel.execute()
        after = w.files.inputs_for(w.files.checked_paths())
        self.assertEqual([x.file_id for x in after], [before["a.txt"], before["b.txt"]])
        self.assertEqual([Path(x.path).name for x in after], ["new_a.txt", "new_b.txt"])
        w.rename_panel.undo()
        self.assertEqual(
            [Path(x.path).name for x in w.files.inputs_for(w.files.checked_paths())],
            ["a.txt", "b.txt"],
        )

    def test_report_flows_through_qt_worker_to_completion(self):
        from PySide6.QtTest import QTest, QSignalSpy
        import time

        source = self.root / "a.png"
        Image.new("RGB", (12, 18)).save(source)
        w = self.window
        reports = QSignalSpy(w.bus.done)
        w.start_conversion([str(source)], "pdf", False)
        deadline = time.monotonic() + 15
        while (w.busy or reports.count() == 0) and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertFalse(w.busy)
        self.assertGreater(reports.count(), 0, "Worker completion signal was not delivered")
        self.assertEqual(reports.at(0)[0].outcome, JobOutcome.DONE)
        self.assertIn("1개 저장 완료", w.last_result["summary"])
        self.assertTrue((self.root / "a.pdf").is_file())
