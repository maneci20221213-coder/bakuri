"""PDF page plans and native copying preserve page content and source files."""

import tempfile
from pathlib import Path
import unittest
from unittest.mock import Mock, patch
import fitz
from bakuri.domain.pdf_selection import page_groups
from bakuri.conversion.pdf_split import split_pdf, pdf_page_count
from bakuri.conversion.office_split import _HancomPages
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

    def test_selection_validation_and_input_order(self):
        self.assertEqual(page_groups(7, every=3), ((0, 1, 2), (3, 4, 5), (6,)))
        self.assertEqual(
            page_groups(10, "extract", selection="8-10, 1-3, 3, 5"), ((7, 8, 9, 0, 1, 2, 4),)
        )
        self.assertEqual(
            page_groups(10, "extract", selection="5, 1-3", separate=True), ((4,), (0, 1, 2))
        )
        self.assertEqual(
            page_groups(7, "boundaries", selection="6, 3"), ((0, 1), (2, 3, 4), (5, 6))
        )
        for text in ["", "1", "8", "2-3"]:
            with self.subTest(text=text), self.assertRaises(ValueError):
                page_groups(7, "boundaries", selection=text)
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
            self.assertEqual([p.get_text().strip() for p in doc], ["Page 5", "Page 1", "Page 7"])
            self.assertEqual(doc[1].get_links()[0]["page"], 0)
            self.assertEqual(doc[0].get_links()[0]["uri"], "https://example.org")
            self.assertEqual(doc.get_toc(), [[1, "First", 2], [2, "Fifth", 1], [1, "Last", 3]])
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

    def test_pdf_split_compacts_objects_without_changing_rendered_pages(self):
        output = Path(split_pdf(self.path, every=5)[0])
        previous = output.with_name("previous.pdf")
        with fitz.open(output) as doc, fitz.open(self.path) as original:
            doc.save(previous, garbage=4, deflate=True)
            for index, page in enumerate(doc):
                self.assertEqual(page.get_pixmap().samples, original[index].get_pixmap().samples)
        self.assertLess(output.stat().st_size, previous.stat().st_size)

    def test_office_split_uses_native_suffix_and_requested_order(self):
        for suffix, adapter in (
            (".hwp", "_HancomPages"),
            (".hwpx", "_HancomPages"),
            (".doc", "_WordPages"),
            (".docx", "_WordPages"),
        ):
            source = self.path.with_name("office" + suffix)
            source.write_bytes(b"original")

            def save(original, dest, spans, page_count, control):
                self.assertEqual(original.read_bytes(), b"original")
                self.assertEqual(dest.suffix, suffix)
                self.assertEqual(spans, [(30, 40), (10, 20)])
                self.assertEqual(page_count, 2)
                dest.write_bytes(b"editable result")

            with (
                patch("bakuri.conversion.office_split.OfficeSession") as session,
                patch(f"bakuri.conversion.office_split.{adapter}") as editor,
            ):
                session.return_value.__enter__.return_value = session.return_value
                editor.return_value.count.return_value = 7
                editor.return_value.position.side_effect = lambda page, count: page * 10
                editor.return_value.save.side_effect = save
                report = run_job(
                    PdfPagesRequest(InputFile(source), mode="extract", selection="4, 2"),
                    JobControl(),
                    "convert",
                    lambda error, context: str(error),
                )
                session.return_value.export.assert_not_called()
                editor.return_value.close.assert_called_once()

            self.assertEqual(report.outcome, "done", report.error)
            output = Path(report.paths[0])
            self.assertTrue(output.parent.samefile(source.parent))
            self.assertEqual(output.name, "office_추출본" + suffix)
            self.assertEqual(output.read_bytes(), b"editable result")
            self.assertEqual(source.read_bytes(), b"original")

    def test_hancom_only_removes_an_empty_page_past_the_requested_count(self):
        for total, end, begin, after, commands in (
            (2, (0, 4, 0), (0, 4, 0), 1, []),
            (3, (0, 4, 1), (0, 4, 0), 2, ["MoveDocEnd", "MovePageBegin"]),
            (3, (0, 4, 0), (0, 4, 0), 2, ["MoveDocEnd", "MovePageBegin", "DeleteBack"]),
            (3, (0, 4, 0), (0, 4, 0), 3, ["MoveDocEnd", "MovePageBegin", "DeleteBack", "Undo"]),
        ):
            with self.subTest(total=total, end=end, begin=begin, after=after):
                app = Mock(PageCount=total)
                app.GetPos.side_effect = [end, begin]

                def run(action):
                    if action == "DeleteBack":
                        app.PageCount = after
                    return True

                app.HAction.Run.side_effect = run
                editor = _HancomPages(app, self.path)
                editor._trim_trailing_blank_pages(2, JobControl())
                self.assertEqual([call.args[0] for call in app.HAction.Run.call_args_list], commands)

    def test_password_pdf_rejected_without_outputs(self):
        locked = self.path.with_name("locked.pdf")
        with fitz.open(self.path) as doc:
            doc.save(
                locked, encryption=fitz.PDF_ENCRYPT_AES_256, user_pw="secret", owner_pw="owner"
            )
        with self.assertRaises(ValueError):
            split_pdf(locked)
        self.assertFalse(list(self.path.parent.glob("locked_*")))
