import io,tempfile,unittest,zipfile
from pathlib import Path
import xml.etree.ElementTree as E
from PIL import Image,ImageDraw
import fitz
from engine import convert
from image_inputs import page_sizes
from pdf_pages import HP,q,paginate
from test_pdf_pages import realistic_package

class PngSizeRegressionTests(unittest.TestCase):
 def test_pdf_is_deflated_without_pixel_or_alpha_loss(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d)
   for mode,color in [('RGB',(20,80,180)),('RGBA',(20,80,180,100))]:
    src=d/f'{mode}.png';image=Image.new(mode,(1200,1600),color)
    ImageDraw.Draw(image).rectangle((100,200,900,1000),fill=(240,220,40) if mode=='RGB' else (240,220,40,200))
    image.save(src,optimize=True);original=src.read_bytes()
    # Reproduce the old raw PDF path as a size baseline.
    with fitz.open() as raw:
     page=raw.new_page(width=576,height=768);page.insert_image(page.rect,filename=str(src));baseline=raw.tobytes()
    out=Path(convert([src],'pdf')[0])
    self.assertLess(out.stat().st_size,len(baseline)//20)
    with fitz.open(stream=baseline,filetype='pdf') as old,fitz.open(out) as new:
     self.assertEqual(new[0].get_pixmap().samples,old[0].get_pixmap().samples)
     xref=new[0].get_images()[0][0];self.assertIn('FlateDecode',new.xref_object(xref))
    self.assertEqual(src.read_bytes(),original)
 def test_same_png_never_grows_and_preserves_palette_transparency(self):
  with tempfile.TemporaryDirectory() as d:
   src=Path(d)/'palette.png';im=Image.new('P',(800,600),0);im.putpalette([20,80,180,240,220,40]+[0]*762)
   ImageDraw.Draw(im).rectangle((20,20,500,400),fill=1);im.save(src,optimize=True,transparency=0)
   out=Path(convert([src],'png')[0]);self.assertLessEqual(out.stat().st_size,src.stat().st_size)
   with Image.open(src) as a,Image.open(out) as b:self.assertEqual(a.convert('RGBA').tobytes(),b.convert('RGBA').tobytes())
 def test_merged_png_pdf_keeps_compression(self):
  with tempfile.TemporaryDirectory() as d:
   paths=[Path(d)/f'{i}.png' for i in range(2)]
   for path in paths:Image.new('RGB',(1200,1600),'white').save(path)
   out=Path(convert(paths,'pdf',True)[0]);self.assertLess(out.stat().st_size,60000)
   with fitz.open(out) as pdf:self.assertEqual(len(pdf),2)

class FullPaperRegressionTests(unittest.TestCase):
 def test_displayed_crop_and_rotation_sizes_use_pdf_points(self):
  with tempfile.TemporaryDirectory() as d:
   src=Path(d)/'long.pdf'
   with fitz.open() as pdf:
    pdf.new_page(width=200,height=1000)
    page=pdf.new_page(width=900,height=700);page.set_cropbox(fitz.Rect(50,50,850,650));page.set_rotation(90)
    pdf.save(src)
   self.assertEqual(page_sizes([src]),[(20000,100000),(60000,80000)])
 def test_tall_landscape_and_square_have_zero_margin_paper_sized_pictures(self):
  with tempfile.TemporaryDirectory() as d:
   dest=Path(d)/'pages.hwpx';sizes=[(20000,100000),(90000,30000),(40000,40000)]
   realistic_package(dest,[(None,1,1)]*3)
   with zipfile.ZipFile(dest) as z:files={n:z.read(n) for n in z.namelist()}
   section=E.fromstring(files['Contents/section0.xml'])
   for pic in section.iter(q(HP,'pic')):
    E.SubElement(pic,q(HP,'orgSz'),width='1000',height='2000')
    E.SubElement(pic,q(HP,'curSz'),width='1000',height='2000')
    rendering=E.SubElement(pic,q(HP,'renderingInfo'))
    for name in ['transMatrix','scaMatrix','rotMatrix']:E.SubElement(rendering,'{http://www.hancom.co.kr/hwpml/2011/core}'+name,e1='2',e2='0',e3='123',e4='0',e5='3',e6='456')
   E.SubElement(section.find(q(HP,'p')),q(HP,'linesegarray'))
   files['Contents/section0.xml']=E.tostring(section)
   with zipfile.ZipFile(dest,'w') as z:
    for n,data in files.items():z.writestr(n,data)
   paginate(dest,[(None,1,1)]*3,sizes)
   with zipfile.ZipFile(dest) as z:
    for i,(w,h) in enumerate(sizes):
     sec=E.fromstring(z.read(f'Contents/section{i}.xml'));page=next(sec.iter(q(HP,'pagePr')));pic=next(sec.iter(q(HP,'pic')))
     self.assertEqual(page.get('landscape'),['WIDELY','NARROWLY','WIDELY'][i])
     self.assertEqual((int(page.get('width')),int(page.get('height'))),(min(w,h),max(w,h)))
     self.assertTrue(all(v=='0' for v in page.find(q(HP,'margin')).attrib.values()))
     self.assertEqual((int(pic.find(q(HP,'sz')).get('width')),int(pic.find(q(HP,'sz')).get('height'))),(w,h))
     self.assertEqual(pic.find(q(HP,'pos')).get('horzRelTo'),'PAPER');self.assertEqual(pic.find(q(HP,'pos')).get('vertRelTo'),'PAPER')
     self.assertEqual(pic.find(q(HP,'pos')).get('treatAsChar'),'0')
     self.assertFalse(list(sec.iter(q(HP,'tbl'))));self.assertFalse(list(sec.iter(q(HP,'linesegarray'))))
     matrices=list(pic.find(q(HP,'renderingInfo')))
     self.assertEqual(float(matrices[1].get('e1')),w/1000);self.assertEqual(float(matrices[1].get('e5')),h/2000)
     self.assertTrue(all(m.get('e3')=='0' and m.get('e6')=='0' for m in matrices))
