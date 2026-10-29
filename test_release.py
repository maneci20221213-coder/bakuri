import unittest,tempfile,zipfile,io
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from image_inputs import stage_images
from hancom_images import compact_document
from engine import convert,OfficeSession

class ImageSizeTests(unittest.TestCase):
 def test_original_jpeg_and_png_payloads(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);folder=d/'stage';folder.mkdir()
   for ext,mode in [('jpeg','RGB'),('png','RGBA')]:
    src=d/('photo.'+ext);Image.effect_noise((1200,900),60).convert(mode).save(src)
    before=src.read_bytes();entries=stage_images([src],folder)
    self.assertEqual(entries[0][0].read_bytes(),before)
    self.assertEqual(entries[0][1:],(1200,900));self.assertEqual(src.read_bytes(),before)
 def test_exif_orientation_normalized(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);src=d/'rotate.jpg';exif=Image.Exif();exif[274]=6
   Image.new('RGB',(120,60),'red').save(src,exif=exif)
   entry=stage_images([src],d)[0];self.assertEqual(entry[1:],(60,120))
 def test_hwpx_repack_preserves_all_content(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'a.hwpx';files={'mimetype':b'application/hwp+zip','Contents/section0.xml':b'<section/>'*1000,'BinData/a.png':b'image'*3000}
   with zipfile.ZipFile(p,'w') as z:
    for k,v in files.items():z.writestr(k,v)
   before=p.stat().st_size;compact_document(p)
   self.assertLess(p.stat().st_size,before)
   with zipfile.ZipFile(p) as z:
    self.assertEqual({n:z.read(n) for n in z.namelist()},files)
    self.assertEqual(z.getinfo('mimetype').compress_type,zipfile.ZIP_STORED)

import os
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from app import Window
application=QApplication.instance() or QApplication([])
class ReleaseUiTests(unittest.TestCase):
 def setUp(self):self.w=Window()
 def tearDown(self):self.w.tray.hide();self.w.deleteLater()
 def test_popup_merge_routing(self):
  w=self.w
  for paths,fmt,expected in [(['a.png','b.jpg'],'pdf',True),(['a.png','b.jpg'],'hwpx',True),(['a.pdf','b.pdf'],'hwpx',True),(['a.png','b.pdf'],'hwpx',True),(['a.png'],'hwpx',False),(['a.png','b.jpg'],'jpeg',False),(['a.doc','b.doc'],'pdf',False)]:
   w.quick_paths=paths
   with patch.object(w,'start_conversion') as start:
    w.quick_selected(fmt);self.assertEqual(start.call_args.args[:3],(paths,fmt,expected))
 def test_formats_follow_checked_input_intersection(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);png=d/'a.png';word=d/'a.docx';Image.new('RGB',(10,10)).save(png);word.write_bytes(b'docx')
   w=self.w;w.files.add_paths([str(png)])
   def enabled(name):return w.fmt.model().item(w.fmt.findText(name)).isEnabled()
   self.assertFalse(enabled('DOCX'));self.assertFalse(enabled('XLSX'));self.assertTrue(enabled('HWPX'));self.assertTrue(enabled('PPTX'))
   w.fmt.setCurrentText('PPTX');w.files.add_paths([str(word)])
   self.assertFalse(enabled('PPTX'));self.assertFalse(enabled('용량 축소'));self.assertEqual(w.fmt.currentText(),'PDF')
   self.assertEqual(w.fmt.model().item(w.fmt.findText('PPTX')).foreground().color().name(),'#a4afbd')
   w.files.item(1).setCheckState(0,Qt.Unchecked);self.assertTrue(enabled('PPTX'))
   w.files.clear();self.assertTrue(all(w.fmt.model().item(i).isEnabled() for i in range(w.fmt.count())))
 def test_cycle_icon_has_transparent_background_and_counters(self):
  from theme import ASSETS
  from PIL import Image,ImageChops
  with Image.open(ASSETS/'app.png') as original,Image.open(ASSETS/'tray.png') as tray:
   self.assertIsNone(ImageChops.difference(original,tray).getbbox())
   for x,y in [(80,55),(102,118),(0,0)]:
    self.assertEqual(original.getpixel((round(x*1024/160),round(y*1024/160)))[3],0)
   self.assertEqual(original.getpixel((round(53*1024/160),round(30*1024/160))),(46,131,242,255))
   colors={color[:3] for count,color in original.getcolors(1024*1024) if color[3]==255}
   self.assertTrue({(46,131,242),(69,206,244)}<=colors)
   self.assertFalse(any(min(c)>245 for c in colors))
