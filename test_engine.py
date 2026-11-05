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


class CadConversionTests(unittest.TestCase):
 def test_dxf_to_vector_pdf_and_images(self):
  import ezdxf,fitz
  from bakuri.conversion.service import convert
  with tempfile.TemporaryDirectory() as folder:
   source=Path(folder)/'drawing.dxf'
   doc=ezdxf.new();model=doc.modelspace()
   model.add_line((0,0),(100,50));model.add_circle((40,25),10)
   doc.saveas(source)
   original=source.read_bytes()
   for output in ('pdf','png','jpeg'):
    result=Path(convert([source],output)[0])
    self.assertEqual(result.suffix,'.'+output)
    if output=='pdf':
     with fitz.open(result) as pdf:
      self.assertEqual(len(pdf),1)
      self.assertTrue(any(drawing.get('color') for drawing in pdf[0].get_drawings()))
    else:
     with Image.open(result) as image:
      self.assertGreater(image.width,image.height)
   self.assertEqual(source.read_bytes(),original)

 def test_dwg_uses_installed_oda_then_renders_dxf(self):
  from unittest.mock import Mock,patch
  import ezdxf,os
  from bakuri.conversion.cad import find_oda
  from bakuri.conversion.service import convert
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder)
   exe=root/'Open Design Alliance'/'ODAFileConverter 26'/'ODAFileConverter.exe'
   exe.parent.mkdir(parents=True);exe.touch()
   source=root/'source.dwg';source.write_bytes(b'dwg fixture')
   def start(args,**kwargs):
    self.assertEqual(Path(args[0]),exe)
    self.assertEqual(Path(args[1],'drawing.dwg').read_bytes(),source.read_bytes())
    doc=ezdxf.new();doc.modelspace().add_line((0,0),(10,20))
    doc.saveas(Path(args[2],'drawing.dxf'))
    process=Mock(returncode=0);process.poll.return_value=0
    process.__enter__=Mock(return_value=process);process.__exit__=Mock(return_value=False)
    return process
   with patch.dict(os.environ,{'ProgramFiles':str(root),'ProgramW6432':'','ProgramFiles(x86)':''}),patch('bakuri.conversion.cad.subprocess.Popen',side_effect=start):
    self.assertEqual(find_oda(),exe)
    self.assertTrue(Path(convert([source],'pdf')[0]).is_file())
