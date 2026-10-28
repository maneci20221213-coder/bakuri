import unittest,types,sys,ctypes,importlib.util,tempfile,os
from pathlib import Path
from unittest.mock import patch

class HotkeyTests(unittest.TestCase):
 def test_repeated_keys_and_exception_recovery(self):
  class Suppress(Exception): pass
  class Settings:
   def value(self,key,default,**kw): return default
  fakegui=types.SimpleNamespace(GetForegroundWindow=lambda:123,GetClassName=lambda hwnd:'CabinetWClass')
  fakeprocess=types.SimpleNamespace(GetWindowThreadProcessId=lambda hwnd:(1,1))
  api=types.SimpleNamespace(GetAsyncKeyState=lambda vk:0,GetGUIThreadInfo=lambda *a:False)
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,LOCALAPPDATA=d),patch.dict(sys.modules,{'winreg':types.ModuleType('winreg'),'win32gui':fakegui,'win32process':fakeprocess}),patch.object(ctypes,'windll',types.SimpleNamespace(user32=api),create=True):
   spec=importlib.util.spec_from_file_location('hotkey_test_module',Path(__file__).with_name('windows.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
   watcher=m.SelectionWatcher(lambda _:None,lambda _:None,Settings())
   class Listener:
    def suppress_event(self): raise Suppress()
   watcher.listener=Listener()
   for i in range(200):
    with self.assertRaises(Suppress):watcher.filter_event(0x100,types.SimpleNamespace(vkCode=0xC0))
    with self.assertRaises(Suppress):watcher.filter_event(0x101,types.SimpleNamespace(vkCode=0xC0))
   self.assertFalse(watcher.pressed);self.assertFalse(watcher.intercepted);self.assertLessEqual(watcher.jobs.qsize(),8)
   dismiss=[];watcher.dismiss=lambda:dismiss.append(True);watcher.popup_open=True
   with self.assertRaises(Suppress):watcher.filter_event(0x100,types.SimpleNamespace(vkCode=0x1B))
   watcher.popup_open=False
   with self.assertRaises(Suppress):watcher.filter_event(0x101,types.SimpleNamespace(vkCode=0x1B))
   self.assertEqual(dismiss,[True])
   fakegui.GetClassName=lambda _:(_ for _ in ()).throw(OSError('window disappeared'))
   self.assertTrue(watcher.filter_event(0x100,types.SimpleNamespace(vkCode=0xC0)));self.assertTrue(watcher.restart.is_set())
   for handler in watcher.log.handlers[:]:handler.close();watcher.log.removeHandler(handler)

class PopupHookTests(unittest.TestCase):
 def test_popup_keys_forward_once_and_only_for_origin(self):
  class Suppress(Exception):pass
  class Settings:
   def value(self,key,default,**kw):return default
  foreground=[123];gui=types.SimpleNamespace(GetForegroundWindow=lambda:foreground[0]);keys=[]
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,LOCALAPPDATA=d),patch.dict(sys.modules,{'winreg':types.ModuleType('winreg'),'win32gui':gui}):
   spec=importlib.util.spec_from_file_location('popup_hook_module',Path(__file__).with_name('windows.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
   watcher=m.SelectionWatcher(lambda _:None,lambda _:None,Settings(),popup_key=keys.append);watcher.popup_windows=(123,456);watcher.popup_open=True
   class Listener:
    def suppress_event(self):raise Suppress()
   watcher.listener=Listener()
   for i in range(100):
    for vk in [0x26,0x25,0x27,0x28,0x09,0x0D,0x20]:
     previous=len(keys)
     with self.assertRaises(Suppress):watcher.filter_event(0x100,types.SimpleNamespace(vkCode=vk))
     with self.assertRaises(Suppress):watcher.filter_event(0x100,types.SimpleNamespace(vkCode=vk))
     self.assertEqual(len(keys),previous+1)
     watcher.popup_open=False
     with self.assertRaises(Suppress):watcher.filter_event(0x101,types.SimpleNamespace(vkCode=vk))
     watcher.popup_open=True
   self.assertFalse(watcher.intercepted)
   previous=len(keys);foreground[0]=999
   self.assertTrue(watcher.filter_event(0x100,types.SimpleNamespace(vkCode=0x26)));self.assertEqual(len(keys),previous)
   for handler in watcher.log.handlers[:]:handler.close();watcher.log.removeHandler(handler)
