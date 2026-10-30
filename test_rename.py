import json,os,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from rename_engine import preview,apply,undo,identity

class RenameTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name).resolve();self.journal=self.root/'history.json'
 def file(self,name,content=b'content'):
  p=self.root/name;p.write_bytes(content);return p
 def test_preview_and_apply_keep_extensions_bytes_and_order(self):
  a=self.file('사진_복사본.PNG',b'a');b=self.file('사진_두번째.jpg',b'b')
  rows=preview([b,a],base='현장',prefix='2026_',suffix='_제출',start=8,digits=3)
  self.assertEqual([r['name'] for r in rows],['2026_현장_008_제출.jpg','2026_현장_009_제출.PNG'])
  self.assertTrue(a.exists());result=apply(rows,self.journal)
  self.assertFalse(a.exists());self.assertEqual([Path(e['current']).read_bytes() for e in result],[b'b',b'a'])
  undo(self.journal);self.assertEqual(a.read_bytes(),b'a');self.assertEqual(b.read_bytes(),b'b')
 def test_remove_and_add(self):
  a=self.file('보고서 복사본.pdf');r=preview([a],find=' 복사본',replace='',prefix='최종_',suffix='_제출')[0]
  self.assertEqual(r['name'],'최종_보고서_제출.pdf')
 def test_collisions_and_invalid_names(self):
  a=self.file('a.pdf');b=self.file('b.pdf');self.file('new_a.pdf')
  self.assertTrue(preview([a],prefix='new_')[0]['error'])
  self.assertTrue(all(r['error'] for r in preview([a,b],find='b',replace='a')))
  for value in ['CON','COM¹','LPT2','bad/name','bad:name','x'*260]:
   rows=preview([a],find='a',replace=value);self.assertTrue(rows[0]['error'],value)
   with self.assertRaises(ValueError):apply(rows,self.journal)
  self.assertTrue(a.exists());self.assertTrue(b.exists())
 def test_swap_case_and_undo_without_overwrite(self):
  a=self.file('a.pdf',b'a');b=self.file('b.pdf',b'b');rows=preview([a,b])
  for r,target in zip(rows,[b,a]):r.update(target=str(target),name=target.name,changed=True)
  apply(rows,self.journal);self.assertEqual(a.read_bytes(),b'b');self.assertEqual(b.read_bytes(),b'a')
  undo(self.journal);self.assertEqual(a.read_bytes(),b'a');self.assertEqual(b.read_bytes(),b'b')
  rows=preview([a],find='a',replace='A');apply(rows,self.journal);self.assertTrue((self.root/'A.pdf').exists());undo(self.journal);self.assertTrue(a.exists())
 def test_stale_preview_and_modified_undo_are_rejected(self):
  a=self.file('a.pdf');rows=preview([a],prefix='new_');a.write_bytes(b'changed')
  # A same-size write may share the old clock tick on Windows. Make the
  # metadata change explicit instead of depending on execution timing.
  changed_time=rows[0]['identity'][-1]+1_000_000_000;os.utime(a,ns=(changed_time,changed_time))
  with self.assertRaises(ValueError):apply(rows,self.journal)
  rows=preview([a],prefix='new_');apply(rows,self.journal);new=self.root/'new_a.pdf';new.write_bytes(b'modified')
  with self.assertRaises(ValueError):undo(self.journal)
  self.assertEqual(new.read_bytes(),b'modified')
 def test_undo_refuses_external_destination(self):
  a=self.file('a.pdf');apply(preview([a],prefix='new_'),self.journal);a.write_bytes(b'external')
  with self.assertRaises(ValueError):undo(self.journal)
  self.assertEqual(a.read_bytes(),b'external')
 def test_partial_failure_rolls_back_and_does_not_overwrite(self):
  import bakuri.renaming.transaction
  a=self.file('a.pdf',b'a');b=self.file('b.pdf',b'b');real=bakuri.renaming.transaction.move;calls=[]
  def failing(src,dst):
   calls.append(dst)
   if len(calls)==4:raise PermissionError('locked')
   return real(src,dst)
  with patch('bakuri.renaming.transaction.move',side_effect=failing),self.assertRaises(RuntimeError):apply(preview([a,b],prefix='new_'),self.journal)
  self.assertEqual(a.read_bytes(),b'a');self.assertEqual(b.read_bytes(),b'b');self.assertFalse(list(self.root.glob('.bakuri-rename-*')))
  self.assertEqual(json.loads(self.journal.read_text())['state'],'rolled_back')
 def test_same_names_across_folders_and_noop(self):
  folders=[self.root/'one',self.root/'two']
  for folder in folders:folder.mkdir();(folder/'a.pdf').write_bytes(b'x')
  paths=[folder/'a.pdf' for folder in folders]
  rows=preview(paths,prefix='new_');self.assertFalse(any(r['error'] for r in rows));apply(rows,self.journal)
  self.assertTrue(all((folder/'new_a.pdf').exists() for folder in folders))
  self.assertEqual(apply(preview([folders[0]/'new_a.pdf']),self.journal),[])

os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt
from app import Window
from build_channel import DEVELOPMENT,SETTINGS_APP
from version import VERSION
APP=QApplication.instance() or QApplication([])
class RenameUiTests(unittest.TestCase):
 def test_preview_checkbox_apply_undo_and_development_isolation(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d).resolve();a=root/'자료.txt';b=root/'다른.txt';a.write_bytes(b'a');b.write_bytes(b'b');w=Window()
   try:
    self.assertIn(VERSION,w.windowTitle());self.assertEqual('개발용' in w.windowTitle(),DEVELOPMENT);self.assertEqual(w.settings.applicationName(),SETTINGS_APP);self.assertEqual(w.updater.disabled,DEVELOPMENT)
    w.rename_panel.journal=root/'history.json';w.files.add_paths([str(a),str(b)]);w.files.item(1).setCheckState(0,Qt.Unchecked)
    w.mode_tabs.setCurrentIndex(1);w.rename_panel.string.setText('최종_')
    self.assertEqual(w.files.item(0).text(4),'최종_자료.txt');self.assertEqual(w.files.item(1).text(4),'')
    w.rename_panel.execute();self.assertTrue((root/'최종_자료.txt').exists());self.assertTrue(b.exists());self.assertEqual(w.files.item(0).data(0,Qt.UserRole),str(root/'최종_자료.txt'))
    w.rename_panel.undo();self.assertTrue(a.exists());self.assertEqual(w.files.item(0).data(0,Qt.UserRole),str(a))
    w.mode_tabs.setCurrentIndex(0);self.assertTrue(w.files.isColumnHidden(4));self.assertFalse(w.files.isColumnHidden(1))
   finally:w.tray.hide();w.hide();w.deleteLater()
