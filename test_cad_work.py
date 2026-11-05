"""CAD work reports nested drawing units, PDF replay units and cancellable phases."""

import tempfile
import unittest
from pathlib import Path
import ezdxf
from engine import convert
from bakuri.application.control import JobControl, Cancelled
from bakuri.application.progress import ProgressEstimate


class CadWorkTests(unittest.TestCase):
    def fixture(self, root):
        doc = ezdxf.new()
        block = doc.blocks.new("REPEATED")
        for i in range(450):
            block.add_line((i, 0), (i, 40))
        for x in range(4):
            doc.modelspace().add_blockref("REPEATED", (x * 500, 0))
        path = root / "drawing.dxf"
        doc.saveas(path)
        return path

    def test_nested_block_and_pdf_replay_have_measured_progress(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.fixture(root)
            values, work = [], []
            control = JobControl(
                lambda p, t: values.append((p, t)), lambda d, n, s: work.append((d, n, s))
            )
            convert([source], "pdf", control=control)
            rendering = [p for p, text in values if "도면 그리기" in text]
            self.assertGreater(len(set(rendering)), 20)
            for _, text in values:
                self.assertNotRegex(text, r"[0-9,]+/[0-9,]+개")
            samples = [(d, n) for d, n, s in work if s.endswith("도면 그리기")]
            self.assertEqual(samples[0], (0, 1804))
            self.assertTrue(any(0 < d < n for d, n in samples))
            self.assertTrue(any(0 < d < n for d, n, s in work if s.endswith("PDF 구성")))
            self.assertEqual([p for p, _ in values], sorted(p for p, _ in values))
            self.assertEqual(values[-1][0], 100)

    def test_cancel_during_replay_preserves_original_and_publishes_nothing(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = self.fixture(root)
            original = source.read_bytes()
            control = JobControl()

            def measured(done, total, stage):
                if stage.endswith("PDF 구성") and done > 0:
                    control.cancel()

            control.measurement = measured
            with self.assertRaises(Cancelled):
                convert([source], "pdf", control=control)
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(control.outputs, [])
            self.assertFalse(source.with_suffix(".pdf").exists())

    def test_stage_estimate_tracks_slower_units_and_discards_stale_predictions(self):
        now = [0.0]
        estimate = ProgressEstimate(lambda: now[0])
        estimate.update(40, "도면 그리기")
        estimate.measure(0, 100, "drawing")
        now[0] = 1
        estimate.measure(10, 100, "drawing")
        now[0] = 2
        estimate.measure(20, 100, "drawing")
        self.assertIn("이 단계 약 8초", estimate.label())
        now[0] = 5
        estimate.measure(23, 100, "drawing")
        self.assertIn("이 단계 약 17초", estimate.label())
        now[0] = 12
        self.assertIn("계산 중", estimate.label())
        self.assertIn("40%", estimate.label())
        estimate.measure(0, 0, "saving")
        self.assertIn("계산 대기", estimate.label())
        estimate.update(100, "완료")
        self.assertIn("100%", estimate.label())
