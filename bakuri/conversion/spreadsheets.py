"""Copy complete Excel sheets through the existing, worker-owned Office session."""

from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
import re

from bakuri.domain.formats import SPREADSHEETS
from bakuri.domain.models import SheetSelectionError
from merged_names import merged_path
from .office import OfficeSession


def fingerprint(path):
    info = Path(path).stat()
    return info.st_size, info.st_mtime_ns


def _check_source(path, expected):
    if fingerprint(path) != expected:
        raise SheetSelectionError("원본 파일이 변경되었습니다. 파일을 다시 선택해 주세요.")


def _check_workbook(book):
    if book.HasVBProject or any(
        book.Sheets.Item(i).Type in {3, 4} for i in range(1, book.Sheets.Count + 1)
    ):
        raise SheetSelectionError(
            "매크로가 포함된 파일입니다. Excel에서 매크로 없는 XLSX 사본을 만든 뒤 다시 선택해 주세요."
        )
    if not book.Sheets.Count:
        raise SheetSelectionError("저장할 시트가 없습니다.")


def inspect_sheets(path, control):
    path = Path(path).resolve()
    expected = fingerprint(path)
    with OfficeSession() as session:
        session.control = control
        book = session.open_spreadsheet(path)
        try:
            _check_workbook(book)
            names = []
            for index in range(1, book.Sheets.Count + 1):
                control.check()
                sheet = book.Sheets.Item(index)
                names.append((str(sheet.Name), sheet.Visible != -1))
            _check_source(path, expected)
            return tuple(names), expected
        finally:
            book.Close(False)


def unique_sheet_name(name, occupied):
    name = re.sub(r"[:\\/?*\[\]\x00-\x1f]", "_", name).strip("'") or "시트"
    number = 0
    while True:
        suffix = "" if not number else f"_{number}"
        limit = 31 - len(suffix)
        stem = name.encode("utf-16-le")[: limit * 2].decode("utf-16-le", errors="ignore")
        result = stem.rstrip("'") + suffix
        if result.casefold() not in occupied:
            return result
        number += 1


def _sheet_values(sheet, control):
    control.check()
    if sheet.ProtectContents:
        raise SheetSelectionError(
            "보호된 시트의 수식을 값으로 바꿀 수 없습니다. Excel에서 시트 보호를 해제해 주세요."
        )
    used = sheet.UsedRange
    used.Value2 = used.Value2


def _defined_names(book):
    names = {}
    for index in range(1, book.Names.Count + 1):
        item = book.Names.Item(index)
        name = str(item.Name)
        if "!" not in name:
            names[name.casefold()] = str(item.RefersTo)
    return names


def _save(book, path, control):
    control.check()
    book.SaveAs(str(path), FileFormat=51)
    control.check()
    if not path.is_file():
        raise RuntimeError("Excel 파일 저장에 실패했습니다.")
    if book.LinkSources(1):
        note = "다른 파일을 참조하는 수식이나 차트가 있습니다. 원본 파일을 이동하기 전에 결과를 확인해 주세요."
        if note not in control.notes:
            control.notes.append(note)


def process_sheets(request, control):
    paths = [Path(file.path).resolve() for file in request.files]
    if any(path.suffix.lower() not in SPREADSHEETS for path in paths):
        raise SheetSelectionError("Excel 파일을 선택해 주세요.")
    with OfficeSession() as session, TemporaryDirectory(prefix="BakuriSheets-") as directory:
        session.control = control
        folder = Path(directory)
        app = session.excel()
        if request.merge:
            _merge(session, app, paths, request.values_only, folder, control)
        else:
            _split(session, app, paths[0], request, folder, control)
    control.complete()
    return list(control.outputs)


def _merge(session, app, paths, values_only, folder, control):
    output = app.Workbooks.Add(-4167)  # xlWBATWorksheet; ignore custom Excel templates.
    try:
        app.Calculation = -4135
        app.CalculateBeforeSave = False
        placeholder = output.Sheets.Item(1)
        placeholder.Name = "_Bakuri_" + uuid4().hex[:16]
        occupied = {str(placeholder.Name).casefold()}
        for index, path in enumerate(paths):
            control.update(5 + 80 * index / len(paths), f"시트 합치기 · {path.name}")
            expected = fingerprint(path)
            source = session.open_spreadsheet(path)
            try:
                _check_workbook(source)
                source_names = {
                    str(source.Sheets.Item(i).Name).casefold()
                    for i in range(1, source.Sheets.Count + 1)
                }
                for number in range(1, source.Sheets.Count + 1):
                    control.check()
                    sheet = source.Sheets.Item(number)
                    name = str(sheet.Name)
                    if name.casefold() in occupied:
                        if source.ProtectStructure:
                            raise SheetSelectionError(
                                "같은 시트 이름이 있어 변경이 필요합니다. Excel에서 문서 구조 보호를 해제해 주세요."
                            )
                        name = unique_sheet_name(f"{path.stem}_{name}", occupied | source_names)
                        sheet.Name = name
                        source_names.add(name.casefold())
                        note = "중복된 시트 이름을 바꿨습니다. 시트명을 직접 적어 참조하는 수식은 결과를 확인해 주세요."
                        if note not in control.notes:
                            control.notes.append(note)
                    occupied.add(name.casefold())
                existing, incoming = _defined_names(output), _defined_names(source)
                if any(
                    existing[name] != incoming[name] for name in existing.keys() & incoming.keys()
                ):
                    raise SheetSelectionError(
                        "파일마다 다르게 정의된 같은 이름의 범위가 있습니다. Excel의 이름 관리자에서 이름을 구분한 뒤 다시 합쳐 주세요."
                    )
                if values_only:
                    for number in range(1, source.Worksheets.Count + 1):
                        _sheet_values(source.Worksheets.Item(number), control)
                source.Sheets.Copy(After=output.Sheets.Item(output.Sheets.Count))
                _check_source(path, expected)
            finally:
                source.Close(False)
        if not any(output.Sheets.Item(i).Visible == -1 for i in range(2, output.Sheets.Count + 1)):
            output.Sheets.Item(2).Visible = -1
        placeholder.Delete()
        control.update(90, "합친 Excel 파일 저장 중")
        staged = folder / "merged.xlsx"
        _save(output, staged, control)
        control.publish(staged, merged_path(paths, "xlsx"))
    finally:
        output.Close(False)


def _split(session, app, path, request, folder, control):
    expected = request.fingerprint or fingerprint(path)
    _check_source(path, expected)
    source = session.open_spreadsheet(path)
    try:
        app.Calculation = -4135
        app.CalculateBeforeSave = False
        _check_workbook(source)
        available = {str(source.Sheets.Item(i).Name) for i in range(1, source.Sheets.Count + 1)}
        if any(name not in available for name in request.sheets):
            raise SheetSelectionError("선택한 시트를 찾을 수 없습니다. 파일을 다시 선택해 주세요.")
        for index, name in enumerate(request.sheets):
            control.update(5 + 90 * index / len(request.sheets), f"시트 저장 중 · {name}")
            sheet = source.Sheets.Item(name)
            # A standalone workbook must contain a visible sheet, including a selected hidden sheet.
            if sheet.Visible != -1:
                if source.ProtectStructure:
                    raise SheetSelectionError(
                        "숨긴 시트를 나누려면 Excel에서 문서 구조 보호를 해제해 주세요."
                    )
                sheet.Visible = -1
            if request.values_only and sheet.Type == -4167:
                _sheet_values(sheet, control)
            sheet.Copy()
            output = app.ActiveWorkbook
            try:
                staged = folder / "sheet.xlsx"
                _save(output, staged, control)
                _check_source(path, expected)
                safe_name = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", name).rstrip(" .") or "시트"
                destination = path.with_name(f"{path.stem[:180]}_{safe_name}.xlsx")
                control.publish(staged, destination)
            finally:
                output.Close(False)
    finally:
        source.Close(False)
