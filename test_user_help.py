import os,tempfile,unittest,logging
os.environ['QT_QPA_PLATFORM']='offscreen'
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication,QPushButton
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from app import Window
from help_ui import HelpDialog
from user_messages import friendly_error,MESSAGES
APP=QApplication.instance() or QApplication([])

class HelpTests(unittest.TestCase):
 def test_help_button_beside_settings_and_f1_open_manual_without_update_check(self):
  w=Window();w.show();w.activateWindow();APP.processEvents()
  settings=w.findChild(QPushButton,'settings')
  self.assertEqual(w.help_button.text(),'?');self.assertGreaterEqual(w.help_button.x(),settings.geometry().right())
  with patch('app.HelpDialog') as dialog,patch.object(w.updater,'request') as check:
   QTest.mouseClick(w.help_button,Qt.LeftButton);QTest.keyClick(w,Qt.Key_F1)
   self.assertEqual(dialog.return_value.exec.call_count,2);check.assert_not_called()
  w.tray.hide();w.hide();w.deleteLater()
 def test_offline_manual_includes_saving_and_limits_and_can_scroll(self):
  dialog=HelpDialog();dialog.show();APP.processEvents();text=dialog.text.toPlainText()
  for phrase in ['원본 파일이 있는 폴더','회색','한 파일로 합쳐서 저장','OCR','용량 축소','완전 종료','잘 안 될 때']:
   self.assertIn(phrase,text)
  self.assertGreater(dialog.text.verticalScrollBar().maximum(),0);dialog.reject()
 def test_developer_readme_retained_and_manual_bundled_in_both_builds(self):
  root=Path(__file__).parent
  self.assertIn('## 빌드·배포',(root/'DEVELOPER-README.md').read_text(encoding='utf-8'))
  self.assertNotIn('py -3.12',(root/'README.md').read_text(encoding='utf-8'))
  for name in ['build_release.ps1','build_exe.bat']:self.assertIn('USER-GUIDE.md;.',(root/name).read_text(encoding='utf-8'))

class UserMessageTests(unittest.TestCase):
 def test_user_messages_hide_technical_details_and_offer_a_next_step(self):
  cases=[(PermissionError('WIN32 SECRET stack'),'conversion','permission'),
         (FileNotFoundError('/private/document.pdf'),'conversion','missing'),
         (RuntimeError('HWPX 구역 목록을 찾지 못했습니다.'),'conversion','hwp'),
         (RuntimeError('COM -2147221164'),'conversion','office'),
         (ValueError('암호가 있는 PDF는 지원하지 않습니다.'),'conversion','password'),
         (RuntimeError('HTTP 503 token=SECRET'),'update_download','update_download'),
         (RuntimeError('unhandled backend details'),'compression','compression')]
  with patch('user_messages.log_error') as log:
   for error,context,expected in cases:
    self.assertEqual(friendly_error(error,context),MESSAGES[expected])
    self.assertNotIn('SECRET',friendly_error(error,context))
   self.assertGreater(log.call_count,0)
 def test_diagnostics_preserved_locally_and_already_friendly_text_is_stable(self):
  logger=logging.getLogger('bakuri.errors');old=logger.handlers[:];logger.handlers=[]
  try:
   with tempfile.TemporaryDirectory() as folder,patch.dict(os.environ,LOCALAPPDATA=folder):
    message=friendly_error(RuntimeError('internal stack: unique-test-marker'))
    self.assertNotIn('unique-test-marker',message)
    self.assertIn('unique-test-marker',(Path(folder)/'Bakuri'/'errors.log').read_text(encoding='utf-8'))
    self.assertEqual(friendly_error(message),message)
    for h in logger.handlers:h.close()
    logger.handlers=[]
  finally:
   for h in logger.handlers:h.close()
   logger.handlers=old
 def test_job_result_dialog_never_shows_raw_exception(self):
  w=Window()
  with patch('app.QMessageBox.warning') as warning,patch('user_messages.log_error'):
   w.finished(dict(paths=[],rows=[],outcome='failed',error='COM SECRET trace',kind='convert'))
   self.assertNotIn('SECRET',warning.call_args.args[2]);self.assertIn('원본',warning.call_args.args[2])
  w.tray.hide();w.hide();w.deleteLater()
