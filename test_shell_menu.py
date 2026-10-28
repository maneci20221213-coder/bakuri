import unittest,types,sys,importlib.util,ctypes
from pathlib import Path
from unittest.mock import patch
from engine import SUPPORTED

class Key:
 def __init__(self,path):self.path=path
 def __enter__(self):return self
 def __exit__(self,*args):pass
class Registry:
 HKEY_CURRENT_USER=1;REG_SZ=1
 def __init__(self):self.tree={}
 def CreateKey(self,root,path):
  parts=path.split('\\')
  for i in range(1,len(parts)+1):self.tree.setdefault('\\'.join(parts[:i]),{})
  return Key(path)
 def OpenKey(self,root,path):
  if path not in self.tree:raise FileNotFoundError(path)
  return Key(path)
 def SetValueEx(self,key,name,_,kind,value):self.tree[key.path][name]=value
 def QueryValueEx(self,key,name):return self.tree[key.path][name],1
 def EnumKey(self,key,index):
  children=sorted(p[len(key.path)+1:] for p in self.tree if p.startswith(key.path+'\\') and '\\' not in p[len(key.path)+1:])
  if index>=len(children):raise OSError('end')
  return children[index]
 def DeleteKey(self,root,path):
  if path not in self.tree:raise FileNotFoundError(path)
  if any(p.startswith(path+'\\') for p in self.tree):raise OSError('has children')
  del self.tree[path]

class ShellMenuTests(unittest.TestCase):
 def test_legacy_migration_and_disable_preserve_other_verbs(self):
  registry=Registry();root=r'Software\Classes\SystemFileAssociations\.pdf\shell'
  for verb in ['BakuriConvert','BakuriPythonTrial','OtherApplication']:
   registry.SetValueEx(registry.CreateKey(1,root+'\\'+verb),'',0,1,verb)
   registry.CreateKey(1,root+'\\'+verb+r'\command')
  registry.CreateKey(1,r'Software\Classes\.pdf\OpenWithProgids')
  # Also clean a stale extension no longer in the supported list.
  stale=r'Software\Classes\SystemFileAssociations\.oldbakuri\shell\BakuriConvert';registry.CreateKey(1,stale+r'\command')
  notices=[]
  with patch.dict(sys.modules,{'winreg':registry}),patch.object(ctypes,'windll',types.SimpleNamespace(shell32=types.SimpleNamespace(SHChangeNotify=lambda *args:notices.append(args))),create=True):
   spec=importlib.util.spec_from_file_location('shell_test_windows',Path(__file__).with_name('windows.py'));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
   self.assertTrue(module.migrate_menu(True));self.assertNotIn(stale,registry.tree)
   self.assertNotIn(root+r'\BakuriConvert',registry.tree)
   for ext in SUPPORTED:
    path=r'Software\Classes\SystemFileAssociations'+chr(92)+ext+r'\shell\BakuriPythonTrial'
    self.assertEqual(registry.tree[path][''],'바꾸리 파일 변환')
    self.assertIn(' --add-files "%1"',registry.tree[path+r'\command'][''])
    self.assertIn('pythonw.exe',registry.tree[path+r'\command'][''])
   self.assertIn(root+r'\OtherApplication\command',registry.tree)
   module.register_menu(False)
   self.assertFalse(any(p.endswith('\\BakuriPythonTrial') or p.endswith('\\BakuriConvert') for p in registry.tree))
   self.assertIn(root+r'\OtherApplication\command',registry.tree);self.assertIn(r'Software\Classes\.pdf\OpenWithProgids',registry.tree)
   self.assertFalse(module.migrate_menu(False));self.assertEqual(len(notices),3)

 def test_clean_machine_registration_and_explicit_disable(self):
  registry=Registry()
  with patch.dict(sys.modules,{'winreg':registry}),patch.object(ctypes,'windll',types.SimpleNamespace(shell32=types.SimpleNamespace(SHChangeNotify=lambda *a:None)),create=True):
   spec=importlib.util.spec_from_file_location('clean_shell',Path(__file__).with_name('windows.py'));module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
   self.assertTrue(module.migrate_menu(True))
   verbs=[p for p in registry.tree if p.endswith('\\BakuriPythonTrial')]
   self.assertEqual(len(verbs),len(SUPPORTED))
   self.assertTrue(module.migrate_menu(True))
   self.assertEqual(len([p for p in registry.tree if p.endswith('\\BakuriPythonTrial')]),len(SUPPORTED))
   self.assertFalse(module.migrate_menu(False))
   self.assertFalse(any(p.endswith('\\BakuriPythonTrial') for p in registry.tree))
