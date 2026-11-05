import unittest,types,sys,ctypes,importlib.util,tempfile,os
from pathlib import Path
from unittest.mock import Mock, patch

class HotkeyTests(unittest.TestCase):
 def test_repeated_keys_and_exception_recovery(self):
  class Suppress(Exception): pass
  class Settings:
   def value(self,key,default,**kw): return '` (백틱)' if key=='hotkey' else default
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

class ToggleHotkeyTests(unittest.TestCase):
 def test_popup_toggle_matches_binding_focus_and_suppresses_repeats(self):
  class Settings:
   def value(self,key,default,**kw):return default
  foreground=[456];dismiss=[];mods=set()
  gui=types.SimpleNamespace(GetForegroundWindow=lambda:foreground[0],GetClassName=lambda hwnd:'QtWindow' if hwnd==456 else 'OtherWindow')
  api=types.SimpleNamespace(GetAsyncKeyState=lambda vk:0x8000 if vk in mods else 0)
  with tempfile.TemporaryDirectory() as d,patch.dict(os.environ,LOCALAPPDATA=d),patch.dict(sys.modules,{'winreg':types.ModuleType('winreg'),'win32gui':gui,'win32process':types.ModuleType('win32process')}),patch.object(ctypes,'windll',types.SimpleNamespace(user32=api),create=True):
   spec=importlib.util.spec_from_file_location('toggle_hook_module',Path(__file__).with_name('windows.py'));m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
   watcher=m.SelectionWatcher(lambda _:None,lambda _:None,Settings(),dismiss=lambda:dismiss.append(True));watcher.popup_windows=(123,456);watcher.popup_open=True
   suppressed=[];watcher.listener=types.SimpleNamespace(suppress_event=lambda:suppressed.append(True))
   for binding in m.KEYS.values():
    watcher.binding=binding;target,required=binding;mods.clear();mods.update(required)
    previous=len(dismiss)
    watcher.filter_event(0x100,types.SimpleNamespace(vkCode=target));watcher.filter_event(0x100,types.SimpleNamespace(vkCode=target));watcher.filter_event(0x101,types.SimpleNamespace(vkCode=target))
    self.assertEqual(len(dismiss),previous+1);self.assertTrue(watcher.jobs.empty());self.assertFalse(watcher.intercepted)
   foreground[0]=999;previous=len(dismiss)
   watcher.filter_event(0x100,types.SimpleNamespace(vkCode=target));self.assertEqual(len(dismiss),previous)
   for handler in watcher.log.handlers[:]:handler.close();watcher.log.removeHandler(handler)


class ExplorerSelectionOrderTests(unittest.TestCase):
    def test_file_selection_uses_explorer_view_order(self):
        native = types.SimpleNamespace(IID_IDataObject=object(), DVASPECT_CONTENT=1, TYMED_HGLOBAL=1)
        view = Mock()
        view.GetItemObject.return_value.GetData.return_value.data_handle = 42
        window = Mock()
        with tempfile.TemporaryDirectory() as directory, patch.dict(
            sys.modules,
            {"winreg": types.ModuleType("winreg"), "pythoncom": native,
             "win32con": types.SimpleNamespace(CF_HDROP=15)},
        ):
            spec = importlib.util.spec_from_file_location(
                "selection_order_test_module", Path(__file__).with_name("windows.py")
            )
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            folder = Path(directory) / "folder"
            folder.mkdir()
            first, last = str(Path(directory) / "3.pdf"), str(Path(directory) / "1.pdf")
            window.Document.SelectedItems.return_value = [
                types.SimpleNamespace(Path=last, IsFolder=False),
                types.SimpleNamespace(Path=first, IsFolder=False),
            ]
            with (
                patch.object(module, "shell_browser", return_value=Mock(
                    QueryActiveShellView=Mock(return_value=view))),
                patch.object(module, "drop_paths", return_value=[first, str(folder), last]) as read,
            ):
                self.assertEqual(module.selected_file_paths(window), [first, last])
                view.GetItemObject.assert_called_once_with(-2147483647, native.IID_IDataObject)
                read.assert_called_once_with(42)
                window.Document.SelectedItems.assert_not_called()
                view.GetItemObject.side_effect = RuntimeError("view order unavailable")
                self.assertEqual(module.selected_file_paths(window), [last, first])


class HotkeyForegroundTests(unittest.TestCase):
    def test_new_foreground_clears_stale_shortcut_state(self):
        with tempfile.TemporaryDirectory() as folder, patch.dict(os.environ, LOCALAPPDATA=folder):
            gui = Mock()
            gui.GetForegroundWindow.return_value = 123
            with patch.dict(sys.modules, {
                'winreg': types.ModuleType('winreg'), 'win32gui': gui,
                'win32process': types.ModuleType('win32process'),
            }):
                spec = importlib.util.spec_from_file_location(
                    'foreground_hook_test', Path(__file__).with_name('windows.py')
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                settings = Mock()
                settings.value.side_effect = lambda key, default, **kw: {
                    'hotkey_binding': '75,17,16'
                }.get(key, default)
                watcher = module.SelectionWatcher(lambda _: None, lambda _: None, settings)
                self.assertEqual(watcher.binding, (75, (17, 16)))
                watcher.key_window = 456
                watcher.intercepted.add(75)
                watcher.pressed.add(75)
                watcher.listener = Mock()
                with patch.object(watcher, 'on_press', return_value=True) as activate:
                    watcher.filter_event(0x100, types.SimpleNamespace(vkCode=75))
                activate.assert_called_once()
                watcher.listener.suppress_event.assert_called_once()
