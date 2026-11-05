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

 def test_dwg_prefers_oda_then_falls_back_to_bundled_on_error(self):
  from unittest.mock import patch
  from bakuri.application.control import JobControl
  from bakuri.conversion.cad import CadError,read_dwg
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);oda=root/'ODAFileConverter.exe';bundled=root/'dwg2dxf.exe';bundled.touch()
   source=root/'drawing.dwg';control=JobControl();drawing=object()
   with patch('bakuri.conversion.cad.find_oda',return_value=oda),patch('bakuri.conversion.cad.bundled_converter',return_value=bundled),patch('bakuri.conversion.cad.convert_dwg_with',side_effect=[drawing,CadError('oda failed'),drawing]) as run:
    self.assertIs(read_dwg(source,control),drawing)
    run.assert_called_once_with(source,control,'ODA File Converter',oda)
    self.assertIs(read_dwg(source,control),drawing)
    self.assertEqual([call.args[2] for call in run.call_args_list],['ODA File Converter','ODA File Converter','LibreDWG'])
    self.assertIn('LibreDWG',control.notes[0])

 def test_cad_colored_lines_print_black_on_white(self):
  import ezdxf
  with tempfile.TemporaryDirectory() as folder:
   source=Path(folder)/'colors.dxf'
   doc=ezdxf.new();doc.modelspace().add_line((0,0),(80,50),dxfattribs={'color':1})
   doc.modelspace().add_line((0,50),(80,0),dxfattribs={'color':3})
   doc.modelspace().add_wipeout([(10,10),(20,10),(20,20),(10,20)])
   doc.saveas(source)
   with fitz.open(convert([source],'pdf')[0]) as pdf:
    strokes=[drawing['color'] for drawing in pdf[0].get_drawings() if drawing.get('color')]
    self.assertEqual(strokes,[(0.0,0.0,0.0)]*2)
    self.assertTrue(any(drawing.get('fill')==(1.0,1.0,1.0) for drawing in pdf[0].get_drawings()))
    self.assertEqual(pdf[0].get_pixmap().pixel(0,0),(255,255,255))

 def test_cad_pdf_is_compressed_and_keeps_vector_geometry(self):
  import ezdxf
  from ezdxf.addons.drawing import Frontend,RenderContext,layout,pymupdf
  with tempfile.TemporaryDirectory() as folder:
   source=Path(folder)/'detail.dxf'
   doc=ezdxf.new()
   for i in range(500):doc.modelspace().add_line((i,0),(i+1,250))
   doc.saveas(source)
   raw=pymupdf.PyMuPdfBackend()
   Frontend(RenderContext(doc),raw).draw_layout(doc.modelspace())
   baseline=raw.get_pdf_bytes(layout.Page(210,297,margins=layout.Margins.all(8)))
   result=Path(convert([source],'pdf',orientation='portrait')[0])
   self.assertLess(result.stat().st_size,len(baseline))
   with fitz.open(result) as pdf:
    self.assertGreater(pdf[0].rect.height,pdf[0].rect.width)
    self.assertEqual(sum(item[0]=='l' for drawing in pdf[0].get_drawings() for item in drawing['items']),500)

 def test_cad_explicit_and_inherited_lineweights_keep_their_widths(self):
  import ezdxf
  with tempfile.TemporaryDirectory() as folder:
   source=Path(folder)/'lineweights.dxf'
   doc=ezdxf.new()
   doc.layers.new('thin',dxfattribs={'lineweight':13})
   model=doc.modelspace()
   model.add_line((0,0),(100,0),dxfattribs={'lineweight':0})
   model.add_line((0,10),(100,10),dxfattribs={'layer':'thin'})
   model.add_line((0,20),(100,20),dxfattribs={'lineweight':35})
   model.add_line((0,30),(100,30))
   for display in (0,1):
    doc.header['$LWDISPLAY']=display
    doc.saveas(source)
    with fitz.open(convert([source],'pdf')[0]) as pdf:
     widths=[path['width'] for path in pdf[0].get_drawings() if path['type']=='s']
     self.assertEqual(len(widths),4)
     for width,mm in zip(widths,(0.01,0.13,0.35,0.25 if display else 0.05)):
      self.assertAlmostEqual(width,mm*72/25.4,places=5)

 def test_cad_text_with_missing_font_matches_installed_korean_font(self):
  import ezdxf
  from ezdxf.fonts import fonts
  manager=fonts.font_manager
  fallback=next((name for name in ('malgun.ttf','malgunbd.ttf','gulim.ttc','batang.ttc','NotoSansCJK-Regular.ttc') if manager.has_font(name)),None)
  if not fallback:self.skipTest('No Korean CAD fallback font installed')
  with tempfile.TemporaryDirectory() as folder:
   images=[]
   for index,font in enumerate(('missing-cad-font.shx',fallback)):
    source=Path(folder)/f'lettering-{index}.dxf'
    doc=ezdxf.new();doc.styles.new('CAD_TEXT',dxfattribs={'font':font})
    doc.modelspace().add_text('한글 치수',dxfattribs={'style':'CAD_TEXT','height':10})
    doc.saveas(source)
    result=convert([source],'pdf',orientation='landscape')[0]
    with fitz.open(result) as pdf:
     pix=pdf[0].get_pixmap()
     images.append(pix.samples)
   self.assertEqual(images[0],images[1])

 def test_inline_mtext_uses_korean_font_without_losing_layout_codes(self):
  import ezdxf
  from ezdxf.fonts import fonts
  manager=fonts.font_manager
  name=next((candidate for candidate in ('malgun.ttf','malgunbd.ttf','gulim.ttc','batang.ttc','NotoSansCJK-Regular.ttc') if manager.has_font(candidate)),None)
  if not name:self.skipTest('No Korean CAD fallback font installed')
  with tempfile.TemporaryDirectory() as folder:
   renders=[]
   for index,family in enumerate(('Missing CAD Font',manager.get_font_face(name).family)):
    source=Path(folder)/f'inline-{index}.dxf'
    doc=ezdxf.new()
    doc.modelspace().add_mtext(r'{\f'+family+r'|b0|i0;한글}\P치수',dxfattribs={'char_height':5,'width':40})
    doc.saveas(source)
    with fitz.open(convert([source],'pdf')[0]) as pdf:
     renders.append(pdf[0].get_pixmap().samples)
   self.assertEqual(renders[0],renders[1])


class ConversionDestinationTests(unittest.TestCase):
 def test_image_pdf_paper_orientation_and_output_folders(self):
  with tempfile.TemporaryDirectory() as folder:
   root=Path(folder);source=root/'source.jpg'
   Image.new('RGB',(80,40),'red').save(source)
   result=Path(convert([source],'pdf',orientation='portrait',output_mode='subfolder')[0])
   self.assertEqual(result.parent,root.resolve()/'바꾸리 변환')
   with fitz.open(result) as pdf:
    page=pdf[0]
    self.assertEqual(page.rect,fitz.paper_rect('a4'))
    image=page.get_images()[0]
    self.assertEqual(pdf.xref_stream_raw(image[0]),source.read_bytes())
   chosen=root/'custom'
   result=Path(convert([source],'pdf',orientation='landscape',output_mode='custom',output_folder=str(chosen))[0])
   self.assertEqual(result.parent,chosen.resolve())
   with fitz.open(result) as pdf:self.assertEqual(pdf[0].rect,fitz.paper_rect('a4-l'))
