import unittest,tempfile
from pathlib import Path
from PIL import Image
import fitz
from compression import compress_image,compress_pdf,RATIO_PROFILES
class RatioTests(unittest.TestCase):
 def test_exact_pixels_and_alpha(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);src=d/'alpha.png';Image.new('RGBA',(400,300),(50,100,200,100)).save(src)
   for key,settings in RATIO_PROFILES.items():
    out,ext,detail=compress_image(src,d,key,False,False,lambda:None,lambda f:None)
    with Image.open(out) as im:
     self.assertEqual(im.size,(round(400*settings['ratio']),round(300*settings['ratio'])))
     self.assertIn('A',im.getbands())
 def test_pdf_pixels_text_and_page_size(self):
  import io
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);src=d/'source.pdf';out=d/'out.pdf'
   data=io.BytesIO();Image.effect_noise((1000,800),100).save(data,'PNG')
   with fitz.open() as doc:
    page=doc.new_page();page.insert_text((20,20),'Retain text');page.insert_image(fitz.Rect(30,40,500,500),stream=data.getvalue());doc.save(src)
   compress_pdf(src,out,'p50',False,False,lambda:None,lambda f:None)
   with fitz.open(out) as doc:
    self.assertIn('Retain text',doc[0].get_text());self.assertEqual(doc[0].rect.width,595)
    self.assertEqual(doc[0].get_images()[0][2:4],(500,400))
