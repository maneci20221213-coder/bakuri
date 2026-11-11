"""Spreadsheet sheet order, original preservation, output routing and UI entry points."""

import copy
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("BAKURI_DISABLE_SHELL_INTEGRATION", "1")

from PySide6.QtCore import QSettings, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QDialogButtonBox
from bakuri.application.control import JobControl
from bakuri.application.runner import execute, run_job
from bakuri.domain.models import InputFile, SheetsRequest, SheetSelectionError
from bakuri.domain.quick_actions import action_available
from bakuri.conversion.office import OfficeSession
from bakuri.conversion.spreadsheets import inspect_sheets, unique_sheet_name
from bakuri.ui.sheets import SheetsDialog
from bakuri.ui.main_window import Window

APP = QApplication.instance() or QApplication([])


class CellValues:
    def __init__(self, sheet):
        self.sheet = sheet
        self.value = ((123,),)

    @property
    def Value2(self):
        return self.value

    @Value2.setter
    def Value2(self, value):
        self.value = value
        self.sheet.formula = False


class Sheet:
    def __init__(self, book, name, hidden=False, formula=True):
        self.book, self.Name = book, name
        self.Visible = 0 if hidden else -1
        self.Type = -4167
        self.ProtectContents = False
        self.UsedRange = CellValues(self)
        self.formula = formula

    def Copy(self):
        output = self.book.app.new_book([self.Name])
        output.sheets[0].formula = self.formula
        self.book.app.ActiveWorkbook = output

    def Delete(self):
        self.book.sheets.remove(self)


class SheetCollection:
    def __init__(self, book):
        self.book = book

    @property
    def Count(self):
        return len(self.book.sheets)

    def Item(self, index):
        if isinstance(index, str):
            return next(sheet for sheet in self.book.sheets if sheet.Name == index)
        return self.book.sheets[index - 1]

    def Copy(self, After):
        self.book.app.copies.append([sheet.Name for sheet in self.book.sheets])
        for sheet in self.book.sheets:
            duplicate = Sheet(After.book, sheet.Name, sheet.Visible != -1, sheet.formula)
            duplicate.UsedRange.value = copy.deepcopy(sheet.UsedRange.Value2)
            After.book.sheets.append(duplicate)


class Book:
    def __init__(self, app, names, macro=False):
        self.app = app
        self.sheets = [Sheet(self, name) for name in names]
        self.Sheets = self.Worksheets = SheetCollection(self)
        self.HasVBProject = macro
        self.ProtectStructure = False
        self.Names = SimpleNamespace(Count=0)
        self.closed = False
        self.saved = False

    def SaveAs(self, name, FileFormat):
        assert FileFormat == 51
        self.saved = True
        Path(name).write_text(json.dumps([sheet.Name for sheet in self.sheets]))

    def LinkSources(self, kind):
        return ("source.xlsx",) if self.app.links else None

    def Close(self, save):
        assert save is False
        self.closed = True


class SheetsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.first, self.second = self.root / "one.xlsx", self.root / "two.xlsx"
        for path in (self.first, self.second):
            path.write_bytes(b"original")
        self.app = SimpleNamespace(links=False, copies=[], books=[])

        def new_book(names, macro=False):
            book = Book(self.app, names, macro)
            self.app.books.append(book)
            return book

        self.app.new_book = new_book
        self.app.Workbooks = SimpleNamespace(Add=lambda count: new_book(["Sheet1"]))
        self.names = {self.first: ["자료", "기준"], self.second: ["자료", "요약"]}
        self.patch_excel = patch.object(OfficeSession, "excel", return_value=self.app)
        self.patch_open = patch.object(
            OfficeSession, "open_spreadsheet", side_effect=lambda path: new_book(self.names[path])
        )
        self.patch_excel.start()
        self.patch_open.start()

    def tearDown(self):
        self.patch_open.stop()
        self.patch_excel.stop()
        self.temp.cleanup()

    def test_merge_copies_groups_in_file_order_and_resolves_duplicate_sheet_names(self):
        request = SheetsRequest((InputFile(self.first), InputFile(self.second)), merge=True)
        (output,) = execute(request, JobControl())
        self.assertEqual(json.loads(Path(output).read_text()), ["자료", "기준", "two_자료", "요약"])
        self.assertEqual(self.app.copies, [["자료", "기준"], ["two_자료", "요약"]])
        self.assertTrue(
            all(sheet.formula for book in self.app.books if book.saved for sheet in book.sheets)
        )
        self.assertEqual(Path(output).parent, self.root)
        self.assertTrue(all(book.closed for book in self.app.books))
        self.assertEqual(self.first.read_bytes(), b"original")
        self.assertEqual(self.second.read_bytes(), b"original")

    def test_split_selection_uses_sheet_names_and_smart_output_count(self):
        request = SheetsRequest((InputFile(self.first),), sheets=("기준", "자료"))
        outputs = execute(request, JobControl())
        self.assertEqual([Path(path).name for path in outputs], ["one_기준.xlsx", "one_자료.xlsx"])
        self.assertTrue(all(Path(path).parent == self.root / "바꾸리 변환" for path in outputs))
        (output,) = execute(SheetsRequest((InputFile(self.first),), sheets=("자료",)), JobControl())
        self.assertEqual(Path(output).parent, self.root)

    def test_changed_source_rejected_and_cancel_retains_first_completed_sheet(self):
        names, stamp = inspect_sheets(self.first, JobControl())
        self.assertEqual([name for name, hidden in names], self.names[self.first])
        self.first.write_bytes(b"changed")
        request = SheetsRequest((InputFile(self.first),), sheets=("자료",), fingerprint=stamp)
        with self.assertRaises(SheetSelectionError):
            execute(request, JobControl())
        control = JobControl()
        publish = control.publish

        def stop(source, desired):
            result = publish(source, desired)
            control.cancel()
            return result

        control.publish = stop
        report = run_job(
            SheetsRequest((InputFile(self.first),), sheets=("자료", "기준")),
            control,
            "convert",
            lambda error, context: str(error),
        )
        self.assertEqual(report.outcome, "cancelled")
        self.assertEqual(len(report.paths), 1)
        self.assertTrue(Path(report.paths[0]).is_file())
        self.assertTrue(all(book.closed for book in self.app.books))

    def test_macro_rejected_and_external_references_are_reported(self):
        self.app.links = True
        control = JobControl()
        execute(SheetsRequest((InputFile(self.first),), sheets=("자료",)), control)
        self.assertIn("다른 파일을 참조", control.notes[0])
        with patch.object(
            OfficeSession, "open_spreadsheet", return_value=self.app.new_book(["매크로"], True)
        ):
            with self.assertRaisesRegex(SheetSelectionError, "매크로"):
                execute(SheetsRequest((InputFile(self.first),), sheets=("매크로",)), JobControl())

    def test_values_mode_replaces_formulas_in_copies_and_keeps_original_files(self):
        for merge, paths in ((False, (self.first,)), (True, (self.first, self.second))):
            request = SheetsRequest(
                tuple(InputFile(p) for p in paths), merge=merge, sheets=("자료",), values_only=True
            )
            result = execute(request, JobControl())
            self.assertTrue(result)
            self.assertFalse(
                any(sheet.formula for book in self.app.books for sheet in book.sheets if book.saved)
            )
            self.assertEqual(self.first.read_bytes(), b"original")
            self.app.books.clear()

    def test_conflicting_workbook_names_fail_before_publishing(self):
        def new_names(reference):
            return SimpleNamespace(
                Count=1, Item=lambda index: SimpleNamespace(Name="계산기준", RefersTo=reference)
            )

        add = self.app.Workbooks.Add

        def create(kind):
            book = add(kind)
            book.Names = new_names("=1")
            return book

        def open_source(path):
            book = self.app.new_book(self.names[path])
            book.Names = new_names("=2")
            return book

        self.app.Workbooks.Add = create
        with patch.object(OfficeSession, "open_spreadsheet", side_effect=open_source):
            control = JobControl()
            with self.assertRaisesRegex(SheetSelectionError, "이름 관리자"):
                execute(
                    SheetsRequest((InputFile(self.first), InputFile(self.second)), merge=True),
                    control,
                )
            self.assertEqual(control.outputs, [])

    def test_duplicate_names_respect_excel_length_and_case(self):
        result = unique_sheet_name("A" * 40, {"a" * 31})
        self.assertEqual(result, "A" * 29 + "_1")
        self.assertLessEqual(len(unique_sheet_name("😀" * 40, set()).encode("utf-16-le")), 62)


class SheetUiTests(unittest.TestCase):
    def test_sheet_dialog_loads_async_and_freezes_selected_names(self):
        with patch(
            "bakuri.ui.sheets.inspect_sheets",
            return_value=((("한달", False), ("숨김", True)), (12, 34)),
        ):
            dialog = SheetsDialog(["one.xlsx"])
            dialog.show()
            for _ in range(50):
                QTest.qWait(10)
                if dialog.sheets.count():
                    break
            self.assertEqual(dialog.selected_sheets(), ("한달", "숨김"))
            self.assertEqual(dialog.fingerprint, (12, 34))
            dialog.select_all(False)
            self.assertFalse(dialog.buttons.button(QDialogButtonBox.Ok).isEnabled())
            dialog.sheets.item(1).setCheckState(Qt.Checked)
            self.assertEqual(dialog.selected_sheets(), ("숨김",))
            dialog.reject()

    def test_popup_defaults_customization_and_main_entry_points(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = [root / "a.xlsx", root / "b.xlsx"]
            for path in paths:
                path.write_bytes(b"xlsx")
            w = Window()
            w.settings = QSettings(str(root / "prefs.ini"), QSettings.IniFormat)
            w.popup.settings = w.settings
            try:
                for selected, expected in ((paths[:1], "sheet_split"), (paths, "sheet_merge")):
                    w.popup.present(selected)
                    self.assertEqual(
                        [w.popup.actions[k] for k in ("pdf", "png", "jpeg")],
                        [expected, "pdf", "png"],
                    )
                    self.assertTrue(w.popup.buttons["pdf"].isEnabled())
                w.settings.setValue("quick_menu/sheet/pdf", "jpeg")
                w.popup.present(paths)
                self.assertEqual(w.popup.actions["pdf"], "jpeg")
                w.settings.remove("quick_menu")
                self.assertFalse(action_available("sheet_split", paths))
                self.assertFalse(action_available("sheet_merge", paths[:1]))
                w.files.add_paths([str(path) for path in paths])
                w.fmt.setCurrentText("시트 합치기")
                with patch.object(w, "start_sheets") as start:
                    w.start()
                    start.assert_called_once_with([str(path) for path in paths], True)
                w.quick_paths = [str(paths[0])]
                with patch.object(w, "start_sheets") as start:
                    w.quick_selected("sheet_split")
                    start.assert_called_once_with(w.quick_paths, False)
                with (
                    patch("bakuri.ui.sheets.SheetsDialog") as dialog,
                    patch.object(w, "begin_job") as begin,
                ):
                    dialog.return_value.exec.return_value = QDialog.Accepted
                    dialog.return_value.selected_sheets.return_value = ("자료",)
                    dialog.return_value.values_only.isChecked.return_value = True
                    dialog.return_value.fingerprint = (12, 34)
                    w.start_sheets(w.quick_paths)
                    request = begin.call_args.args[0]
                    self.assertEqual(request.sheets, ("자료",))
                    self.assertTrue(request.values_only)
                    self.assertEqual(request.location.mode, "smart")
            finally:
                w.popup.motion.reset()
                w.tray.hide()
                w.hide()
