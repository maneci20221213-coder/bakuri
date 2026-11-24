import unittest,tempfile,types
from pathlib import Path
from unittest.mock import Mock,patch
from PIL import Image
import fitz
from engine import OfficeSession,can_convert,convert
class DocumentSlideTests(unittest.TestCase):
 def test_routes(self):
  for ext in ['doc','docx']:
   for fmt in ['hwpx','pdf','png','jpeg']:self.assertTrue(can_convert('a.'+ext,fmt))
  for ext in ['hwp','hwpx']:self.assertTrue(can_convert('a.'+ext,'docx'))
  for ext in ['ppt','pptx']:
   for fmt in ['pdf','png','jpeg']:self.assertTrue(can_convert('a.'+ext,fmt))
   self.assertFalse(can_convert('a.'+ext,'docx'))
  self.assertFalse(can_convert('a.docx','pptx'))
 def test_slides_order_ratio_and_embedding(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);a=d/'a.png';Image.new('RGB',(400,200)).save(a)
   pdf=d/'a.pdf'
   with fitz.open() as doc:
    doc.new_page(width=200,height=400);doc.new_page(width=300,height=300);doc.save(pdf)
   book=Mock();book.PageSetup.SlideWidth=720;book.PageSetup.SlideHeight=360
   pics=[];book.Slides.Add.return_value.Shapes.AddPicture.side_effect=lambda *args:pics.append(args)
   book.SaveAs.side_effect=lambda name,fmt:Path(name).write_bytes(b'pptx')
   session=OfficeSession();app=Mock();app.Presentations.Add.return_value=book
   with patch.object(session,'powerpoint',return_value=app):session.slides_document([a,pdf],d/'out.pptx',d)
   self.assertEqual(len(pics),3)
   self.assertTrue(all(p[1:3]==(False,True) for p in pics))
   self.assertEqual(pics[0][-2:],(720,360))
   self.assertEqual(pics[1][-2:],(180,360))
   book.Close.assert_called_once()
 def test_cancel_closes_presentation(self):
  session=OfficeSession();book=Mock();app=Mock();app.Presentations.Add.return_value=book
  with patch.object(session,'powerpoint',return_value=app),patch.object(session,'check',side_effect=RuntimeError('stop')):
   with self.assertRaises(RuntimeError):session.slides_document([Path('a.png')],Path('x.pptx'),Path('.'))
  book.Close.assert_called_once()


class WordConversionTests(unittest.TestCase):
    def test_odt_is_opened_by_word_and_saved_as_editable_docx(self):
        app = Mock()
        book = app.Documents.Open.return_value
        book.SaveAs2.side_effect = lambda name, **kwargs: Path(name).write_bytes(b"docx")
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.odt"
            source.write_bytes(b"odt")
            modules = {
                "pythoncom": Mock(),
                "win32com": types.ModuleType("win32com"),
                "win32com.client": Mock(),
            }
            with (
                patch.dict("sys.modules", modules),
                patch.object(OfficeSession, "word", return_value=app),
            ):
                (output,) = convert([source], "docx")
            self.assertEqual(Path(output).read_bytes(), b"docx")
            self.assertEqual(source.read_bytes(), b"odt")
            app.Documents.Open.assert_called_once_with(
                str(source.resolve()), ReadOnly=True, AddToRecentFiles=False
            )
            self.assertEqual(book.SaveAs2.call_args.kwargs, {"FileFormat": 12})
            book.Close.assert_called_once_with(False)

    def test_pdf_and_images_embed_one_picture_per_word_page(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            pdf, photo = root / "mixed.pdf", root / "photo.png"
            with fitz.open() as doc:
                doc.new_page(width=200, height=400)
                doc.new_page(width=450, height=250)
                doc.save(pdf)
            Image.new("RGBA", (400, 200), (0, 0, 255, 180)).save(photo)
            app = Mock()
            pdf_book, photo_book = Mock(), Mock()
            app.Documents.Add.side_effect = [pdf_book, photo_book]
            pages = []
            for book in (pdf_book, photo_book):
                book.Content.End = 1
                book.SaveAs2.side_effect = lambda name, **kwargs: Path(name).write_bytes(b"docx")

                def add_picture(path, link, embed, target, book=book):
                    setup = book.Sections.Last.PageSetup
                    with Image.open(path) as image:
                        pages.append(
                            (setup.Orientation, setup.PageWidth, setup.PageHeight, image.size)
                        )
                    self.assertEqual((link, embed), (False, True))
                    return Mock()

                book.InlineShapes.AddPicture.side_effect = add_picture

            with patch.object(OfficeSession, "word", return_value=app):
                outputs = convert([pdf, photo], "docx", dpi=72)
            self.assertEqual([Path(path).name for path in outputs], ["mixed.docx", "photo.docx"])
            self.assertEqual(
                pages,
                [(0, 200, 400, (200, 400)), (1, 450, 250, (450, 250)), (1, 842, 595, (400, 200))],
            )
            pdf_book.Range.return_value.InsertBreak.assert_called_once_with(2)
            photo_book.Range.return_value.InsertBreak.assert_not_called()
            pdf_book.Close.assert_called_once_with(False)
            photo_book.Close.assert_called_once_with(False)
