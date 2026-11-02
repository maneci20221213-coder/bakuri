"""PDF page plans and native copying preserve page content and source files."""

import tempfile
from pathlib import Path
import unittest
import fitz
from bakuri.domain.pdf_selection import page_groups
from bakuri.conversion.pdf_split import split_pdf, pdf_page_count
from bakuri.application.control import JobControl, Cancelled
from bakuri.application.runner import run_job
from bakuri.domain.models import PdfPagesRequest, InputFile


class PdfSplitTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "문서.pdf"
        with fitz.open() as doc:
            for i in range(7):
                p = doc.new_page(width=200 + i, height=300 + i)
                p.insert_text((20, 30), f"Page {i + 1}")
                if i == 2:
                    p.set_rotation(90)
            doc[0].insert_link(
                {
                    "kind": fitz.LINK_GOTO,
                    "from": fitz.Rect(10, 40, 80, 60),
                    "page": 4,
                    "to": fitz.Point(0, 0),
                }
            )
            doc[4].insert_link(
                {
                    "kind": fitz.LINK_URI,
                    "from": fitz.Rect(10, 40, 80, 60),
                    "uri": "https://example.org",
                }
            )
            doc[2].insert_link(
                {
                    "kind": fitz.LINK_URI,
                    "from": fitz.Rect(10, 40, 80, 60),
                    "uri": "https://example.org/rotated",
                }
            )
            doc[2].add_text_annot((50, 80), "retain annotation")
            doc.set_toc([[1, "First", 1], [2, "Fifth", 5], [1, "Last", 7]])
            doc.set_metadata({"title": "Original title"})
            doc.save(self.path)
        self.before = self.path.read_bytes()

    def test_selection_validation_and_original_order(self):
        self.assertEqual(page_groups(7, every=3), ((0, 1, 2), (3, 4, 5), (6,)))
        self.assertEqual(
            page_groups(10, "extract", selection="8-10, 1-3, 3, 5"), ((0, 1, 2, 4, 7, 8, 9),)
        )
        self.assertEqual(
            page_groups(10, "extract", selection="5, 1-3", separate=True), ((0, 1, 2), (4,))
        )
        for text in ["", "0", "8", "3-1", "1,,2", "1;2", "bad"]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                page_groups(7, "extract", selection=text)
        with self.assertRaises(ValueError):
            page_groups(7, "extract", selection="1-3, 3", separate=True)

    def test_interval_geometry_annotations_and_collision(self):
        self.assertEqual(pdf_page_count(self.path), 7)
        existing = self.path.with_name("문서_001-003쪽.pdf")
        existing.write_bytes(b"existing")
        outputs = split_pdf(self.path, every=3)
        self.assertEqual(
            [Path(p).name for p in outputs],
            ["문서_001-003쪽_1.pdf", "문서_004-006쪽.pdf", "문서_007쪽.pdf"],
        )
        with fitz.open(self.path) as source:
            for group, path in zip(page_groups(7, every=3), outputs):
                with fitz.open(path) as result:
                    self.assertEqual(len(result), len(group))
                    for i, page in enumerate(group):
                        self.assertEqual(result[i].rect, source[page].rect)
                        self.assertEqual(result[i].rotation, source[page].rotation)
                        self.assertEqual(result[i].get_text(), source[page].get_text())
                        if page == 2:
                            self.assertEqual(
                                result[i].get_links()[0]["from"],
                                source[page].get_links()[0]["from"],
                            )
                    self.assertEqual(result.metadata["title"], "Original title")
            with fitz.open(outputs[0]) as result:
                self.assertEqual(next(result[2].annots()).info["content"], "retain annotation")
        self.assertEqual(self.path.read_bytes(), self.before)
        self.assertEqual(existing.read_bytes(), b"existing")

    def test_disjoint_extraction_remaps_links_and_bookmarks(self):
        paths = split_pdf(self.path, "extract", selection="5, 1, 7")
        with fitz.open(paths[0]) as doc:
            self.assertEqual([p.get_text().strip() for p in doc], ["Page 1", "Page 5", "Page 7"])
            self.assertEqual(doc[0].get_links()[0]["page"], 1)
            self.assertEqual(doc[1].get_links()[0]["uri"], "https://example.org")
            self.assertEqual(doc.get_toc(), [[1, "First", 1], [2, "Fifth", 2], [1, "Last", 3]])
        paths = split_pdf(self.path, "extract", selection="1, 5", separate=True)
        with fitz.open(paths[0]) as doc:
            self.assertEqual(doc[0].get_links(), [])

    def test_cancel_after_first_publish_retains_completed_output(self):
        control = JobControl()
        publish = control.publish

        def once(source, desired):
            result = publish(source, desired)
            control.cancel()
            return result

        control.publish = once
        report = run_job(
            PdfPagesRequest(InputFile(str(self.path)), every=3),
            control,
            "convert",
            lambda e, c: str(e),
        )
        self.assertEqual(report.outcome, "cancelled")
        self.assertEqual(len(report.paths), 1)
        self.assertTrue(Path(report.paths[0]).is_file())
        self.assertEqual(self.path.read_bytes(), self.before)
        self.assertFalse(list(self.path.parent.glob("*004*")))
        with self.assertRaises(Cancelled):
            split_pdf(self.path, control=control)

    def test_password_pdf_rejected_without_outputs(self):
        locked = self.path.with_name("locked.pdf")
        with fitz.open(self.path) as doc:
            doc.save(
                locked, encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="secret", owner_pw="owner"
            )
        with self.assertRaises(ValueError):
            split_pdf(locked)
        self.assertFalse(list(self.path.parent.glob("locked_*")))
