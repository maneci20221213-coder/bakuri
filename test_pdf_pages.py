import unittest,tempfile,zipfile
from pathlib import Path
import xml.etree.ElementTree as E
from pdf_pages import paginate,fit_page,HP,OPF,q
class PdfPageTests(unittest.TestCase):
 def test_mixed_orientation_and_ratio(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'x.hwpx'
   section=f'<section xmlns:hp="{HP}"><hp:p><hp:run><hp:secPr><hp:pagePr><hp:margin/></hp:pagePr></hp:secPr><hp:tbl rowCnt="2"><hp:sz/><hp:tr><hp:tc><hp:cellAddr rowAddr="0"/><hp:cellSz/><hp:pic><hp:sz/></hp:pic></hp:tc></hp:tr><hp:tr><hp:tc><hp:cellAddr rowAddr="1"/><hp:cellSz/><hp:pic><hp:sz/></hp:pic></hp:tc></hp:tr></hp:tbl></hp:run></hp:p></section>'
   content=f'<package xmlns="{OPF}"><manifest><item id="section0" href="Contents/section0.xml"/></manifest><spine><itemref idref="section0"/></spine></package>'
   with zipfile.ZipFile(p,'w') as z:
    z.writestr('Contents/section0.xml',section);z.writestr('Contents/content.hpf',content);z.writestr('Contents/header.xml','<head secCnt="1"/>');z.writestr('BinData/image.png',b'image')
   paginate(p,[(None,100,200),(None,300,100)])
   with zipfile.ZipFile(p) as z:
    for i,(w,h) in enumerate([(100,200),(300,100)]):
     section=E.fromstring(z.read(f'Contents/section{i}.xml'))
     page=next(section.iter(q(HP,'pagePr')))
     self.assertEqual(page.get('landscape'),'NARROWLY' if w>h else 'WIDELY')
     size=next(section.iter(q(HP,'sz')))
     self.assertAlmostEqual(int(size.get('width'))/int(size.get('height')),w/h,places=3)
     self.assertEqual(len(list(section.iter(q(HP,'tbl')))),0)
     self.assertEqual(int(size.get('width')),w*48);self.assertEqual(int(size.get('height')),h*48)
     self.assertTrue(all(int(v)==0 for v in page.find(q(HP,'margin')).attrib.values()))
    self.assertEqual(E.fromstring(z.read('Contents/header.xml')).get('secCnt'),'2')
    spine=E.fromstring(z.read('Contents/content.hpf')).find(q(OPF,'spine'))
    self.assertEqual([item.get('idref') for item in spine],['section0','section1'])

# Literal fixtures are intentionally independent of pdf_pages.OPF, to catch a
# namespace constant regression that the original shared-constant test missed.
HANCOM_OPF='http://www.idpf.org/2007/opf/'
def realistic_package(path,entries,namespace=HANCOM_OPF):
 section=f'<hs:sec xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" xmlns:hp="{HP}"><hp:p><hp:run><hp:secPr><hp:pagePr width="59528" height="84188"><hp:margin/></hp:pagePr></hp:secPr><hp:tbl rowCnt="{len(entries)}" colCnt="1"><hp:sz/>'
 for index in range(len(entries)):
  section+=f'<hp:tr><hp:tc borderFillIDRef="{index+1}"><hp:cellAddr rowAddr="{index}"/><hp:cellSz/><hp:subList><hp:p><hp:run><hp:pic><hp:sz/><hp:img binaryItemIDRef="image{index}"/></hp:pic></hp:run></hp:p></hp:subList></hp:tc></hp:tr>'
 section+='</hp:tbl></hp:run></hp:p></hs:sec>'
 content=f'<opf:package xmlns:opf="{namespace}"><opf:metadata><opf:title>keep title</opf:title></opf:metadata><opf:manifest><opf:item id="header" href="Contents/header.xml"/><opf:item id="section0" href="Contents/section0.xml"/>'+''.join(f'<opf:item id="image{i}" href="BinData/image{i}.png"/>' for i in range(len(entries)))+'</opf:manifest><opf:spine><opf:itemref idref="header"/><opf:itemref idref="section0"/></opf:spine></opf:package>'
 with zipfile.ZipFile(path,'w') as z:
  z.writestr('mimetype','application/hwp+zip');z.writestr('Contents/section0.xml',section)
  z.writestr('Contents/content.hpf',content);z.writestr('Contents/header.xml','<head secCnt="1"/>')
  for i,entry in enumerate(entries):z.writestr(f'BinData/image{i}.png',b'original image bytes '+bytes([i]))

class HancomPackagingRegressionTests(unittest.TestCase):
 def test_literal_hancom_namespace_metadata_binary_and_order(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'actual-shape.hwpx';entries=[(None,100,200),(None,300,100)]
   realistic_package(path,entries);paginate(path,entries)
   with zipfile.ZipFile(path) as z:
    package=E.fromstring(z.read('Contents/content.hpf'))
    self.assertEqual(package.tag,'{'+HANCOM_OPF+'}package')
    self.assertEqual(package.find('{'+HANCOM_OPF+'}metadata')[0].text,'keep title')
    manifest=package.find('{'+HANCOM_OPF+'}manifest');spine=package.find('{'+HANCOM_OPF+'}spine')
    self.assertEqual([x.get('idref') for x in spine],['header','section0','section1'])
    self.assertEqual([x.get('href') for x in manifest if x.get('id','').startswith('section')],['Contents/section0.xml','Contents/section1.xml'])
    self.assertTrue(all(x.tag=='{'+HANCOM_OPF+'}item' for x in manifest))
    for i in range(2):
     self.assertEqual(z.read(f'BinData/image{i}.png'),b'original image bytes '+bytes([i]))
     section=E.fromstring(z.read(f'Contents/section{i}.xml'))
     self.assertEqual(next(section.iter(q(HP,'img'))).get('binaryItemIDRef'),f'image{i}')
 def test_slashless_legacy_namespace_is_preserved(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'legacy.hwpx';entries=[(None,100,200)]
   realistic_package(path,entries,HANCOM_OPF.rstrip('/'));paginate(path,entries)
   with zipfile.ZipFile(path) as z:
    package=E.fromstring(z.read('Contents/content.hpf'));self.assertEqual(len(package.find('{'+HANCOM_OPF.rstrip('/')+'}spine')),2)
 def test_unrecognized_namespace_rejected_without_changing_file(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'invalid.hwpx';entries=[(None,100,200)]
   realistic_package(path,entries,'urn:unrecognized');original=path.read_bytes()
   with self.assertRaisesRegex(RuntimeError,'구역 목록 형식'):paginate(path,entries)
   self.assertEqual(path.read_bytes(),original)
 def test_pdf_staging_through_hancom_save_and_page_layout(self):
  from unittest.mock import patch
  import fitz
  from engine import OfficeSession
  from test_images import Hancom
  class SavedByHancom(Hancom):
   def SaveAs(self,path,fmt,options):
    realistic_package(Path(path),self.pictures)
    with zipfile.ZipFile(path) as z:files={n:z.read(n) for n in z.namelist()}
    for i,picture in enumerate(self.pictures):files[f'BinData/image{i}.png']=picture[2]
    with zipfile.ZipFile(path,'w') as z:
     for n,data in files.items():z.writestr(n,data)
    return True
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);pdf=d/'mixed.pdf';dest=d/'output.hwpx';stage=d/'stage';stage.mkdir()
   with fitz.open() as doc:
    doc.new_page(width=300,height=600);doc.new_page(width=800,height=400);doc.save(pdf)
   original=pdf.read_bytes();session=OfficeSession();app=SavedByHancom()
   with patch.object(session,'hwp',return_value=app):session.image_document([pdf],dest,stage,'background',lambda s:None)
   self.assertEqual(pdf.read_bytes(),original)
   with zipfile.ZipFile(dest) as z:
    self.assertEqual([n for n in z.namelist() if n.startswith('Contents/section')],['Contents/section0.xml','Contents/section1.xml'])
    for i,direction in enumerate(['WIDELY','NARROWLY']):
     section=E.fromstring(z.read(f'Contents/section{i}.xml'))
     self.assertEqual(next(section.iter(q(HP,'pagePr'))).get('landscape'),direction)
     self.assertFalse(list(section.iter(q(HP,'tbl'))))
     size=next(section.iter(q(HP,'pic'))).find(q(HP,'sz'))
     self.assertEqual((int(size.get('width')),int(size.get('height'))),[(30000,60000),(80000,40000)][i])
   self.assertTrue(all(picture[1]=='inline' for picture in app.pictures))
