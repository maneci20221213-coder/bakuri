"""Download public release assets, then let Velopack verify and apply locally."""
import hashlib,json,re,tempfile
from pathlib import Path
from update_transport import download_to,validate_url

class PublicReleaseManager:
    def __init__(self,repository,sdk_factory=None,downloader=None):
        self.repository=repository.rstrip('/');validate_url(self.repository)
        self.factory=sdk_factory;self.fetch=downloader or download_to
        self.folder=tempfile.TemporaryDirectory(prefix='BakuriUpdate-')
        self.cache=Path(self.folder.name);self.manager=None
    def check_for_updates(self):
        feed=self.cache/'releases.stable.json'
        self.fetch(self.repository+'/releases/latest/download/releases.stable.json',feed,2*1024*1024)
        data=json.loads(feed.read_text(encoding='utf-8-sig'))
        assets=data.get('Assets',[])
        if not isinstance(assets,list) or not assets:raise ValueError('Missing stable release assets')
        for asset in assets:
            version=asset.get('Version','');name=asset.get('FileName','')
            if (asset.get('PackageId')!='Bakuri.FileConverter' or asset.get('Type')!='Full'
                or not re.fullmatch(r'\d+\.\d+\.\d+',version)
                or name!='Bakuri.FileConverter-'+version+'-stable-full.nupkg'
                or type(asset.get('Size')) is not int or not 0<asset['Size']<=1024**3
                or not re.fullmatch(r'[0-9A-Fa-f]{64}',asset.get('SHA256',''))):
                raise ValueError('Invalid stable update asset')
        if self.factory is None:
            import velopack
            self.factory=velopack.UpdateManager
        self.manager=self.factory(str(self.cache))
        return self.manager.check_for_updates()
    def download_updates(self,info):
        asset=info.TargetFullRelease
        # Pin the tag to the version checked earlier, even if latest changes.
        url=self.repository+'/releases/download/v'+str(asset.Version)+'/'+asset.FileName
        target=self.cache/asset.FileName;partial=target.with_suffix('.partial')
        try:
            self.fetch(url,partial,asset.Size)
            if partial.stat().st_size!=asset.Size:raise ValueError('Incomplete update package')
            with partial.open('rb') as file:digest=hashlib.file_digest(file,'sha256').hexdigest()
            if digest.lower()!=asset.SHA256.lower():raise ValueError('Update checksum mismatch')
            partial.replace(target)
            self.manager.download_updates(info)
        finally:partial.unlink(missing_ok=True)
    def apply_updates_and_restart(self,info):
        return self.manager.apply_updates_and_restart(info)
