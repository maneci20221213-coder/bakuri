import ctypes,importlib.util,os,sys,tempfile,types,unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtCore import QSettings,Qt
from PySide6.QtWidgets import QApplication,QPushButton
from PIL import Image
from app import Window
from file_list import Files

APP=QApplication.instance() or QApplication([])

class RefactorTests(unittest.TestCase):
 def test_toolbar_buttons_have_same_size_even_when_focused(self):
  w=Window();w.show();APP.processEvents()
  settings=w.findChild(QPushButton,'settings')
  for button in (settings,w.help_button):
   button.setFocus();APP.processEvents()
   self.assertEqual(settings.size(),w.help_button.size())
   self.assertEqual(settings.width(),40);self.assertEqual(settings.height(),40)
  w.tray.hide();w.hide();w.deleteLater()
 def test_duplicate_batches_keep_order_and_can_readd_removed_files(self):
  with tempfile.TemporaryDirectory() as d:
   paths=[Path(d)/f'{i}.png' for i in range(8)]
   for p in paths:Image.new('RGB',(4,4)).save(p)
   files=Files();files.add_paths([str(p) for p in paths+paths])
   self.assertEqual(files.checked_paths(),[str(p.resolve()) for p in paths])
   files.takeItem(0);files.add_paths([str(paths[0])])
   self.assertEqual(files.checked_paths(),[str(p.resolve()) for p in paths[1:]+paths[:1]])
   files.deleteLater()
 def load_windows(self):
  spec=importlib.util.spec_from_file_location('refactor_windows',Path(__file__).with_name('windows.py'))
  module=importlib.util.module_from_spec(spec)
  with patch.dict(sys.modules,winreg=types.ModuleType('winreg')):spec.loader.exec_module(module)
  return module
 def test_startup_default_and_saved_or_external_disable_are_preserved(self):
  windows=self.load_windows()
  with tempfile.TemporaryDirectory() as d:
   settings=QSettings(str(Path(d)/'prefs.ini'),QSettings.IniFormat)
   with patch.object(windows,'set_startup') as write,patch.object(windows,'startup_enabled',return_value=False):
    windows.initialize_startup(settings)
    write.assert_called_once_with(True);self.assertTrue(settings.value('startup_enabled',type=bool))
    write.reset_mock();settings.setValue('startup_enabled',False)
    windows.initialize_startup(settings);write.assert_not_called()
    settings.clear();windows.initialize_startup(settings,first_run=False)
    write.assert_called_once_with(False);self.assertFalse(settings.value('startup_enabled',type=bool))
 def test_installer_shortcut_choice_is_explicit_and_targets_stable_launcher(self):
  windows=self.load_windows()
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);(root/'current').mkdir();desktop=root/'Desktop';desktop.mkdir()
   for p in (root/'Update.exe',root/'BakuriFileConverter.exe'):p.touch()
   link=desktop/'바꾸리.lnk'
   shortcut=types.SimpleNamespace(TargetPath=str(root/'BakuriFileConverter.exe'),Save=lambda:link.touch())
   shell=types.SimpleNamespace(SpecialFolders=lambda _:str(desktop),CreateShortcut=lambda _:shortcut)
   com=types.SimpleNamespace(CoInitialize=lambda:None,CoUninitialize=lambda:None)
   client=types.SimpleNamespace(Dispatch=lambda _:shell)
   with patch.dict(sys.modules,{'pythoncom':com,'win32com':types.SimpleNamespace(client=client),'win32com.client':client}),patch.object(sys,'frozen',True,create=True),patch.object(sys,'executable',str(root/'current'/'BakuriFileConverter.exe')):
    windows.apply_install_options([]);self.assertFalse(link.exists())
    windows.apply_install_options(['--desktop-shortcut=1']);self.assertTrue(link.exists())
    self.assertEqual(shortcut.TargetPath,str(root/'BakuriFileConverter.exe'))
    windows.apply_install_options(['--desktop-shortcut=0']);self.assertFalse(link.exists())
    link.touch();shortcut.TargetPath=str(root/'another-app.exe')
    windows.apply_install_options(['--desktop-shortcut=0']);self.assertTrue(link.exists())
