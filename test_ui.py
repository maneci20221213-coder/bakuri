import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import unittest,tempfile
from pathlib import Path
from PIL import Image
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from app import Files,Window,SettingsDialog,QuickPopup
app=QApplication.instance() or QApplication([])
class UiTests(unittest.TestCase):
 def test_check_and_sort(self):
  with tempfile.TemporaryDirectory() as d:
   paths=[]
   for name in ['사진10.png','사진2.png','사진1.png']:
    p=Path(d)/name; Image.new('RGB',(3,3)).save(p); paths.append(str(p))
   files=Files(); files.add_paths(paths); files.item(0).setCheckState(0,Qt.Unchecked)
   files.sort_names()
   self.assertEqual([files.item(i).text(2) for i in range(3)],['사진1.png','사진2.png','사진10.png'])
   self.assertEqual(len(files.checked_paths()),2)
   self.assertEqual(files.item(2).checkState(0),Qt.Unchecked)
   files.check_all(Qt.Unchecked); self.assertEqual(files.checked_paths(),[])
 def test_settings_and_tray(self):
  w=Window(); dialog=SettingsDialog(w)
  self.assertEqual(dialog.key.count(),4)
  self.assertIn('설정',[a.text() for a in w.tray.contextMenu().actions()])
  self.assertIn('0.14.5',w.windowTitle());self.assertNotIn('시험',w.windowTitle())
  w.tray.hide(); w.deleteLater()

class PopupTests(unittest.TestCase):
 def test_direction_and_enter(self):
  from PySide6.QtTest import QTest
  popup=QuickPopup(); selected=[]; popup.chosen.connect(selected.append)
  popup.present(['sample.pdf']); app.processEvents()
  QTest.keyClick(popup.buttons['pdf'],Qt.Key_Right)
  QTest.keyClick(popup.buttons['jpeg'],Qt.Key_Return)
  self.assertEqual(selected,['hwpx']); self.assertFalse(popup.isVisible())
 def test_escape(self):
  from PySide6.QtTest import QTest
  popup=QuickPopup(); popup.present(['sample.pdf']); app.processEvents()
  QTest.keyClick(popup.buttons['pdf'],Qt.Key_Escape)
  self.assertFalse(popup.isVisible())

class RecentUiTests(unittest.TestCase):
 def test_delete_keeps_original(self):
  from PySide6.QtTest import QTest
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'original.png'; Image.new('RGB',(30,20)).save(p)
   files=Files(); files.add_paths([str(p),str(p)])
   self.assertEqual(files.count(),1)
   files.item(0).setSelected(True); QTest.keyClick(files,Qt.Key_Delete)
   self.assertEqual(files.count(),0); self.assertTrue(p.exists())
 def test_popup_transparency_and_hidden_timer(self):
  popup=QuickPopup(); self.assertTrue(popup.testAttribute(Qt.WA_TranslucentBackground))
  popup.present(['file.pdf']); self.assertTrue(popup.monitor.isActive())
  popup.hide(); self.assertFalse(popup.monitor.isActive())
 def test_completion_link(self):
  w=Window(); w.settings.setValue('notify',False); w.finished(['/tmp/a.pdf','/tmp/other/b.pdf'])
  self.assertIn('href=',w.status.text()); self.assertEqual(w.output_folders,[str(Path('/tmp')),str(Path('/tmp/other'))])
  w.tray.hide(); w.deleteLater()

class LatestPopupTests(unittest.TestCase):
 def test_blank_click_closes_without_conversion(self):
  from unittest.mock import patch
  import types,sys
  popup=QuickPopup();chosen=[];popup.chosen.connect(chosen.append);popup.present(['a.pdf']);app.processEvents()
  point=popup.mapToGlobal(__import__('PySide6.QtCore',fromlist=['QPoint']).QPoint(1,1))
  # Qt's offscreen backend does not provide a real Win32 HWND. Supply the
  # native coordinate boundary while exercising the actual blank-hit logic.
  native=types.SimpleNamespace(ScreenToClient=lambda hwnd,p:(1,1),GetClientRect=lambda hwnd:(0,0,popup.width(),popup.height()))
  with patch.dict(sys.modules,{'win32gui':native}): popup.clicked_at((point.x(),point.y()))
  self.assertFalse(popup.isVisible());self.assertEqual(chosen,[])
 def test_button_click_still_converts(self):
  from PySide6.QtTest import QTest
  popup=QuickPopup();chosen=[];popup.chosen.connect(chosen.append);popup.present(['a.pdf']);app.processEvents()
  QTest.mouseClick(popup.buttons['pdf'],Qt.LeftButton);self.assertEqual(chosen,['pdf_merge'])
 def test_escape_without_focus(self):
  from unittest.mock import patch
  import types,sys
  popup=QuickPopup();popup.present(['a.pdf'],123,0)
  with patch.dict(sys.modules,{'windows':types.SimpleNamespace(source_active=lambda *a:True,escape_pressed=lambda:True)}),patch.object(sys,'platform','win32'):
   popup.check_source()
  self.assertFalse(popup.isVisible())
 def test_xlsx_quick_button_and_header(self):
  popup=QuickPopup();popup.present(['a.xls']);self.assertTrue(popup.buttons['xlsx'].isVisible());self.assertFalse(popup.buttons['hwpx'].isVisible());popup.hide()
  files=Files();files.show();app.processEvents();files.place_master()
  self.assertGreater(files.selection_caption.x(),files.master.geometry().right());self.assertEqual(files.selection_caption.text(),'선택');files.hide()

class SaveModeTests(unittest.TestCase):
 def test_pdf_merge_resets_for_other_formats(self):
  w=Window();w.merge.click();self.assertTrue(w.merge.isChecked())
  w.fmt.setCurrentText('XLSX');self.assertFalse(w.merge.isEnabled());self.assertFalse(w.merge.isChecked());self.assertTrue(w.individual.isChecked())
  w.fmt.setCurrentText('PDF');self.assertTrue(w.merge.isEnabled());self.assertTrue(w.individual.isChecked())
  w.tray.hide();w.deleteLater()

class Popup080Tests(unittest.TestCase):
 def test_center_button_matrix(self):
  popup=QuickPopup()
  cases=[(['a.xlsx'],None),(['a.xls','b.xlsx'],None),(['a.xls','b.csv'],'xlsx'),(['a.hwp'],'hwpx'),(['a.HWP','b.hwp'],'hwpx'),(['a.hwpx'],None),(['a.odt'],None),(['a.hwp','b.hwpx'],None),(['a.bmp','b.webp'],'compress'),(['a.pdf'],'compress')]
  for paths,center in cases:
   popup.present(paths)
   self.assertEqual(popup.buttons['xlsx'].isVisible(),center=='xlsx',paths)
   self.assertEqual(popup.buttons['hwpx'].isVisible(),center=='hwpx',paths)
   self.assertEqual(popup.buttons['compress'].isVisible(),center=='compress',paths)
   popup.hide()
 def test_native_navigation_without_focus_and_border(self):
  popup=QuickPopup();selected=[];popup.chosen.connect(selected.append)
  for iteration in range(60):
   popup.present(['a.xls']);popup.clearFocus()
   for vk,key in [(0x25,'png'),(0x27,'xlsx'),(0x27,'jpeg'),(0x25,'xlsx'),(0x26,'pdf'),(0x28,'xlsx'),(0x28,'more'),(0x26,'xlsx'),(0x26,'pdf'),(0x27,'jpeg')]:
    popup.native_key(vk);self.assertEqual(popup.current,key)
    self.assertEqual([k for k,b in popup.buttons.items() if b.property('selected')],[key])
   popup.native_key(0x0D);self.assertEqual(selected[-1],'jpeg');self.assertFalse(popup.isVisible())
  popup.present(['a.hwp']);popup.native_key(0x09);popup.native_key(0x09)
  self.assertEqual(popup.current,'hwpx');popup.native_key(0x20);self.assertEqual(selected[-1],'hwpx')
 def test_hwpx_merge_requires_only_images(self):
  with tempfile.TemporaryDirectory() as d:
   d=Path(d);image=d/'a.bmp';Image.new('RGB',(20,20)).save(image)
   w=Window();w.files.add_paths([str(image)]);w.fmt.setCurrentText('HWPX');self.assertTrue(w.merge.isEnabled())
   w.merge.click();self.assertTrue(w.merge.isChecked())
   document=d/'a.hwp';document.write_bytes(b'hwp');w.files.add_paths([str(document)]);self.assertFalse(w.merge.isEnabled());self.assertTrue(w.individual.isChecked())
   w.tray.hide();w.deleteLater()
 def test_image_setting_roundtrip(self):
  w=Window();previous=w.settings.value('image_mode','background');w.settings.setValue('image_mode','background')
  dialog=SettingsDialog(w);self.assertEqual(dialog.image_mode.currentData(),'background')
  dialog.image_mode.setCurrentIndex(1);dialog.save();self.assertEqual(w.settings.value('image_mode'),'inline')
  self.assertEqual(SettingsDialog(w).image_mode.currentData(),'inline');w.settings.setValue('image_mode',previous);w.tray.hide();w.deleteLater()


class SpatialNavigationTests(unittest.TestCase):
 def test_center_traversal_and_edges(self):
  popup=QuickPopup()
  for file,center in [('a.hwp','hwpx'),('a.xls','xlsx'),('a.png','compress')]:
   popup.present([file]);popup.native_key(0x25)
   self.assertEqual(popup.current,'png')
   popup.native_key(0x25);self.assertEqual(popup.current,'png')
   popup.native_key(0x27);self.assertEqual(popup.current,center)
   popup.native_key(0x27);self.assertEqual(popup.current,'jpeg')
   popup.native_key(0x27);self.assertEqual(popup.current,'jpeg')
   popup.native_key(0x25);self.assertEqual(popup.current,center)
   popup.native_key(0x25);self.assertEqual(popup.current,'png')
   popup.select('pdf');popup.native_key(0x26);self.assertEqual(popup.current,'pdf')
   popup.native_key(0x28);self.assertEqual(popup.current,center)
   popup.native_key(0x28);self.assertEqual(popup.current,'more')
   popup.native_key(0x28);self.assertEqual(popup.current,'more')
   popup.native_key(0x26);self.assertEqual(popup.current,center)
   popup.native_key(0x26);self.assertEqual(popup.current,'pdf');popup.hide()
 def test_no_center_skips_empty_position(self):
  popup=QuickPopup()
  for file in ['a.xlsx','a.hwpx','a.odt']:
   popup.present([file]);popup.native_key(0x25);popup.native_key(0x27);self.assertEqual(popup.current,'jpeg')
   popup.native_key(0x25);self.assertEqual(popup.current,'png')
   popup.select('pdf');popup.native_key(0x28);self.assertEqual(popup.current,'more')
   popup.native_key(0x26);self.assertEqual(popup.current,'pdf');popup.hide()

class JobUiTests(unittest.TestCase):
 def test_jpeg_label_and_image_pdf_compression_center(self):
  w=Window();self.assertIn('JPEG',[w.fmt.itemText(i) for i in range(w.fmt.count())]);self.assertNotIn('JPG',[w.fmt.itemText(i) for i in range(w.fmt.count())]);w.tray.hide();w.deleteLater()
  popup=QuickPopup();self.assertEqual(popup.buttons['jpeg'].accessibleName(),'JPEG')
  for paths in [['a.jpg'],['a.pdf'],['a.png','b.pdf']]:
   popup.present(paths);self.assertTrue(popup.buttons['compress'].isVisible());self.assertFalse(popup.buttons['hwpx'].isVisible());popup.select('png');popup.native_key(0x27);self.assertEqual(popup.current,'compress');popup.hide()
 def test_progress_anchor_stop_button_and_cancel_reset(self):
  import threading,time
  from PySide6.QtCore import QPoint
  from PySide6.QtTest import QTest
  from jobs import Cancelled
  for stop_from_popup in [True,False]:
   w=Window();w.settings.setValue('notify',False);entered=threading.Event();release=threading.Event()
   def operation(control):
    control.update(37,'test measured units');entered.set();release.wait(2);control.check()
   center=QPoint(400,300);w.begin_job(operation,'convert',center);self.assertTrue(entered.wait(1));app.processEvents()
   self.assertEqual(w.run.text(),'작업 중지');self.assertTrue(w.run.isEnabled());self.assertEqual(w.progress_popup.number.text(),'37%');self.assertTrue(w.progress_popup.isVisible())
   self.assertLessEqual(abs(w.progress_popup.geometry().center().x()-center.x()),1);self.assertLessEqual(abs(w.progress_popup.geometry().center().y()-center.y()),1)
   QTest.mouseClick(w.progress_popup.stop if stop_from_popup else w.run,Qt.LeftButton)
   self.assertTrue(w.control.cancelled.is_set());self.assertEqual(w.run.text(),'중지 요청 중');self.assertTrue(w.busy);self.assertFalse(w.run.isEnabled());self.assertFalse(w.progress_popup.stop.isEnabled())
   w.update_progress(60,'late queued progress');self.assertIn('중지 요청 중',w.status.text())
   release.set();deadline=time.monotonic()+2
   while w.busy and time.monotonic()<deadline:QTest.qWait(10)
   self.assertFalse(w.busy);self.assertFalse(w.progress_popup.isVisible());self.assertIn('작업 중지',w.status.text());self.assertTrue(w.run.isEnabled());self.assertEqual(w.run.text(),'변환 시작  →');w.tray.hide();w.deleteLater()
 def test_main_compression_mode_and_results(self):
  w=Window();w.settings.setValue('notify',False);w.fmt.setCurrentText('용량 축소');self.assertEqual(w.run.text(),'용량 축소 시작');self.assertFalse(w.merge.isEnabled());self.assertFalse(w.compression_profile.isHidden())
  row=dict(source='/tmp/a.jpeg',output='/tmp/a_용량축소.jpeg',before=2_000_000,after=900_000,status='저장 완료',detail='1MB 목표 달성')
  w.finished(dict(paths=[row['output']],rows=[row],kind='compress',outcome='done',error=''))
  self.assertIn('상세 결과',w.status.text());self.assertIn('저장 폴더',w.status.text());self.assertEqual(w.compression_rows,[row]);w.tray.hide();w.deleteLater()
 def test_quick_conversion_passes_original_popup_center(self):
  from unittest.mock import patch
  w=Window();w.quick_paths=['/tmp/a.pdf'];w.popup.present(w.quick_paths);center=w.popup.geometry().center()
  with patch.object(w,'start_conversion') as start:
   w.quick_selected('jpeg');self.assertEqual(start.call_args.args,(['/tmp/a.pdf'],'jpeg',False,center))
  w.popup.hide();w.tray.hide();w.deleteLater()
 def test_quick_compression_can_show_options_or_use_saved_preferences(self):
  from unittest.mock import patch
  from work_ui import CompressionDialog
  w=Window();previous=w.settings.value('compress_direct',False,type=bool);w.settings.setValue('compress_direct',True)
  with patch.object(w,'begin_job') as begin:
   w.start_compression(['/tmp/a.pdf'],__import__('PySide6.QtCore',fromlist=['QPoint']).QPoint(400,300));self.assertEqual(begin.call_args.args[1],'compress')
  w.settings.setValue('compress_direct',False)
  with patch.object(CompressionDialog,'exec',return_value=__import__('PySide6.QtWidgets',fromlist=['QDialog']).QDialog.Rejected),patch.object(w,'begin_job') as begin:
   w.start_compression(['/tmp/a.pdf'],__import__('PySide6.QtCore',fromlist=['QPoint']).QPoint(400,300));begin.assert_not_called()
  w.settings.setValue('compress_direct',previous);w.tray.hide();w.deleteLater()
