import unittest,tempfile,types,sys
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import fitz
from engine import convert

class RecentEngineTests(unittest.TestCase):
 def test_dpi_and_image_dimensions(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);pdf=d/'page.pdf'
   with fitz.open() as doc:doc.new_page(width=96,height=96);doc.save(pdf)
   out=convert([pdf],'png',dpi=300)[0]
   with Image.open(out) as im:self.assertEqual(im.size,(400,400))
   source=d/'image.png';Image.new('RGB',(731,529),'red').save(source)
   out=convert([source],'jpg')[0]
   with Image.open(out) as im:self.assertEqual(im.size,(731,529))
 def test_office_reused_and_closed(self):
  calls=[]
  class App:
   def Open(self,*args):calls.append('open');return True
   def SaveAs(self,path,*args):Path(path).write_bytes(b'converted');return True
   def Clear(self,*args):calls.append('clear')
   def Quit(self):calls.append('quit')
  com=types.ModuleType('pythoncom');com.CoInitialize=lambda:calls.append('init');com.CoUninitialize=lambda:calls.append('uninit')
  client=types.ModuleType('win32com.client');client.DispatchEx=lambda name:(calls.append('start') or App())
  package=types.ModuleType('win32com');package.client=client
  windows=types.ModuleType('windows');windows.register_hancom=lambda app:True
  with patch.dict(sys.modules,{'pythoncom':com,'win32com':package,'win32com.client':client,'windows':windows}),tempfile.TemporaryDirectory() as d:
   paths=[]
   for name in ['one.odt','two.odt']:
    p=Path(d)/name;p.write_bytes(b'input');paths.append(p)
   self.assertEqual(len(convert(paths,'hwpx')),2)
  self.assertEqual(calls.count('start'),1);self.assertEqual(calls.count('clear'),2);self.assertEqual(calls.count('quit'),1);self.assertEqual(calls[-1],'uninit')

class HwpTests(unittest.TestCase):
 def test_hwp_routes_to_hancom(self):
  import engine
  with tempfile.TemporaryDirectory() as d:
   source=Path(d)/'legacy.hwp';source.write_bytes(bytes.fromhex('d0cf11e0a1b11ae1'))
   def export(session,src,target,fmt): self.assertEqual(src.suffix,'.hwp');target.write_bytes(b'pdf result')
   with patch.object(engine.OfficeSession,'export',export): result=convert([source],'pdf')
   self.assertEqual(Path(result[0]).suffix,'.pdf');self.assertEqual(source.read_bytes(),bytes.fromhex('d0cf11e0a1b11ae1'))
