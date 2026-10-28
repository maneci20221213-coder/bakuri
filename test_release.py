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
 def test_tray_white_arrows_are_transparent(self):
  from theme import icon,ASSETS
  from PySide6.QtGui import QImage
  original=QImage(str(ASSETS/'app.png'));tray=icon('tray').pixmap(original.size()).toImage()
  whites=blues=0
  for y in range(original.height()):
   for x in range(original.width()):
    a=original.pixelColor(x,y);b=tray.pixelColor(x,y)
    if a.alpha()>250 and min(a.red(),a.green(),a.blue())>250:
     whites+=1;self.assertLess(b.alpha(),8)
    if a.alpha()>250 and a.red()<60 and a.blue()>180:
     blues+=1;self.assertGreater(b.alpha(),220)
  self.assertGreater(whites,1000);self.assertGreater(blues,1000)
