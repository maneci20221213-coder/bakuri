import unittest,tempfile,zipfile,types
from pathlib import Path
from unittest.mock import patch
from PIL import Image
import fitz
from engine import convert,can_convert,OfficeSession
from image_inputs import IMAGES,stage_images
from hancom_images import create_document,table_dimensions,unit,verify_document

class ImageTests(unittest.TestCase):
 def test_extra_rasters_preserve_pixels_and_originals(self):
  with tempfile.TemporaryDirectory() as d:
   for extension in ['bmp','gif','webp','tif','tiff','ico']:
    path=Path(d)/('sample.'+extension)
    im=Image.new('RGB',(32,32),(40,90,200));im.save(path,**({'lossless':True} if extension=='webp' else {}))
    before=path.read_bytes()
    for fmt in ['png','jpg']:
     output=convert([path],fmt)
     self.assertEqual(len(output),1)
     with Image.open(output[0]) as image:self.assertEqual(image.size,(32,32))
    self.assertEqual(path.read_bytes(),before)
 def test_tiff_all_pages_and_order(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'scan.tiff';Image.new('RGB',(71,53),'red').save(path,save_all=True,append_images=[Image.new('RGB',(41,37),'blue')])
   out=convert([path],'png');self.assertEqual([Path(p).name for p in out],['scan_001.png','scan_002.png'])
   with Image.open(out[0]) as im:self.assertEqual(im.size,(71,53));self.assertEqual(im.getpixel((0,0))[:3],(255,0,0))
   with Image.open(out[1]) as im:self.assertEqual(im.size,(41,37));self.assertEqual(im.getpixel((0,0))[:3],(0,0,255))
   with fitz.open(convert([path],'pdf')[0]) as pdf:
    self.assertEqual(len(pdf),2)
    self.assertEqual([(int(pdf.extract_image(page.get_images()[0][0])['width']),int(pdf.extract_image(page.get_images()[0][0])['height'])) for page in pdf],[(71,53),(41,37)])
 def test_animated_first_frame_and_exif_orientation(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);path=d/'moving.gif';Image.new('RGB',(20,10),'red').save(path,save_all=True,append_images=[Image.new('RGB',(20,10),'blue')],duration=100,loop=0)
   out=convert([path],'png');self.assertEqual(len(out),1)
   with Image.open(out[0]) as im:self.assertEqual(im.getpixel((0,0))[:3],(255,0,0))
   path=d/'rotate.jpg';im=Image.new('RGB',(30,10));exif=im.getexif();exif[274]=6;im.save(path,exif=exif)
   with Image.open(convert([path],'png')[0]) as image:self.assertEqual(image.size,(10,30))
 def test_matrix_and_image_hwpx_merge_routing(self):
  self.assertTrue(all(can_convert('a'+ext,'hwpx') for ext in IMAGES))
  self.assertTrue(can_convert('a.hwp','hwpx'));self.assertTrue(can_convert('a.odt','hwpx'))
  self.assertTrue(can_convert('a.pdf','hwpx'));self.assertFalse(can_convert('a.hwpx','hwpx'))
  calls=[]
  def export(session,paths,dest,folder,mode,progress):
   calls.append(([Path(p).name for p in paths],mode));dest.write_bytes(b'fake COM output')
  with tempfile.TemporaryDirectory() as d,patch.object(OfficeSession,'image_document',export):
   paths=[Path(d)/'one.png',Path(d)/'two.bmp']
   for path in paths:Image.new('RGB',(30,20)).save(path)
   out=convert(paths,'hwpx',True,image_mode='inline');self.assertEqual(len(out),1);self.assertEqual(Path(out[0]).name,'합친문서.hwpx')
   self.assertEqual(calls,[(['one.png','two.bmp'],'inline')])
   out=convert(paths,'hwpx');self.assertEqual(len(out),2);self.assertEqual([Path(p).name for p in out],['one.hwpx','two.hwpx'])
   with self.assertRaises(ValueError):convert([Path(d)/'a.hwp'],'hwpx',True)

class Parameters:
 def __init__(self):self.values={}
 def SetItem(self,key,value):self.values[key]=value
 def CreateItemSet(self,key,kind):self.values[key]=Parameters();return self.values[key]
 def CreateItemArray(self,key,size):return self.CreateItemSet(key,'array')
class Picture:
 def __init__(self):self.Properties=Parameters()
class Hancom:
 """A stateful test double: fails if cell selection/navigation is incorrect."""
 def __init__(self,fail=False):self.actions={};self.row=0;self.selected=False;self.pictures=[];self.fail=fail;self.clears=0;self.HAction=types.SimpleNamespace(Run=self.run)
 def Clear(self,_):self.clears+=1
 def CreateAction(self,name):
  def create():p=Parameters();self.actions[name]=p;return p
  return types.SimpleNamespace(CreateSet=create,GetDefault=lambda p:True,Execute=lambda p:True)
 def run(self,name):
  if name=='TableCellBlock':self.selected=True
  elif name=='Cancel':self.selected=False
  elif name=='TableRightCell':
   if self.selected:raise AssertionError('selection not cancelled')
   self.row+=1
  return True
 def InsertBackgroundPicture(self,kind,path,embedded,fill,*args):
  assert self.selected and kind=='SelectedCell' and embedded and fill==5
  self.pictures.append((self.row,'background',Path(path).read_bytes()));return True
 def InsertPicture(self,path,embedded,size,*args):
  assert not self.selected and embedded and size==3
  self.pictures.append((self.row,'inline',Path(path).read_bytes()));return Picture()
 def SaveAs(self,path,fmt,_):
  assert fmt=='HWPX';rows=self.actions['TableCreate'].values['Rows'];mode=self.pictures[0][1]
  with zipfile.ZipFile(path,'w') as z:
   z.writestr('Contents/section0.xml','<hp:sec xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"><hp:tbl rowCnt="%d" colCnt="1">'%rows+''.join('<hp:tr><hp:tc borderFillIDRef="1">'+('<hp:pic/>' if mode=='inline' and not self.fail else '')+'</hp:tc></hp:tr>' for i in range(rows))+'</hp:tbl></hp:sec>')
   z.writestr('Contents/header.xml','<hh:head xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head" xmlns:hc="http://www.hancom.co.kr/hwpml/2011/core"><hh:borderFill id="1">'+('<hc:img/>' if mode=='background' and not self.fail else '')+'</hh:borderFill></hh:head>')
   for i,picture in enumerate(self.pictures):z.writestr(f'BinData/image{i}.png',picture[2])
  return True

class HancomTableTests(unittest.TestCase):
 def test_single_and_multiple_cells_both_modes(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);paths=[]
   for i,size in enumerate([(731,529),(400,900)]):
    path=d/f'{i}.png';Image.new('RGB',size,'red').save(path);paths.append(path)
   for count in [1,2]:
    entries=stage_images(paths[:count],d);width,heights=table_dimensions(entries)
    for (_,w,h),height in zip(entries,heights):
     self.assertLessEqual(height,unit(245));self.assertAlmostEqual(width/height,w/h,delta=.001)
    for mode in ['background','inline']:
     app=Hancom();out=d/f'{count}_{mode}.hwpx';create_document(app,entries,out,mode)
     self.assertEqual(app.actions['TableCreate'].values['Rows'],count);self.assertEqual(app.actions['TableCreate'].values['Cols'],1)
     self.assertEqual([p[0] for p in app.pictures],list(range(count)));self.assertEqual(app.clears,2)
     with zipfile.ZipFile(out) as archive:
      import io
      with Image.open(io.BytesIO(archive.read('BinData/image0.png'))) as image:self.assertEqual(image.size,(731,529))
 def test_incomplete_documents_are_rejected_and_cleared(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);path=d/'a.png';Image.new('RGB',(30,20)).save(path);entries=stage_images([path],d)
   for mode in ['background','inline']:
    app=Hancom(fail=True)
    with self.assertRaisesRegex(RuntimeError,'검증 실패'):create_document(app,entries,d/'bad.hwpx',mode)
    self.assertEqual(app.clears,2)

class JpegPdfTests(unittest.TestCase):
 def test_jpeg_bytes_embedded_without_reencoding(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'photo.jpg';Image.new('RGB',(731,529),'red').save(path,quality=95)
   original=path.read_bytes()
   with fitz.open(convert([path],'pdf')[0]) as document:
    image=document.extract_image(document[0].get_images()[0][0]);self.assertEqual(image['image'],original);self.assertEqual((image['width'],image['height']),(731,529))
