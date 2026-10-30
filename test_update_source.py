import hashlib,json,tempfile,types,unittest
from pathlib import Path
from unittest.mock import Mock
from update_source import PublicReleaseManager
from update_transport import validate_url

class PublicSourceTests(unittest.TestCase):
 def setUp(self):
  self.payload=b'verified test package';self.calls=[]
  self.asset=dict(PackageId='Bakuri.FileConverter',Version='0.14.8',Type='Full',FileName='Bakuri.FileConverter-0.14.8-stable-full.nupkg',Size=len(self.payload),SHA256=hashlib.sha256(self.payload).hexdigest())
  self.info=types.SimpleNamespace(TargetFullRelease=types.SimpleNamespace(**self.asset))
  self.sdk=Mock();self.sdk.check_for_updates.return_value=self.info
 def fetch(self,url,path,limit):
  self.calls.append(url)
  Path(path).write_bytes(json.dumps({'Assets':[self.asset]}).encode() if url.endswith('.json') else self.payload)
 def manager(self,fetch=None):
  manager=PublicReleaseManager('https://github.com/example/bakuri',sdk_factory=lambda source:self.sdk,downloader=fetch or self.fetch)
  self.addCleanup(manager.folder.cleanup);return manager
 def test_check_does_not_download_package_and_download_pins_checked_version(self):
  manager=self.manager();self.assertIs(manager.check_for_updates(),self.info)
  self.assertEqual(self.calls,['https://github.com/example/bakuri/releases/latest/download/releases.stable.json'])
  manager.download_updates(self.info)
  self.assertIn('/releases/download/v0.14.8/',self.calls[-1]);self.assertEqual((manager.cache/self.asset['FileName']).read_bytes(),self.payload)
  self.sdk.download_updates.assert_called_once_with(self.info)
  manager.apply_updates_and_restart(self.info);self.sdk.apply_updates_and_restart.assert_called_once_with(self.info)
 def test_corrupt_or_partial_download_never_reaches_sdk(self):
  for body in [b'bad',b'x'*len(self.payload)]:
   manager=self.manager();manager.check_for_updates()
   def corrupt(url,path,limit):Path(path).write_bytes(body)
   manager.fetch=corrupt
   with self.assertRaises(ValueError):manager.download_updates(self.info)
   self.assertFalse((manager.cache/self.asset['FileName']).exists());self.assertFalse(list(manager.cache.glob('*.partial')))
  self.sdk.download_updates.assert_not_called()
 def test_invalid_feed_filenames_or_hashes_are_rejected(self):
  for key,value in [('FileName','../unexpected.nupkg'),('SHA256',''),('PackageId','OtherApp'),('Size',-1),('Version','../../file')]:
   old=self.asset[key];self.asset[key]=value
   with self.assertRaises(ValueError):self.manager().check_for_updates()
   self.asset[key]=old
  self.sdk.check_for_updates.assert_not_called()
 def test_only_https_github_download_hosts_are_allowed(self):
  for url in ['http://github.com/file','https://github.com.evil.example/file','https://github.com@evil.example/file','https://github.com:8080/file','https://evil.example/file']:
   with self.assertRaises(ValueError):validate_url(url)
  validate_url('https://release-assets.githubusercontent.com/file')

 def test_prerelease_asset_passes_validation_and_pins_exact_tag(self):
  self.asset['Version']='1.0.0-beta.1'
  self.asset['FileName']='Bakuri.FileConverter-1.0.0-beta.1-stable-full.nupkg'
  self.info.TargetFullRelease=types.SimpleNamespace(**self.asset)
  manager=self.manager();manager.check_for_updates();manager.download_updates(self.info)
  self.assertIn('/releases/download/v1.0.0-beta.1/',self.calls[-1])
