import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import unittest,tempfile,types
from unittest.mock import Mock,patch
from PySide6.QtWidgets import QApplication,QWidget,QLabel,QDialog
from PySide6.QtCore import QSettings
from updater import UpdateController,UpdatePrompt
APP=QApplication.instance() or QApplication([])
class UpdateTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.settings=QSettings(self.tmp.name+'/s.ini',QSettings.IniFormat)
  self.window=QWidget();self.window.busy=False;self.window.status=QLabel();self.window.show()
  self.updater=UpdateController(self.window,self.settings);self.manager=Mock()
 def tearDown(self):self.window.close();self.tmp.cleanup()
 def result(self,v):return self.manager,types.SimpleNamespace(TargetFullRelease=types.SimpleNamespace(Version=v))
 def test_no_background_or_popup_network(self):
  with patch('updater.feed_url') as feed:
   for reason in ['background','popup','shell']:self.updater.request(reason)
   feed.assert_not_called()
 def test_decline_no_download_repeat_suppressed(self):
  with patch('updater.UpdatePrompt') as prompt:
   prompt.return_value.exec.return_value=QDialog.Rejected;prompt.return_value.skip.isChecked.return_value=False
   self.updater.on_checked(self.result('1.0.0'));self.updater.on_checked(self.result('1.0.0'))
   self.assertEqual(prompt.call_count,1);self.manager.download_updates.assert_not_called()
 def test_skipped_version_persists_next_version_offered(self):
  with patch('updater.UpdatePrompt') as prompt:
   prompt.return_value.exec.return_value=QDialog.Rejected;prompt.return_value.skip.isChecked.return_value=True
   self.updater.on_checked(self.result('1.0.0'));self.assertEqual(self.settings.value('update_skipped_version'),'1.0.0')
   other=UpdateController(self.window,self.settings);other.on_checked(self.result('1.0.0'));self.assertEqual(prompt.call_count,1)
   other.on_checked(self.result('1.1.0'));self.assertEqual(prompt.call_count,2)
 def test_approval_required_for_download(self):
  with patch('updater.UpdatePrompt') as prompt:
   prompt.return_value.exec.return_value=QDialog.Accepted;prompt.return_value.skip.isChecked.return_value=False
   self.updater.on_checked(self.result('1.0.0'));self.updater.worker.join(2)
   self.manager.download_updates.assert_called_once();self.assertTrue(self.updater.installing)
 def test_checkbox_disables_install(self):
  dialog=UpdatePrompt('1.0');dialog.skip.setChecked(True);self.assertFalse(dialog.install.isEnabled())
 def test_background_bootstrap_disables_auto_apply(self):
  import velopack_bootstrap
  sdk=Mock();sdk.App.return_value.set_auto_apply_on_startup.return_value=sdk.App.return_value
  with patch.dict('sys.modules',{'velopack':sdk}):velopack_bootstrap.bootstrap()
  sdk.App.return_value.set_auto_apply_on_startup.assert_called_once_with(False)

class GithubDistributionTests(unittest.TestCase):
 def test_public_github_source_no_token_and_no_prereleases(self):
  import updater,json
  with tempfile.TemporaryDirectory() as folder:
   p=__import__('pathlib').Path(folder)/'config.json';p.write_text(json.dumps({'source':'github','url':'https://github.com/example/bakuri'}))
   sdk=Mock()
   with patch('updater.config_path',return_value=p),patch.dict('sys.modules',{'velopack':sdk}):
    url=updater.feed_url();updater.make_update_manager(url)
   sdk.GithubSource.assert_called_once_with('https://github.com/example/bakuri',access_token=None,prerelease=False)
   sdk.UpdateManager.assert_called_once_with(sdk.GithubSource.return_value)
 def test_rejects_credentials_and_non_repository_github_url(self):
  import updater,json
  from pathlib import Path
  cases=['http://github.com/owner/repo','https://token@github.com/owner/repo','https://github.com/owner/repo?token=secret','https://github.com/owner/repo/releases','https://other.example/owner/repo']
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'config.json'
   for url in cases:
    p.write_text(json.dumps({'source':'github','url':url}))
    with patch('updater.config_path',return_value=p),self.assertRaises(ValueError):updater.feed_url()
 def test_explicit_entry_deduplicated_for_five_minutes(self):
  window=QWidget();window.busy=False;window.status=QLabel();window.show()
  settings=QSettings('BakuriTest','cooldown');manager=UpdateController(window,settings)
  with patch('updater.feed_url',return_value=''),patch('updater.time.monotonic',side_effect=[100,101,401]):
   manager.request('direct');manager.worker.join(2);manager.checking=False
   first=manager.worker;manager.request('expanded');self.assertIs(manager.worker,first)
   manager.request('expanded');manager.worker.join(2);self.assertIsNot(manager.worker,first)
  window.close()
