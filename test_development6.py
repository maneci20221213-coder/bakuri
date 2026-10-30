import os,tempfile,types,unittest
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
from unittest.mock import Mock,patch
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication
from file_names import name_lines
from file_list import Files
from settings_ui import SettingsDialog
from app import Window
APP=QApplication.instance() or QApplication([])

class NameDisplayTests(unittest.TestCase):
 def test_three_lines_keep_full_unicode_name_when_it_fits(self):
  text='서울지역_연간사업실적_검토자료_😀.pdf';font=APP.font().toString()
  lines=name_lines(text,font,140)
  self.assertLessEqual(len(lines),3);self.assertGreater(len(lines),1);self.assertEqual(''.join(lines),text)
  long=name_lines('긴파일명'*100+'.pdf',font,140)
  self.assertEqual(len(long),3);self.assertIn('…',long[-1])
 def test_fit_names_inside_viewport_and_wrap_without_changing_data(self):
  with tempfile.TemporaryDirectory() as d:
   f=Files(allow_all=True);f.setColumnCount(6);f.headerItem().setText(4,'변경될 이름');f.resize(1050,350)
   original='자료_'+'abcdefghij'*11+'.pdf';path=Path(d)/original;path.touch()
   f.add_paths([str(path)]);f.item(0).setText(4,'최종_'+original);f.setColumnHidden(1,True);f.setColumnHidden(3,True);f.setColumnWidth(5,95);f.show()
   try:
    for _ in range(3):APP.processEvents()
    f.fit_name_columns();APP.processEvents()
    self.assertLessEqual(sum(f.columnWidth(c) for c in [0,2,4,5]),f.viewport().width())
    self.assertGreater(f.columnWidth(4),250);self.assertEqual(f.item(0).text(2),original)
    self.assertEqual(f.item(0).data(0,Qt.UserRole),str(path));self.assertEqual(f.item(0).text(4),'최종_'+original)
    before=f.columnWidth(4);f.header().resizeSection(2,f.columnWidth(2)-50);APP.processEvents();self.assertEqual(f.columnWidth(4),before)
    f.resize(1250,350)
    for _ in range(3):APP.processEvents()
    self.assertGreater(f.columnWidth(4),before)
    self.assertGreaterEqual(f.visualItemRect(f.item(0)).height(),60)
   finally:f.hide();f.deleteLater()
 def test_row_height_grows_for_three_lines_and_shrinks_on_widening(self):
  from PySide6.QtWidgets import QTreeWidgetItem
  f=Files();f.setStyleSheet(f.styleSheet()+'QTreeWidget {font-size:20px;}');f.resize(800,300);f.addTopLevelItem(QTreeWidgetItem(['','','x'*50+'.pdf','']))
  f.setColumnHidden(1,True);f.setColumnHidden(3,True);f.show();APP.processEvents()
  try:
   f.fit_timer.stop();f.setColumnWidth(2,145);f.reflow_names();APP.processEvents();small=f.visualItemRect(f.item(0)).height()
   f.setColumnWidth(2,650);f.reflow_names();APP.processEvents();wide=f.visualItemRect(f.item(0)).height()
   self.assertGreater(small,wide);self.assertGreaterEqual(wide,60)
  finally:f.hide();f.deleteLater()

class DeveloperHotkeyTests(unittest.TestCase):
 def test_developer_starts_selection_and_mouse_hooks_without_registry_changes(self):
  fake=types.ModuleType('windows');fake.SelectionWatcher=Mock();fake.MouseWatcher=Mock();fake.initialize_startup=Mock();fake.migrate_menu=Mock()
  with patch.dict('sys.modules',{'windows':fake}),patch.dict(os.environ,BAKURI_DISABLE_SHELL_INTEGRATION='0'),patch('app.sys.platform','win32'):
   w=Window()
   try:
    fake.SelectionWatcher.return_value.start.assert_called_once();fake.MouseWatcher.return_value.start.assert_called_once()
    fake.initialize_startup.assert_not_called();fake.migrate_menu.assert_not_called()
    self.assertTrue(w.updater.disabled)
    w.popup.origin=123;w.popup_visibility(True)
    self.assertTrue(w.watcher.popup_open);self.assertEqual(w.watcher.popup_windows[0],123)
   finally:w.tray.hide();w.hide();w.deleteLater()
 def test_hotkey_settings_are_enabled_and_default_is_distinct(self):
  from build_channel import DEFAULT_HOTKEY
  self.assertEqual(DEFAULT_HOTKEY,'F9');w=Window()
  try:
   dialog=SettingsDialog(w);self.assertTrue(dialog.enabled.isEnabled());self.assertTrue(dialog.key.isEnabled());self.assertFalse(dialog.auto.isEnabled());self.assertFalse(dialog.explorer.isEnabled());dialog.reject()
  finally:w.tray.hide();w.hide();w.deleteLater()
