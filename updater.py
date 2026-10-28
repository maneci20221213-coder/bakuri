"""Consent-only Velopack updates. Network activity only on explicit UI entry."""
import json,threading,time
from pathlib import Path
from urllib.parse import urlparse
from PySide6.QtCore import QObject,Signal
from PySide6.QtWidgets import QDialog,QVBoxLayout,QLabel,QCheckBox,QDialogButtonBox,QMessageBox
from version import VERSION
from user_messages import friendly_error
def config_path():
    import sys
    return Path(sys.executable).with_name('update-config.json') if getattr(sys,'frozen',False) else Path(__file__).with_name('update-config.json')
def feed_url():
    data=json.loads(config_path().read_text(encoding='utf-8-sig'))
    url=data.get('url','').strip()
    if not url:return ''
    parsed=urlparse(url)
    if parsed.scheme!='https' or not parsed.netloc or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError('업데이트 주소는 인증정보 없는 HTTPS 주소여야 합니다.')
    kind=data.get('source','http')
    if kind not in {'github','http'}:raise ValueError('지원하지 않는 업데이트 배포 방식입니다.')
    if kind=='github' and (parsed.netloc!='github.com' or len(parsed.path.strip('/').split('/'))!=2):
        raise ValueError('GitHub 업데이트 주소는 저장소 주소여야 합니다.')
    return url.rstrip('/')

def make_update_manager(url):
    import velopack
    data=json.loads(config_path().read_text(encoding='utf-8-sig'))
    if data.get('source','http')=='github':
        # Public repository: never embed a GitHub token in the distributed app.
        source=velopack.GithubSource(url,access_token=None,prerelease=False)
    else:source=url
    return velopack.UpdateManager(source)

class UpdatePrompt(QDialog):
    def __init__(self,version,parent=None):
        super().__init__(parent);self.setWindowTitle('바꾸리 업데이트');self.setMinimumWidth(390)
        layout=QVBoxLayout(self);label=QLabel(f'새 버전 {version}이 있습니다.\n지금 다운로드하고 설치할까요?\n설치 시 바꾸리가 종료된 뒤 다시 실행됩니다.');label.setWordWrap(True);layout.addWidget(label)
        self.skip=QCheckBox('이 버전 건너뛰기');layout.addWidget(self.skip)
        buttons=QDialogButtonBox();self.install=buttons.addButton('업데이트',QDialogButtonBox.AcceptRole);buttons.addButton('나중에',QDialogButtonBox.RejectRole)
        self.skip.toggled.connect(lambda checked:self.install.setEnabled(not checked))
        buttons.accepted.connect(self.accept);buttons.rejected.connect(self.reject);layout.addWidget(buttons)

class UpdateController(QObject):
    checked=Signal(object);failed=Signal(str);downloaded=Signal(object)
    def __init__(self,window,settings,manager_factory=None):
        super().__init__(window);self.window=window;self.settings=settings;self.factory=manager_factory
        self.checking=False;self.installing=False;self.offered=set();self.worker=None;self.last_check=None
        self.checked.connect(self.on_checked);self.failed.connect(self.on_failed);self.downloaded.connect(self.on_downloaded)
    def request(self,reason):
        if reason not in {'direct','expanded'} or self.checking or self.installing or self.window.busy:return
        now=time.monotonic()
        if self.last_check is not None and now-self.last_check<300:return
        self.last_check=now;self.checking=True
        def work():
            try:
                url=feed_url()
                if not url:self.checked.emit(None);return
                factory=self.factory
                if factory is None:factory=make_update_manager
                manager=factory(url);info=manager.check_for_updates()
                self.checked.emit((manager,info) if info else None)
            except Exception as exc:self.failed.emit(friendly_error(exc,'update_check'))
        self.worker=threading.Thread(target=work,daemon=True);self.worker.start()
    def on_checked(self,result):
        self.checking=False
        if not result or self.window.busy or not self.window.isVisible():return
        manager,info=result
        version=str(info.TargetFullRelease.Version)
        if version in self.offered or version==self.settings.value('update_skipped_version',''):return
        self.offered.add(version)
        dialog=UpdatePrompt(version,self.window);accepted=dialog.exec()==QDialog.Accepted
        if dialog.skip.isChecked():
            self.settings.setValue('update_skipped_version',version);self.settings.sync();return
        if not accepted or self.window.busy:return
        self.installing=True;self.window.setEnabled(False);self.window.status.setText('업데이트 다운로드 중 · 완료 후 다시 실행합니다.')
        def download():
            try:manager.download_updates(info);self.downloaded.emit((manager,info))
            except Exception as exc:self.failed.emit(friendly_error(exc,'update_download'))
        self.worker=threading.Thread(target=download,daemon=True);self.worker.start()
    def on_downloaded(self,result):
        manager,info=result
        try:
            # Main UI thread, after all conversion work has been excluded.
            manager.apply_updates_and_restart(info)
            from PySide6.QtWidgets import QApplication
            QApplication.quit()
        except Exception as exc:self.on_failed(friendly_error(exc,'update_install'))
    def on_failed(self,text):
        was_installing=self.installing;self.checking=False;self.installing=False;self.window.setEnabled(True)
        text=friendly_error(text,'update_install' if was_installing else 'update_check')
        self.window.status.setText(text)
        if was_installing:QMessageBox.warning(self.window,'업데이트를 완료하지 못했어요',text)
