"""Sequential submissions, immutable snapshots, cancellation and honest estimates."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ["BAKURI_DISABLE_SHELL_INTEGRATION"] = "1"

import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from PySide6.QtCore import QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from app import Window
from bakuri.application.progress import ProgressEstimate
from bakuri.domain.models import JobOutcome

APP = QApplication.instance() or QApplication([])


class EstimateTests(unittest.TestCase):
    def test_estimates_use_elapsed_work_and_never_invent_progress(self):
        now = [0.0]
        estimate = ProgressEstimate(lambda: now[0])
        self.assertIn("1%", estimate.label())
        self.assertIn("계산 중", estimate.label())
        now[0] = 10
        estimate.update(25, "처리 중")
        self.assertIn("약 30초", estimate.label(2))
        self.assertIn("대기 2개", estimate.label(2))
        now[0] = 80
        estimate.update(25, "외부 프로그램 응답 대기")
        self.assertIn("다시 계산 중", estimate.label())
        self.assertIn("25%", estimate.label())
        estimate.update(20, "저장 중")
        self.assertEqual(estimate.percent, 25)
        estimate.update(100, "완료")
        self.assertIn("100%", estimate.label())


class JobQueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.window = Window()
        self.window.settings = QSettings(
            str(Path(self.temp.name) / "prefs.ini"), QSettings.IniFormat
        )
        self.window.settings.setValue("notify", True)
        self.release = threading.Event()
        self.started = threading.Event()

    def tearDown(self):
        self.release.set()
        self.wait_until(lambda: not self.window.busy)
        self.window.results.toast.hide()
        self.window.tray.hide()
        self.window.hide()
        self.window.deleteLater()
        self.temp.cleanup()

    def wait_until(self, predicate):
        deadline = time.monotonic() + 8
        while not predicate() and time.monotonic() < deadline:
            QTest.qWait(10)
        self.assertTrue(predicate(), "Worker did not settle")

    def blocked(self, control):
        control.update(10, "처리 중")
        self.started.set()
        if not self.release.wait(5):
            raise TimeoutError("test barrier")
        control.check()
        control.complete()

    def start_blocked(self):
        self.window.begin_job(self.blocked, "convert")
        self.assertTrue(self.started.wait(2))
        APP.processEvents()

    def test_fifo_only_one_worker_and_live_controls_and_queue_notice(self):
        w = self.window
        self.start_blocked()
        events = []
        w.begin_job(lambda c: events.append("second"), "compress")
        w.begin_job(lambda c: events.append("third"), "convert")
        self.assertEqual(events, [])
        self.assertEqual(len(w.pending_jobs), 2)
        self.assertTrue(w.files.isEnabled())
        self.assertTrue(w.toolbar.isEnabled())
        self.assertTrue(w.fmt.isEnabled())
        self.assertEqual(w.run.text(), "대기열에 추가")
        self.assertFalse(w.mode_tabs.isTabEnabled(1))
        self.assertIn("대기열에 추가했습니다", w.results.toast.notice.text())
        self.assertIn("대기 2개", w.status.text())
        self.release.set()
        self.wait_until(lambda: not w.busy)
        self.assertEqual(events, ["second", "third"])
        self.assertTrue(w.mode_tabs.isTabEnabled(1))

    def test_queued_request_keeps_files_options_after_list_and_settings_change(self):
        w = self.window
        source = Path(self.temp.name) / "picture.png"
        Image.new("RGB", (10, 20)).save(source)
        self.start_blocked()
        w.settings.setValue("dpi", 300)
        w.start_conversion([str(source)], "pdf", False)
        request = w.pending_jobs[0][0]
        w.files.clear()
        w.settings.setValue("dpi", 96)
        self.assertEqual(request.options.dpi, 300)
        reports = []
        w.bus.done.connect(reports.append)
        self.release.set()
        self.wait_until(lambda: not w.busy and len(reports) == 2)
        self.assertEqual(len(reports), 2)
        self.assertTrue((source.with_suffix(".pdf")).is_file())

    def test_cancel_current_continues_queue_and_failure_does_not_stall_it(self):
        w = self.window
        self.start_blocked()
        calls, reports = [], []
        w.bus.done.connect(reports.append)

        def fail(control):
            calls.append("failed")
            raise ValueError("broken input")

        w.begin_job(fail, "convert")
        w.begin_job(lambda c: calls.append("last"), "convert")
        w.request_stop()
        self.assertTrue(w.run.isEnabled())
        self.release.set()
        with patch("user_messages.log_error"):
            self.wait_until(lambda: not w.busy and len(reports) == 3)
        self.assertEqual(calls, ["failed", "last"])
        self.assertEqual(
            [r.outcome for r in reports],
            [JobOutcome.CANCELLED, JobOutcome.FAILED, JobOutcome.DONE],
        )

    def test_clear_pending_does_not_cancel_current_and_opt_out_stays_silent(self):
        w = self.window
        w.settings.setValue("notify", False)
        self.start_blocked()
        calls = []
        with patch.object(w.results.toast, "queued") as notice:
            w.begin_job(lambda c: calls.append("queued"), "convert")
            notice.assert_not_called()
        w.clear_pending()
        self.assertFalse(w.control.cancelled.is_set())
        self.assertFalse(w.tray_clear_action.isEnabled())
        self.release.set()
        self.wait_until(lambda: not w.busy)
        self.assertEqual(calls, [])

    def test_quick_menu_submits_during_work(self):
        w = self.window
        self.start_blocked()
        w.quick_paths = ["example.png"]
        with patch.object(w, "start_conversion") as start:
            w.quick_selected("pdf")
            start.assert_called_once()
        with (
            patch.object(w.popup, "present") as popup,
            patch("bakuri.ui.main_window.Path.is_file", return_value=True),
        ):
            with patch("bakuri.ui.main_window.sys.platform", "linux"):
                w.receive((["example.png"], 0, 0))
            popup.assert_called_once()
        self.release.set()
