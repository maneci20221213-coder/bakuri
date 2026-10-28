import unittest,tempfile
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
