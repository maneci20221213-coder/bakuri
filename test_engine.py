import unittest,tempfile
from pathlib import Path
from PIL import Image
import fitz
from engine import convert
class EngineTests(unittest.TestCase):
 def test_pipeline(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d); a=d/'a.png'; b=d/'b.png'
   Image.new('RGB',(40,30),'red').save(a); Image.new('RGB',(40,30),'blue').save(b)
   original=a.read_bytes(); out=convert([b,a],'pdf',True)
   with fitz.open(out[0]) as pdf:
    self.assertEqual(len(pdf),2)
    pix=pdf[0].get_pixmap(); self.assertGreater(pix.pixel(5,5)[2],200)
   images=convert(out,'png'); self.assertEqual(len(images),2)
   result=convert([a],'png'); self.assertNotEqual(str(a),result[0]); self.assertEqual(original,a.read_bytes())
   transparent=d/'transparent.png'; Image.new('RGBA',(10,10),(0,0,0,0)).save(transparent)
   jpg=convert([transparent],'jpg')[0]
   with Image.open(jpg) as im: self.assertEqual(im.getpixel((0,0)),(255,255,255))
 def test_reject(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'a.png'; Image.new('RGB',(2,2)).save(p)
   with self.assertRaises(ValueError): convert([p],'xlsx')
   with self.assertRaises(ValueError): convert([p],'png',True)
if __name__=='__main__': unittest.main()

class FileNameTests(unittest.TestCase):
 def test_single_page_keeps_stem(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'보고서.pdf'
   with fitz.open() as doc:
    doc.new_page(); doc.save(p)
   self.assertEqual(Path(convert([p],'png')[0]).name,'보고서.png')
   self.assertEqual(Path(convert([p],'png')[0]).name,'보고서_1.png')
