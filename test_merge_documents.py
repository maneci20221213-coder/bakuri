import os,tempfile,unittest,zipfile
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from engine import convert,OfficeSession,can_merge
from merged_names import merged_path
from jobs import JobControl,Cancelled

class MergeTests(unittest.TestCase):
 def test_names(self):
  for names,expected in [(['사업_1.pdf','사업_2.pdf'],'사업_통합본.pdf'),(['1_보고서.pdf','2_보고서.pdf'],'보고서_통합본.pdf'),(['one.pdf','two.pdf'],'one 등 통합본.pdf')]:self.assertEqual(merged_path(names,'pdf').name,expected)
 def test_hancom_order_preservation_and_failure(self):
  for fail in [False,True]:
   with tempfile.TemporaryDirectory() as d:
    files=[Path(d)/n for n in ['문서_1.hwp','문서_2.hwpx']]
    for file in files:file.write_bytes(b'original')
    inserts=[];params={};cleared=[]
    def execute(p):inserts.append(dict(params));return not fail
    def save(path,*args):
     with zipfile.ZipFile(path,'w') as z:z.writestr('Contents/section0.xml','<section/>')
     return True
    app=SimpleNamespace(Clear=lambda value:cleared.append(value),Open=lambda *args:True,HAction=SimpleNamespace(Run=lambda name:True),SaveAs=save,CreateAction=lambda name:SimpleNamespace(CreateSet=lambda:SimpleNamespace(SetItem=params.__setitem__),GetDefault=lambda p:None,Execute=execute))
    control=JobControl()
    with patch.object(OfficeSession,'hwp',return_value=app):
     if fail:
      with self.assertRaises(RuntimeError):convert(files,'hwpx',True,control=control)
      self.assertEqual(control.outputs,[])
     else:
      out=convert(files,'hwpx',True);self.assertEqual(Path(out[0]).name,'문서_통합본.hwpx')
    self.assertEqual(Path(inserts[0]['FileName']),files[1]);self.assertEqual(inserts[0]['KeepSection'],1);self.assertEqual(inserts[0]['KeepStyle'],1)
    self.assertEqual(cleared,[1,1]);self.assertEqual([p.read_bytes() for p in files],[b'original']*2)
 def test_window_and_popup(self):
  from PySide6.QtWidgets import QApplication,QSystemTrayIcon
  from app import Window,QuickPopup
  application=QApplication.instance() or QApplication([])
  w=Window();popup=QuickPopup(animate=False)
  try:
   popup.present(['a.hwp','b.hwpx']);self.assertEqual(popup.actions['pdf'],'hwp_merge')
   for key in ['png','jpeg','more']:self.assertEqual(popup.buttons[key].size(),popup.buttons['pdf'].size())
   with tempfile.TemporaryDirectory() as d:
    a=Path(d)/'a.pdf';a.touch();w.files.add_paths([str(a)])
    w.showMinimized();w.quick_paths=[str(a)];w.quick_selected('more');self.assertFalse(w.isMinimized());self.assertEqual(w.files.count(),1)
    with patch.object(QSystemTrayIcon,'isSystemTrayAvailable',return_value=True):w.close()
    self.assertEqual(w.files.count(),0)
  finally:popup.hide();w.tray.hide();w.deleteLater()
