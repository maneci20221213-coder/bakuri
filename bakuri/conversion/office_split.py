"""Split the editable body at page boundaries reported by the installed editor."""

from contextlib import closing
from itertools import pairwise
from pathlib import Path
from shutil import copyfile
from tempfile import TemporaryDirectory

from bakuri.conversion.office import OfficeSession
from bakuri.domain.formats import HANCOM, WORDS
from bakuri.domain.pdf_selection import PageSelectionError, page_groups, page_output_path


def _runs(group):
    start = group[0]
    for previous, page in pairwise(group):
        if page != previous + 1:
            yield start, previous + 1
            start = page
    yield start, group[-1] + 1


def _check_span(start, end):
    if start >= end:
        raise PageSelectionError("선택한 쪽의 본문 경계를 구분할 수 없습니다. 범위를 바꿔 주세요.")


class _WordPages:
    def __init__(self, app, source):
        self.app = app
        self.book = app.Documents.Open(str(source), ReadOnly=True, AddToRecentFiles=False)

    def close(self):
        self.book.Close(False)

    def count(self):
        self.book.Repaginate()
        return self.book.ComputeStatistics(2)  # wdStatisticPages

    def position(self, index, count):
        if index == count:
            return self.book.Content.End
        if index == 0:
            return self.book.Content.Start
        return self.book.GoTo(What=1, Which=1, Count=index + 1).Start  # absolute page

    def save(self, source, dest, spans, control):
        copyfile(source, dest)
        book = self.app.Documents.Open(str(dest), ReadOnly=False, AddToRecentFiles=False)
        try:
            start, end = spans[0]
            end = self._trim_page_break(start, end)
            if end < book.Content.End:
                book.Range(end, book.Content.End - 1).Delete()
            if start > book.Content.Start:
                book.Range(book.Content.Start, start).Delete()
            for start, end in spans[1:]:
                control.check()
                end = self._trim_page_break(start, end)
                position = book.Content.End - 1
                book.Range(position, position).InsertBreak(7)  # wdPageBreak
                position = book.Content.End - 1
                book.Range(position, position).FormattedText = self.book.Range(
                    start, end
                ).FormattedText
            control.check()
            book.Save()
        finally:
            book.Close(False)

    def _trim_page_break(self, start, end):
        if (
            end < self.book.Content.End
            and end > start
            and self.book.Range(end - 1, end).Text == "\f"
        ):
            return end - 1
        return end


class _HancomPages:
    def __init__(self, app, source):
        self.app = app
        self.source = source
        self.source_open = False
        self.open()

    def open(self):
        if not self.app.Open(str(self.source), "", ""):
            raise PageSelectionError(
                "한글 문서를 열 수 없습니다. 한글에서 문서를 먼저 확인해 주세요."
            )
        self.source_open = True

    def close(self):
        self.app.Clear(1)
        self.source_open = False

    def count(self):
        return self.app.PageCount

    def position(self, index, count):
        app = self.app
        if index in {0, count}:
            action = "MoveDocBegin" if index == 0 else "MoveDocEnd"
            moved = app.HAction.Run(action)
        else:
            params = app.HParameterSet.HGotoE
            app.HAction.GetDefault("Goto", params.HSet)
            params.SetSelectionIndex = 1  # page
            params.HSet.SetItem("DialogResult", index + 1)
            app.HAction.Execute("Goto", params.HSet)
            info = app.XHwpDocuments.Active_XHwpDocument.XHwpDocumentInfo
            current = info.CurrentPage
            while current != index:
                action = "MovePageDown" if current < index else "MovePageUp"
                app.HAction.Run(action)
                next_page = info.CurrentPage
                if abs(index - next_page) >= abs(index - current):
                    raise PageSelectionError("선택한 쪽의 한글 본문 경계를 찾을 수 없습니다.")
                current = next_page
            app.HAction.Run("MovePageBegin")
            moved = info.CurrentPage == index
        position = tuple(app.GetPos())
        if moved is False or position[0] != 0:
            raise PageSelectionError("선택한 쪽의 한글 본문 경계를 찾을 수 없습니다.")
        return position[1:]

    def save(self, source, dest, spans, control):
        if not self.source_open:
            self.open()
        app = self.app
        blocks = []
        for start, end in spans:
            control.check()
            if not app.SetPos(0, 0, 0) or not app.SelectText(*start, *end):
                raise PageSelectionError("선택한 한글 본문 범위를 복사할 수 없습니다.")
            block = app.GetTextFile("HWP", "saveblock")
            if not block:
                raise PageSelectionError("선택한 한글 본문 범위를 복사할 수 없습니다.")
            blocks.append(block)
        self.close()
        try:
            for index, block in enumerate(blocks):
                control.check()
                if index:
                    app.HAction.Run("MoveDocEnd")
                    if app.HAction.Run("BreakPage") is False:
                        raise PageSelectionError("추출한 한글 문서에 쪽을 추가할 수 없습니다.")
                if not app.SetTextFile(block, "HWP", "insertfile" if index else ""):
                    raise PageSelectionError("추출한 한글 본문을 새 문서에 넣을 수 없습니다.")
            control.check()
            if not app.SaveAs(str(dest), source.suffix[1:].upper(), ""):
                raise PageSelectionError("추출한 한글 문서를 저장할 수 없습니다.")
        finally:
            self.close()


def split_office(source, mode, every, selection, separate, control):
    source = Path(source).resolve()
    suffix = source.suffix.lower()
    if suffix not in HANCOM | WORDS:
        raise PageSelectionError("한글 또는 Word 문서를 선택해 주세요.")
    control.update(0, "문서 페이지 확인 중")
    with TemporaryDirectory() as directory, OfficeSession() as session:
        session.control = control
        folder = Path(directory)
        original = folder / f"original{suffix}"
        copyfile(source, original)
        if suffix in HANCOM:
            editor = _HancomPages(session.hwp(), original)
        else:
            editor = _WordPages(session.word(), original)
        with closing(editor):
            count = editor.count()
            groups = page_groups(count, mode, every, selection, separate)
            runs = [tuple(_runs(group)) for group in groups]
            boundaries = sorted({point for group in runs for span in group for point in span})
            positions = {}
            for index, page in enumerate(boundaries):
                control.update(30 * index / len(boundaries), "문서 페이지 경계 확인 중")
                positions[page] = editor.position(page, count)
            for previous, page in pairwise(boundaries):
                _check_span(positions[previous], positions[page])
            for index, (group, spans) in enumerate(zip(groups, runs)):
                control.update(
                    30 + 68 * index / len(groups), f"문서 저장 중 · {index + 1}/{len(groups)}"
                )
                dest = folder / f"part-{index}{suffix}"
                if spans == ((0, count),):
                    copyfile(original, dest)
                else:
                    editor.save(
                        original, dest, [(positions[a], positions[b]) for a, b in spans], control
                    )
                target = page_output_path(source, count, group, mode == "extract" and not separate)
                control.publish(dest, target)
    control.complete()
    return list(control.outputs)
