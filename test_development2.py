import os,tempfile,threading,time,unittest
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication,QLineEdit,QDialog,QSystemTrayIcon
from PySide6.QtCore import QMimeData,QUrl,Qt
from PySide6.QtTest import QTest
from app import Window
from rename_engine import preview,pasted_lines
from tray_results import compression_savings
APP=QApplication.instance() or QApplication([])

class RenameOptionsTests(unittest.TestCase):
 def test_number_and_custom_text_positions_keep_extension(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'보고서_최종.PDF';p.touch()
   cases=[('before','','001_보고서_최종.PDF'),('after','','보고서_최종_001.PDF'),('before_marker','최종','보고서_001_최종.PDF'),('after_marker','보고서','보고서_001_최종.PDF')]
   for pos,marker,expected in cases:
    row=preview([p],number_enabled=True,number_position=pos,number_marker=marker)[0]
    self.assertFalse(row['error']);self.assertEqual(row['name'],expected)
   value={str(p):'서울'}
   self.assertEqual(preview([p],text_by_source=value,text_position='before')[0]['name'],'서울보고서_최종.PDF')
   self.assertEqual(preview([p],text_by_source=value,text_mode='replace',number_enabled=True)[0]['name'],'서울_001.PDF')
   self.assertTrue(preview([p],number_enabled=True,number_position='before_marker',number_marker='없음')[0]['error'])
 def test_multiline_preserves_empty_rows_and_rejects_mismatch(self):
  self.assertEqual(pasted_lines('서울\r\n\r\n부산\r\n',3),['서울','','부산'])
  self.assertEqual(pasted_lines('서울\n\n',2),['서울',''])
  for text,count in [('서울\n부산',3),('서울\t부산',1)]:
   with self.assertRaises(ValueError):pasted_lines(text,count)

class DevelopmentUiTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve();self.w=Window();self.w.settings.setValue('notify',False);self.w.rename_panel.journal=self.root/'history.json';self.w.show();APP.processEvents()
  self.addCleanup(self.w.deleteLater);self.addCleanup(self.w.hide);self.addCleanup(self.w.tray.hide);self.addCleanup(APP.clipboard().clear)
 def file(self,name):p=self.root/name;p.write_bytes(b'unchanged');return p
 def test_file_clipboard_import_all_tabs_and_text_editor_keeps_normal_paste(self):
  p=self.file('a.pdf');q=self.file('b.txt');folder=self.root/'folder';folder.mkdir()
  for mode in [0,1]:
   self.w.files.clear();self.w.mode_tabs.setCurrentIndex(mode);self.w.files.setFocus();APP.processEvents()
   mime=QMimeData();mime.setUrls([QUrl.fromLocalFile(str(p)),QUrl.fromLocalFile(str(q)),QUrl.fromLocalFile(str(p)),QUrl.fromLocalFile(str(folder)),QUrl('https://example.com/a.pdf')]);APP.clipboard().setMimeData(mime)
   QTest.keyClick(self.w.files,Qt.Key_V,Qt.ControlModifier)
   self.assertEqual(self.w.files.count(),2);self.assertEqual(p.read_bytes(),b'unchanged')
  self.w.rename_panel.find.setFocus();APP.clipboard().setText('복사한 문구');QTest.keyClick(self.w.rename_panel.find,Qt.Key_V,Qt.ControlModifier)
  self.assertEqual(self.w.rename_panel.find.text(),'복사한 문구');self.assertEqual(self.w.files.count(),2)
 def test_busy_paste_is_ignored(self):
  p=self.file('a.pdf');mime=QMimeData();mime.setUrls([QUrl.fromLocalFile(str(p))]);APP.clipboard().setMimeData(mime)
  self.w.busy=True;self.w.paste_files();self.assertEqual(self.w.files.count(),0);self.w.busy=False
 def test_per_file_text_survives_sort_uncheck_and_rename_undo(self):
  b=self.file('b.txt');a=self.file('a.txt');w=self.w;w.mode_tabs.setCurrentIndex(1);w.files.add_paths([str(b),str(a)]);panel=w.rename_panel
  panel.text_enabled.setChecked(True);panel.assign_values(['부산','서울']);w.files.sort_names()
  self.assertEqual([w.files.item(i).text(6) for i in range(2)],['서울','부산'])
  panel.text_position.setCurrentIndex(1);self.assertEqual(w.files.item(0).text(4),'a서울.txt')
  w.files.item(0).setText(6,'서울수정');self.assertEqual(w.files.item(0).text(4),'a서울수정.txt');w.files.item(0).setText(6,'서울')
  w.files.item(0).setCheckState(0,Qt.Unchecked);self.assertEqual(w.files.item(0).text(6),'서울')
  w.files.item(0).setCheckState(0,Qt.Checked);panel.replace_name.setChecked(True);panel.number_enabled.setChecked(True);panel.number_position.setCurrentIndex(0)
  self.assertEqual(w.files.item(0).text(4),'1_서울.txt')
  panel.execute();self.assertTrue((self.root/'1_서울.txt').exists());self.assertEqual(w.files.item(0).text(6),'서울')
  panel.undo();self.assertTrue(a.exists());self.assertEqual(w.files.item(0).text(6),'서울')
  editor=panel.files.itemDelegate().createEditor(panel.files.viewport(),None,panel.files.model().index(0,2));self.assertIsNone(editor)
 def test_only_completion_toast_and_tray_progress_stop(self):
  w=self.w;w.settings.setValue('notify',True);entered=threading.Event();release=threading.Event()
  def operation(control):control.update(37,'진행 중');entered.set();release.wait(3);control.check()
  with patch.object(w.tray,'showMessage') as notify:
   try:
    w.begin_job(operation,'convert');self.assertTrue(entered.wait(1));APP.processEvents();self.assertIn('37%',w.tray.toolTip());notify.assert_not_called()
    self.assertTrue(w.tray_stop_action.isEnabled());w.tray_stop_action.trigger();self.assertIn('중지 요청',w.tray.toolTip());self.assertFalse(w.tray_stop_action.isEnabled())
   finally:release.set()
   deadline=time.monotonic()+3
   while w.busy and time.monotonic()<deadline:QTest.qWait(10)
   self.assertFalse(w.busy);notify.assert_called_once();self.assertIn('작업 중지',notify.call_args.args[1]);self.assertTrue(w.tray_result_action.isEnabled())
  w.settings.setValue('notify',False)
 def test_completion_summary_savings_and_last_result_without_alert(self):
  rows=[dict(source='a.pdf',output='out.pdf',before=10_000_000,after=4_000_000,status='저장 완료',detail=''),dict(source='b.pdf',output='',before=90_000_000,after=90_000_000,status='실패',detail='')]
  w=self.w;w.settings.setValue('notify',True)
  with patch.object(w.tray,'showMessage') as notify,patch('app.QMessageBox.warning') as warning:
   w.finished(dict(paths=['out.pdf'],rows=rows,kind='compress',outcome='done',error=''))
   text=notify.call_args.args[1];self.assertIn('10.00 MB → 4.00 MB',text);self.assertIn('6.00 MB 절감(60.0%)',text);self.assertIn('실패 1개',text);warning.assert_not_called()
   self.assertEqual(w.last_result['rows'],rows);self.assertTrue(w.tray_result_action.isEnabled())
  w.settings.setValue('notify',False)

class SavingsTests(unittest.TestCase):
 def test_only_saved_files_count(self):
  self.assertEqual(compression_savings([dict(status='실패',before=100,after=0,output='')]),'')
  result=compression_savings([dict(status='저장 완료',before=1000,after=500,output='x'),dict(status='건너뜀',before=100000,after=0,output='')])
  self.assertIn('50.0%',result);self.assertIn('저장한 1개',result)
