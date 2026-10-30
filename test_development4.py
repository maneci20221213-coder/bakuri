import os,tempfile,unittest
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication,QLineEdit
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from app import Window
APP=QApplication.instance() or QApplication([])

class RenameListTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve()
  self.w=Window();self.w.settings.setValue('notify',False);self.panel=self.w.rename_panel;self.panel.journal=self.root/'history.json'
  self.w.show();APP.processEvents();self.w.mode_tabs.setCurrentIndex(1)
  self.paths=[self.root/name for name in ['a.PDF','b.PDF','c.PDF','d.PDF']]
  for p in self.paths:p.write_bytes(p.name.encode())
  self.w.files.add_paths([str(p) for p in self.paths]);APP.processEvents()
  self.addCleanup(self.w.deleteLater);self.addCleanup(self.w.hide);self.addCleanup(self.w.tray.hide);self.addCleanup(APP.clipboard().clear)
 def paste(self,column,text,row=0):
  files=self.w.files;files.setCurrentItem(files.item(row),column);files.setFocus();APP.processEvents();APP.clipboard().setText(text);QTest.keyClick(files,Qt.Key_V,Qt.ControlModifier);APP.processEvents()
 def test_restore_conversion_size_and_repeat_switch(self):
  w=self.w;w.mode_tabs.setCurrentIndex(0);w.resize(905,710);APP.processEvents();size=w.size()
  for _ in range(2):
   w.mode_tabs.setCurrentIndex(1);APP.processEvents();self.assertGreaterEqual(w.width(),1100)
   w.resize(1250,780);w.mode_tabs.setCurrentIndex(0);APP.processEvents();self.assertEqual(w.size(),size)
 def test_text_column_opt_in_plain_insert_and_fill(self):
  self.assertTrue(self.w.files.isColumnHidden(6));self.panel.text_enabled.setChecked(True);self.assertFalse(self.w.files.isColumnHidden(6))
  self.paste(6,'서울\r\n\r\n부산\r\n')
  self.assertEqual([self.w.files.item(i).text(6) for i in range(4)],['서울','서울','부산','부산'])
  self.assertEqual(self.w.files.item(0).text(4),'서울a.PDF')
  self.panel.text_enabled.setChecked(False);self.assertTrue(self.w.files.isColumnHidden(6));self.assertEqual(self.w.files.item(0).text(4),'a.PDF')
  self.panel.text_enabled.setChecked(True);self.panel.assign_values(['지역','','동네','']);self.panel.fill.click()
  self.assertEqual([self.w.files.item(i).text(6) for i in range(4)],['지역','지역','동네','동네'])
  self.w.mode_tabs.setCurrentIndex(0);self.assertTrue(self.w.files.isColumnHidden(6))
 def test_name_paste_starts_at_current_skips_unchecked_no_padding(self):
  self.w.files.item(2).setCheckState(0,Qt.Unchecked);self.paste(4,'첫째\r\n둘째.PDF\r\n',1)
  self.assertEqual([self.w.files.item(i).text(4) for i in range(4)],['a.PDF','첫째.PDF','','둘째.PDF'])
  self.panel.string.setText('추가');self.assertEqual(self.w.files.item(1).text(4),'첫째.PDF')
  self.w.files.sort_names();self.assertEqual(self.w.files.item(3).text(4),'둘째.PDF')
  self.w.files.item(1).setText(4,'');self.assertEqual(self.w.files.item(1).text(4),'추가b.PDF')
 def test_overflow_and_multi_column_are_atomic(self):
  for text in ['하나\n둘\n셋\n넷\n다섯','하나\t둘']:
   with patch('rename_ui.QMessageBox.information') as notice:self.paste(4,text);notice.assert_called_once()
   self.assertEqual([self.w.files.item(i).text(4) for i in range(4)],[p.name for p in self.paths])
 def test_real_editor_typing_multiline_paste_and_apply_undo(self):
  files=self.w.files;item=files.item(0);files.setCurrentItem(item,4);files.editItem(item,4);APP.processEvents()
  editor=APP.focusWidget();self.assertIsInstance(editor,QLineEdit);editor.setText('직접수정');QTest.keyClick(editor,Qt.Key_Return);APP.processEvents()
  self.assertEqual(item.text(4),'직접수정.PDF');files.editItem(item,4);APP.processEvents();editor=APP.focusWidget()
  APP.clipboard().setText('서울\n부산');QTest.keyClick(editor,Qt.Key_V,Qt.ControlModifier);APP.processEvents()
  self.assertEqual([files.item(i).text(4) for i in range(4)],['서울.PDF','부산.PDF','c.PDF','d.PDF'])
  self.panel.execute();self.assertTrue((self.root/'서울.PDF').exists());self.assertEqual((self.root/'부산.PDF').read_bytes(),b'b.PDF')
  self.panel.undo();self.assertTrue(all(p.exists() for p in self.paths))
 def test_manual_names_use_existing_collision_and_invalid_checks(self):
  self.paste(4,'중복\n중복');self.assertFalse(self.panel.run.isEnabled());self.assertIn('겹칩니다',self.w.files.item(0).text(5))
  self.paste(4,'bad/name\n안전');self.assertFalse(self.panel.run.isEnabled());self.assertTrue(all(p.exists() for p in self.paths))
 def test_number_defaults_dot_separator_and_unified_string_position(self):
  p=self.panel;self.assertEqual(p.digits.value(),1);p.number_enabled.setChecked(True);p.separator.setCurrentIndex(p.separator.findData('.'))
  self.assertEqual(self.w.files.item(0).text(4),'a.1.PDF');p.string.setText('추가');p.string_position.setCurrentIndex(1)
  self.assertEqual(self.w.files.item(0).text(4),'a.1추가.PDF');p.string_position.setCurrentIndex(2);p.string_marker.setText('.')
  self.assertEqual(self.w.files.item(0).text(4),'a추가.1.PDF')
  p.string_marker.setText('없는문자');self.assertFalse(p.run.isEnabled())
 def test_inline_text_editor_keeps_single_line_paste(self):
  self.panel.text_enabled.setChecked(True);files=self.w.files;item=files.item(0);item.setText(6,'앞');files.setCurrentItem(item,6);files.editItem(item,6);APP.processEvents()
  editor=APP.focusWidget();self.assertIsInstance(editor,QLineEdit);editor.deselect();editor.setCursorPosition(len(editor.text()));APP.clipboard().setText('뒤');QTest.keyClick(editor,Qt.Key_V,Qt.ControlModifier);QTest.keyClick(editor,Qt.Key_Return);APP.processEvents()
  self.assertEqual(item.text(6),'앞뒤');self.assertEqual(files.item(1).text(6),'')

 def test_independent_column_widths_and_compact_status(self):
  files=self.w.files;self.panel.text_enabled.setChecked(True);QTest.qWait(20)
  self.assertEqual(files.headerItem().text(6),'추가할 문자열')
  widths={column:files.columnWidth(column) for column in [2,4,5,6]}
  self.assertLess(widths[5],150)
  files.header().resizeSection(6,widths[6]+90);APP.processEvents()
  self.assertEqual(files.columnWidth(6),widths[6]+90)
  for column in [2,4,5]:self.assertEqual(files.columnWidth(column),widths[column])
  files.header().resizeSection(2,widths[2]+100);APP.processEvents()
  self.assertEqual(files.columnWidth(2),widths[2]+100);self.assertEqual(files.columnWidth(4),widths[4]);self.assertEqual(files.columnWidth(6),widths[6]+90)
  self.w.mode_tabs.setCurrentIndex(0);APP.processEvents();before=files.columnWidth(3);files.header().resizeSection(2,600);APP.processEvents();self.assertEqual(files.columnWidth(3),before)
 def test_file_strings_share_position_and_suspend_common_string(self):
  panel=self.panel;panel.string.setText('공통');panel.string_position.setCurrentIndex(1)
  self.assertEqual(self.w.files.item(0).text(4),'a공통.PDF')
  panel.assign_values(['하나','둘','셋','넷']);panel.text_enabled.setChecked(True)
  self.assertFalse(panel.string.isEnabled());self.assertEqual(self.w.files.item(0).text(4),'a하나.PDF')
  panel.string_position.setCurrentIndex(0);self.assertEqual(self.w.files.item(0).text(4),'하나a.PDF')
  panel.text_enabled.setChecked(False);self.assertTrue(panel.string.isEnabled());self.assertEqual(panel.string.text(),'공통');self.assertEqual(self.w.files.item(0).text(4),'공통a.PDF')
 def test_shared_marker_position_with_per_file_strings(self):
  panel=self.panel;panel.assign_values(['첫째','둘째','셋째','넷째']);panel.text_enabled.setChecked(True)
  panel.string_position.setCurrentIndex(3);panel.string_marker.setText('a')
  self.assertEqual(self.w.files.item(0).text(4),'a첫째.PDF');self.assertTrue(panel.string_marker.isVisible())
  panel.text_enabled.setChecked(False);panel.string.setText('공통');self.assertEqual(self.w.files.item(0).text(4),'a공통.PDF')
 def test_simple_summary_and_shared_row_layout(self):
  panel=self.panel;self.assertEqual(panel.message.text(),'0개 변경 예정 · 오류 0개')
  self.assertFalse(hasattr(panel,'replace_name'));self.assertFalse(hasattr(panel,'text_position'))
  self.assertGreaterEqual(panel.layout().contentsMargins().left(),20)
  panel.text_enabled.setChecked(True);APP.processEvents()
  self.assertGreater(panel.text_enabled.geometry().left(),panel.string.geometry().right())
  self.assertGreater(panel.string_position.geometry().left(),panel.text_enabled.geometry().right())
