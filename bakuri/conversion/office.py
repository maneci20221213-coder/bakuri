"""Office/Hancom COM resources stay on the calling worker thread."""

from pathlib import Path
import codecs, csv
import fitz
from image_inputs import stage_images, page_sizes, frames, save_png
from bakuri.domain.formats import WORDS, PRESENTATIONS, SPREADSHEETS


def text_import_options(src):
    with src.open("rb") as handle:
        sample = handle.read(65536)
    if sample.startswith((b"\xff\xfe", b"\xfe\xff")):
        encoding = "utf-16"
        origin = 1200
    else:
        try:
            codecs.getincrementaldecoder("utf-8-sig")().decode(sample, final=False)
            encoding = "utf-8-sig"
            origin = 65001
        except UnicodeDecodeError:
            encoding = "cp949"
            origin = 949
    text = sample.decode(encoding, errors="replace")
    if src.suffix.lower() == ".tsv":
        delimiter = "\t"
    else:
        try:
            delimiter = csv.Sniffer().sniff(text, delimiters=",;\t").delimiter
        except csv.Error:
            delimiter = ","
    return dict(
        Origin=origin,
        DataType=1,
        TextQualifier=1,
        ConsecutiveDelimiter=False,
        Tab=delimiter == "\t",
        Semicolon=delimiter == ";",
        Comma=delimiter == ",",
        Space=False,
        Other=False,
        Local=True,
    )


class OfficeSession:
    def __init__(self):
        self.apps = {}
        self.com = None
        self.control = None
        self.advance = lambda fraction, text: None

    def __enter__(self):
        return self

    def check(self):
        if self.control:
            self.control.check()

    def hwp(self):
        self.check()
        import pythoncom, win32com.client

        if self.com is None:
            pythoncom.CoInitialize()
            self.com = pythoncom
        app = self.apps.get("hwp")
        if app is None:
            app = win32com.client.DispatchEx("HWPFrame.HwpObject")
            self.apps["hwp"] = app
            from windows import register_hancom

            register_hancom(app)
        return app

    def image_document(self, paths, dest, folder, mode, progress):
        from hancom_images import create_document, compact_document

        entries = stage_images(
            paths,
            folder,
            progress,
            checkpoint=self.check,
            advance=lambda fraction: self.advance(0.35 * fraction, "이미지 준비"),
        )
        self.check()
        pdf_pages = any(Path(p).suffix.lower() == ".pdf" for p in paths)
        create_document(
            self.hwp(),
            entries,
            dest,
            "inline" if pdf_pages else mode,
            progress,
            checkpoint=self.check,
            advance=lambda fraction: self.advance(0.35 + 0.6 * fraction, "한글 그림 넣기"),
        )
        if pdf_pages:
            self.check()
            from pdf_pages import paginate

            paginate(dest, entries, page_sizes(paths))
            self.check()
        compact_document(dest, self.check)

    def powerpoint(self):
        self.check()
        import pythoncom, win32com.client

        if self.com is None:
            pythoncom.CoInitialize()
            self.com = pythoncom
        if "powerpoint" not in self.apps:
            app = win32com.client.DispatchEx("PowerPoint.Application")
            self.apps["powerpoint"] = app
            app.AutomationSecurity = 3
            app.DisplayAlerts = 1
        return self.apps["powerpoint"]

    def slides_document(self, paths, dest, folder, dpi=150):
        book = self.powerpoint().Presentations.Add(WithWindow=False)
        try:
            count = 0
            for source in paths:
                self.check()
                if source.suffix.lower() == ".pdf":
                    with fitz.open(source) as document:
                        if document.needs_pass:
                            raise ValueError("암호가 있는 PDF는 지원하지 않습니다.")
                        for page in document:
                            self.check()
                            image = folder / f"slide-{count}.png"
                            page.get_pixmap(dpi=dpi, alpha=False).save(str(image))
                            self.add_slide(book, image, page.rect.width, page.rect.height, count)
                            count += 1
                else:
                    for image in frames(source):
                        self.check()
                        path = folder / f"slide-{count}.png"
                        save_png(image, path, source)
                        self.add_slide(book, path, image.width, image.height, count)
                        count += 1
            self.check()
            if not count:
                raise ValueError("슬라이드로 만들 페이지가 없습니다.")
            book.SaveAs(str(dest), 24)
            self.check()
            if not dest.exists():
                raise RuntimeError("PPTX 저장에 실패했습니다.")
        finally:
            book.Close()

    def add_slide(self, book, image, width, height, index):
        if index == 0:
            book.PageSetup.SlideWidth = 720
            book.PageSetup.SlideHeight = max(72, min(4032, 720 * height / width))
        sw = float(book.PageSetup.SlideWidth)
        sh = float(book.PageSetup.SlideHeight)
        scale = min(sw / width, sh / height)
        w = width * scale
        h = height * scale
        slide = book.Slides.Add(index + 1, 12)
        slide.Shapes.AddPicture(str(image), False, True, (sw - w) / 2, (sh - h) / 2, w, h)
        self.check()

    def word(self):
        self.check()
        import pythoncom, win32com.client

        if self.com is None:
            pythoncom.CoInitialize()
            self.com = pythoncom
        app = self.apps.get("word")
        if app is None:
            app = win32com.client.DispatchEx("Word.Application")
            self.apps["word"] = app
            app.Visible = False
            app.DisplayAlerts = 0
            app.AutomationSecurity = 3
        return app

    def excel(self):
        self.check()
        import pythoncom, win32com.client

        if self.com is None:
            pythoncom.CoInitialize()
            self.com = pythoncom
        if "excel" not in self.apps:
            app = win32com.client.DispatchEx("Excel.Application")
            self.apps["excel"] = app
            app.Visible = False
            app.DisplayAlerts = False
            app.AutomationSecurity = 3
            app.EnableEvents = False
            app.AskToUpdateLinks = False
        return self.apps["excel"]

    def open_spreadsheet(self, source):
        app = self.excel()
        if source.suffix.lower() in {".csv", ".tsv"}:
            app.Workbooks.OpenText(str(source), **text_import_options(source))
            return app.ActiveWorkbook
        return app.Workbooks.Open(
            str(source),
            UpdateLinks=0,
            ReadOnly=True,
            IgnoreReadOnlyRecommended=True,
            Password="",
            WriteResPassword="",
            Notify=False,
        )

    def word_document(self, source, dest, folder, dpi):
        """Embed each PDF page or image on its own Word page."""
        book = self.word().Documents.Add()
        try:
            if source.suffix.lower() == ".pdf":
                with fitz.open(source) as document:
                    if document.needs_pass:
                        raise ValueError("암호가 있는 PDF는 지원하지 않습니다.")
                    if not len(document):
                        raise ValueError("페이지가 없는 PDF입니다.")
                    image = folder / "word-page.png"
                    for index, page in enumerate(document):
                        self.check()
                        page.get_pixmap(dpi=dpi, alpha=False).save(str(image))
                        self.add_word_page(book, image, page.rect.width, page.rect.height, index)
                        self.advance(0.9 * (index + 1) / len(document), "Word에 PDF 페이지 넣기")
            else:
                entries = stage_images([source], folder, checkpoint=self.check)
                for index, (image, width, height) in enumerate(entries):
                    paper = fitz.paper_rect("a4-l" if width > height else "a4")
                    self.add_word_page(book, image, width, height, index, paper=paper)
                    self.advance(0.9 * (index + 1) / len(entries), "Word에 이미지 넣기")
            self.check()
            book.SaveAs2(str(dest), FileFormat=12)  # wdFormatXMLDocument
            self.check()
            if not dest.is_file():
                raise RuntimeError("Word 저장에 실패했습니다.")
        finally:
            book.Close(False)

    def add_word_page(self, book, image, width, height, index, *, paper=None):
        self.check()
        if index:
            end = book.Content.End - 1
            book.Range(end, end).InsertBreak(2)  # wdSectionBreakNextPage
        setup = book.Sections.Last.PageSetup
        page_width, page_height = (
            (paper.width, paper.height) if paper is not None else (width, height)
        )
        scale = min(1, 1584 / max(page_width, page_height))  # Word's 22-inch page limit
        page_width, page_height = max(72, page_width * scale), max(72, page_height * scale)
        setup.Orientation = int(page_width > page_height)
        setup.Gutter = 0
        setup.TopMargin = setup.BottomMargin = setup.LeftMargin = setup.RightMargin = 12
        setup.PageWidth = page_width
        setup.PageHeight = page_height

        end = book.Content.End - 1
        target = book.Range(end, end)
        paragraph = target.ParagraphFormat
        paragraph.Alignment = 1  # Center horizontally
        paragraph.SpaceBefore = paragraph.SpaceAfter = 0
        paragraph.LineSpacingRule = 0  # Single spacing leaves room for the inline image
        paragraph.PageBreakBefore = False
        picture = book.InlineShapes.AddPicture(str(image), False, True, target)
        fit = min((page_width - 24) / width, (page_height - 36) / height)
        picture.LockAspectRatio = 0
        picture.Width = width * fit
        picture.Height = height * fit
        self.check()

    def export(self, src, dest, fmt):
        self.check()
        import pythoncom, win32com.client

        if self.com is None:
            pythoncom.CoInitialize()
            self.com = pythoncom
        if src.suffix.lower() in PRESENTATIONS:
            book = self.powerpoint().Presentations.Open(
                str(src), ReadOnly=True, Untitled=False, WithWindow=False
            )
            try:
                self.check()
                book.SaveAs(str(dest), 32)
                self.check()
                if not dest.exists():
                    raise RuntimeError("PowerPoint PDF 저장에 실패했습니다.")
            finally:
                book.Close()
            return
        word_pdf = src.suffix.lower() in WORDS and fmt.upper() == "PDF"
        odt_docx = src.suffix.lower() == ".odt" and fmt.upper() == "DOCX"
        if word_pdf or odt_docx:
            app = self.word()
            book = app.Documents.Open(str(src), ReadOnly=True, AddToRecentFiles=False)
            try:
                self.check()
                if word_pdf:
                    book.ExportAsFixedFormat(str(dest), 17)
                else:
                    book.SaveAs2(str(dest), FileFormat=12)  # wdFormatXMLDocument
                self.check()
                if not dest.exists():
                    raise RuntimeError("Word 저장에 실패했습니다.")
            finally:
                book.Close(False)
            return
        excel = src.suffix.lower() in SPREADSHEETS
        app = self.excel() if excel else self.apps.get("hwp")
        if app is None:
            app = win32com.client.DispatchEx("HWPFrame.HwpObject")
            self.apps["hwp"] = app
            from windows import register_hancom

            register_hancom(app)
        book = None
        try:
            if excel:
                book = self.open_spreadsheet(src)
                self.check()
                if fmt.upper() == "XLSX":
                    book.SaveAs(str(dest), FileFormat=51)
                else:
                    book.ExportAsFixedFormat(0, str(dest), 0, True, False)
            else:
                if not app.Open(str(src), "", ""):
                    raise RuntimeError("한글 문서 열기에 실패했습니다.")
                self.check()
                if not app.SaveAs(str(dest), "OOXML" if fmt.upper() == "DOCX" else fmt.upper(), ""):
                    raise RuntimeError("한글 저장에 실패했습니다.")
            self.check()
            if not dest.exists():
                raise RuntimeError("변환 결과가 생성되지 않았습니다.")
        finally:
            if book is not None:
                book.Close(False)
            if not excel:
                app.Clear(1)

    def __exit__(self, *args):
        for app in self.apps.values():
            try:
                app.Quit()
            except Exception:
                pass
        self.apps.clear()
        if self.com is not None:
            self.com.CoUninitialize()


def office(src, dest, fmt):
    with OfficeSession() as session:
        session.export(src, dest, fmt)
