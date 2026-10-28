import unittest,tempfile,io,hashlib,threading
from pathlib import Path
from unittest.mock import patch
from PIL import Image,ImageDraw
import fitz
from compression import compress,TARGET_BYTES,compress_image
from jobs import JobControl,Cancelled
from engine import convert,OfficeSession

class CompressionTests(unittest.TestCase):
 def test_photo_one_mb_target_jpeg_name_collision_and_original(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);path=d/'사진.jpg';Image.effect_noise((2600,1800),32).convert('RGB').save(path,quality=100,subsampling=0)
   original=hashlib.sha256(path.read_bytes()).hexdigest();control=JobControl();output=compress([path],'size',control=control)
   self.assertGreater(path.stat().st_size,TARGET_BYTES);self.assertEqual(len(output),1,control.rows)
   result=Path(output[0]);self.assertEqual(result.name,'사진_용량축소.jpeg');self.assertLessEqual(result.stat().st_size,TARGET_BYTES)
   with Image.open(result) as image:self.assertGreaterEqual(max(image.size),1600);self.assertEqual(image.format,'JPEG')
   self.assertEqual(original,hashlib.sha256(path.read_bytes()).hexdigest());self.assertEqual(control.percent,100)
   second=compress([path],'size')[0];self.assertEqual(Path(second).name,'사진_용량축소_1.jpeg')
 def test_transparent_graphic_keeps_pixels_and_transparency(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'文字.png';image=Image.new('RGBA',(800,600),(0,0,0,0));ImageDraw.Draw(image).text((30,30),'123456 abc',fill=(10,20,30,255));image.save(path,compress_level=0)
   result=Path(compress([path],'quality')[0]);self.assertEqual(result.suffix,'.png')
   with Image.open(result) as output:self.assertEqual(output.size,image.size);self.assertEqual(output.convert('RGBA').tobytes(),image.tobytes())
 def test_no_bigger_result_and_small_photo_skipped(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);path=d/'small.jpeg';Image.new('RGB',(20,10),'red').save(path)
   control=JobControl();self.assertEqual(compress([path],'size',control=control),[]);self.assertIn('이미 1MB 이하',control.rows[0]['detail'])
   control=JobControl();self.assertEqual(compress([path],'lossless',control=control),[]);self.assertEqual(control.rows[0]['status'],'건너뜀')
 def test_goal_missed_does_not_break_quality_floor(self):
  # Exercise the bounded search without a slow/unreproducible pathological photo.
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);path=d/'noise.jpeg';Image.effect_noise((2800,1900),40).convert('RGB').save(path,quality=100)
   qualities=[];dimensions=[]
   def encode(image,fmt,quality=92,strip=False):
    qualities.append(quality);dimensions.append(max(image.size));out=io.BytesIO();image.save(out,'JPEG');return out.getvalue()+b'0'*TARGET_BYTES
   with patch('compression.encoded',encode):
    target,suffix,detail=compress_image(path,d,'size',False,False,lambda:None,lambda f:None)
   self.assertGreater(target.stat().st_size,TARGET_BYTES);self.assertIn('목표 미달',detail);self.assertGreaterEqual(min(qualities),82);self.assertGreaterEqual(min(dimensions),1600)
 def test_animation_skipped_without_losing_frames(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'moving.gif';Image.new('RGB',(30,20),'red').save(path,save_all=True,append_images=[Image.new('RGB',(30,20),'blue')],duration=100,loop=0)
   control=JobControl();self.assertEqual(compress([path],control=control),[]);self.assertIn('모든 프레임',control.rows[0]['detail'])
   with Image.open(path) as original:self.assertEqual(original.n_frames,2)
 def test_tiff_all_pages_lossless(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'scan.tif';images=[Image.new('RGB',(100,80),'red'),Image.new('RGB',(70,110),'blue')];images[0].save(path,save_all=True,append_images=images[1:],compression='raw')
   output=compress([path],'quality')[0]
   with Image.open(output) as image:
    self.assertEqual(image.n_frames,2)
    for index,expected in enumerate(images):image.seek(index);self.assertEqual(image.convert('RGB').tobytes(),expected.tobytes())
 def test_metadata_preserve_or_remove_and_orientation(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'oriented.jpg';image=Image.effect_noise((1800,1200),25).convert('RGB');exif=image.getexif();exif[274]=6;exif[315]='Bakuri test author';image.save(path,quality=100,subsampling=0,exif=exif)
   for strip in [False,True]:
    result=compress([path],'quality',strip_metadata=strip)[0]
    with Image.open(result) as output:
     self.assertEqual(output.size,(1200,1800));self.assertEqual(output.getexif().get(274,1),1)
     self.assertEqual(output.getexif().get(315),None if strip else 'Bakuri test author')
 def test_pdf_text_links_annotations_forms_and_scan_resolution(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);source=d/'scan.pdf';data=io.BytesIO();Image.new('RGB',(2400,3300),'white').save(data,'PNG',compress_level=0)
   with fitz.open() as document:
    page=document.new_page(width=288,height=396);page.insert_image(page.rect,stream=data.getvalue());page.insert_text((10,20),'searchable text')
    page.insert_link({'kind':fitz.LINK_URI,'from':fitz.Rect(10,25,100,45),'uri':'https://example.org'})
    page.add_text_annot((30,60),'keep annotation');widget=fitz.Widget();widget.field_name='test';widget.field_type=fitz.PDF_WIDGET_TYPE_TEXT;widget.rect=fitz.Rect(10,90,150,110);widget.field_value='keep value';page.add_widget(widget);document.save(source)
   original=source.read_bytes();control=JobControl();outputs=compress([source],'quality',control=control);self.assertEqual(len(outputs),1,control.rows)
   with fitz.open(outputs[0]) as result:
    page=result[0];self.assertIn('searchable text',page.get_text());self.assertEqual(page.get_links()[0]['uri'],'https://example.org');self.assertEqual(len(list(page.annots())),1);self.assertEqual(list(page.widgets())[0].field_value,'keep value')
    entry=page.get_images()[0];self.assertEqual((entry[2],entry[3]),(1200,1650))
   self.assertEqual(source.read_bytes(),original)
 def test_pdf_masks_and_shared_images_remain_correct(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'alpha.pdf';data=io.BytesIO();Image.new('RGBA',(100,80),(30,100,200,70)).save(data,'PNG')
   with fitz.open() as document:
    for i in range(2):page=document.new_page(width=120,height=100);page.insert_image(fitz.Rect(10,10,110,90),stream=data.getvalue())
    document.save(path,deflate=False)
   control=JobControl();outputs=compress([path],control=control)
   if outputs:
    with fitz.open(path) as original,fitz.open(outputs[0]) as result:
     for a,b in zip(original,result):self.assertEqual(a.get_pixmap().samples,b.get_pixmap().samples)
   else:self.assertNotEqual(control.rows[0]['status'],'실패',control.rows)

class CancellationTests(unittest.TestCase):
 def test_pre_cancel_does_not_create_outputs(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'a.png';Image.new('RGB',(30,20)).save(path);control=JobControl();control.cancel()
   with self.assertRaises(Cancelled):convert([path],'jpeg',control=control)
   self.assertEqual(list(Path(d).iterdir()),[path])
 def test_conversion_cancel_preserves_completed_files_and_stops_future_pages(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);path=d/'pages.pdf'
   with fitz.open() as doc:
    for i in range(6):doc.new_page()
    doc.save(path)
   control=JobControl();original_publish=control.publish
   def publish(*args):
    out=original_publish(*args);control.cancel();return out
   control.publish=publish
   with self.assertRaises(Cancelled):convert([path],'png',control=control)
   self.assertEqual(len(control.outputs),1);self.assertTrue(Path(control.outputs[0]).exists());self.assertEqual(len(list(d.glob('*.png'))),1);self.assertLess(control.percent,100)
 def test_cancel_during_atomic_publish_removes_partial_file(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);source=d/'source.bin';source.write_bytes(b'a'*(3*1024*1024));output=d/'out.bin';control=JobControl();checks=[0]
   def check():
    checks[0]+=1
    if checks[0]>=4:raise Cancelled()
   control.check=check
   with self.assertRaises(Cancelled):control.publish(source,output)
   self.assertFalse(output.exists());self.assertEqual(control.outputs,[]);self.assertEqual(source.stat().st_size,3*1024*1024)
 def test_cancel_between_compress_candidates_publishes_nothing(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'large.jpeg';Image.effect_noise((1800,1400),30).convert('RGB').save(path,quality=100,subsampling=0)
   control=JobControl();control.callback=lambda percent,text:control.cancel() if percent>0 else None
   with self.assertRaises(Cancelled):compress([path],'size',control=control)
   self.assertEqual(control.outputs,[]);self.assertEqual(len(list(Path(d).iterdir())),1)
 def test_progress_monotonic_reaches_100_after_success(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);paths=[]
   for i in range(3):p=d/f'{i}.png';Image.new('RGB',(20+i,30)).save(p);paths.append(p)
   values=[];control=JobControl(lambda percent,text:values.append(percent));out=convert(paths,'jpeg',control=control)
   self.assertEqual(values,sorted(values));self.assertEqual(values[-1],100);self.assertEqual(len(out),3);self.assertTrue(all(Path(p).suffix=='.jpeg' for p in out))

class OfficeCancellationTests(unittest.TestCase):
 def test_cancel_after_open_still_closes_owned_office_instance(self):
  import types,sys
  calls=[];control=JobControl()
  class Hwp:
   def Open(self,*args):calls.append('open');control.cancel();return True
   def SaveAs(self,*args):calls.append('save');raise AssertionError('must not export after cancellation')
   def Clear(self,*args):calls.append('clear')
   def Quit(self):calls.append('quit')
  com=types.ModuleType('pythoncom');com.CoInitialize=lambda:calls.append('init');com.CoUninitialize=lambda:calls.append('uninit')
  client=types.ModuleType('win32com.client');client.DispatchEx=lambda name:Hwp()
  package=types.ModuleType('win32com');package.client=client
  with tempfile.TemporaryDirectory() as d,patch.dict(sys.modules,{'pythoncom':com,'win32com':package,'win32com.client':client,'windows':types.SimpleNamespace(register_hancom=lambda app:True)}):
   path=Path(d)/'a.hwp';path.write_bytes(b'original')
   with self.assertRaises(Cancelled):convert([path],'pdf',control=control)
   self.assertEqual(list(Path(d).iterdir()),[path]);self.assertEqual(control.outputs,[])
  self.assertEqual(calls,['init','open','clear','quit','uninit'])

class PdfPreservationTests(unittest.TestCase):
 def test_shared_image_uses_largest_display_size(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'shared.pdf';image=Image.effect_noise((1800,1200),32).convert('RGB');data=io.BytesIO();image.save(data,'JPEG',quality=100)
   with fitz.open() as document:
    page=document.new_page(width=432,height=288);xref=page.insert_image(page.rect,stream=data.getvalue())
    page=document.new_page(width=432,height=288);page.insert_image(fitz.Rect(0,0,43.2,28.8),xref=xref);document.save(path)
   control=JobControl();outputs=compress([path],'size',control=control);self.assertEqual(len(outputs),1,control.rows)
   with fitz.open(outputs[0]) as result:
    for page in result:
     entry=page.get_images()[0];self.assertEqual((entry[2],entry[3]),(1500,1000))
 def test_signature_field_is_skipped(self):
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'signature.pdf'
   with fitz.open() as document:
    page=document.new_page();widget=fitz.Widget();widget.field_name='signature';widget.field_type=fitz.PDF_WIDGET_TYPE_SIGNATURE;widget.rect=fitz.Rect(10,10,150,50);page.add_widget(widget);document.save(path)
   control=JobControl();self.assertEqual(compress([path],control=control),[]);self.assertEqual(control.rows[0]['status'],'건너뜀');self.assertIn('서명',control.rows[0]['detail'])
 def test_grayscale_and_rgb_render_after_lossless_optimization(self):
  with tempfile.TemporaryDirectory() as d:
   for mode in ['L','RGB']:
    source=Path(d)/(mode+'.pdf');data=io.BytesIO();Image.linear_gradient('L').resize((300,300)).convert(mode).save(data,'PNG',compress_level=0)
    with fitz.open() as document:
     page=document.new_page(width=200,height=200);page.insert_image(page.rect,stream=data.getvalue());document.save(source)
    control=JobControl();outputs=compress([source],'lossless',control=control);self.assertEqual(len(outputs),1,control.rows)
    with fitz.open(source) as original,fitz.open(outputs[0]) as result:self.assertEqual(original[0].get_pixmap().samples,result[0].get_pixmap().samples)


class TiffMetadataTests(unittest.TestCase):
 def test_custom_metadata_tiff_skipped_unless_removal_requested(self):
  from PIL.TiffImagePlugin import ImageFileDirectory_v2
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'metadata.tif';info=ImageFileDirectory_v2();info[270]='private description';Image.new('RGB',(200,160),'red').save(path,compression='raw',tiffinfo=info)
   control=JobControl();self.assertEqual(compress([path],control=control),[]);self.assertIn('메타데이터',control.rows[0]['detail'])
   control=JobControl();outputs=compress([path],strip_metadata=True,control=control);self.assertEqual(len(outputs),1,control.rows)
   with Image.open(outputs[0]) as output:self.assertNotIn(270,output.tag_v2)
