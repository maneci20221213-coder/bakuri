"""CI-only: real Windows download transport and installed Velopack SDK check/download."""
import json,shutil,sys,tempfile,xml.etree.ElementTree as ET
from pathlib import Path
import velopack
from update_transport import download_to
from update_source import PublicReleaseManager
from version import VERSION

def verify(root,releases):
 with tempfile.TemporaryDirectory(prefix='BakuriUpdateTest-') as folder:
  folder=Path(folder)
  public_feed=folder/'public.json'
  download_to('https://github.com/maneci20221213-coder/bakuri/releases/latest/download/releases.stable.json',public_feed,2*1024*1024)
  assert json.loads(public_feed.read_text(encoding='utf-8-sig'))['Assets']
  print('Windows Internet HTTPS download verification passed.')
  manifest=root/'current'/'sq.version'
  tree=ET.parse(manifest)
  node=next(x for x in tree.iter() if x.tag.rsplit('}',1)[-1]=='version')
  node.text='0.14.7';older=folder/'older.version';tree.write(older,encoding='utf-8',xml_declaration=True)
  locator=velopack.VelopackLocatorConfig(root,root/'Update.exe',root/'packages',older,root/'current',False)
  def factory(source):return velopack.UpdateManager(source,locator=locator)
  def copy_asset(url,target,limit):
   name=url.rsplit('/',1)[-1];source=releases/name
   assert source.stat().st_size<=limit;shutil.copyfile(source,target)
  manager=PublicReleaseManager('https://github.com/maneci20221213-coder/bakuri',sdk_factory=factory,downloader=copy_asset)
  try:
   info=manager.check_for_updates()
   assert info and str(info.TargetFullRelease.Version)==VERSION
   package=root/'packages'/info.TargetFullRelease.FileName
   package.unlink(missing_ok=True)
   manager.download_updates(info)
   assert package.is_file() and package.stat().st_size==info.TargetFullRelease.Size
   print('Installed SDK older-version detection and verified package download passed.')
  finally:manager.folder.cleanup()

if __name__=='__main__':verify(Path(sys.argv[1]),Path(sys.argv[2]))
