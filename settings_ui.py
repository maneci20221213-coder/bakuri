"""Application preferences and their Windows integration."""
import sys
from PySide6.QtWidgets import (QDialog,QFormLayout,QCheckBox,QComboBox,QLabel,QPushButton,QDialogButtonBox,QMessageBox)
from work_ui import add_profiles,read_options
from user_messages import friendly_error

class SettingsDialog(QDialog):
    def __init__(self,window):
        super().__init__(window); self.window=window; self.setWindowTitle('바꾸리 설정'); form=QFormLayout(self)
        self.enabled=QCheckBox('단축키 사용'); self.enabled.setChecked(window.settings.value('hotkey_enabled',True,type=bool)); form.addRow(self.enabled)
        self.key=QComboBox(); self.key.addItems(['` (백틱)','F8','F9','Ctrl+Alt+B']); self.key.setCurrentText(window.settings.value('hotkey','` (백틱)')); form.addRow('단축키',self.key)
        hint=QLabel('탐색기·바탕화면에서 작동합니다. 다른 앱과 충돌하면 F8 또는 Ctrl+Alt+B로 바꿔 주세요.'); hint.setWordWrap(True); form.addRow(hint)
        self.auto=QCheckBox('윈도우 로그인 시 백그라운드 실행')
        self.auto.setChecked(window.settings.value('startup_enabled',True,type=bool))
        if sys.platform=='win32':
            from windows import startup_enabled
            self.auto.setChecked(startup_enabled())
        else: self.auto.setEnabled(False)
        form.addRow(self.auto)
        self.explorer=QCheckBox('탐색기 우클릭 메뉴 추가'); self.explorer.setChecked(window.settings.value('explorer',True,type=bool)); form.addRow(self.explorer)
        self.repair_menu=QPushButton('우클릭 메뉴 다시 등록');self.repair_menu.setEnabled(sys.platform=='win32');self.repair_menu.clicked.connect(self.restore_menu);form.addRow(self.repair_menu)
        self.dpi=QComboBox(); self.dpi.addItems(['96','150','200','300']); self.dpi.setCurrentText(str(window.settings.value('dpi',150,type=int))); form.addRow('PDF 이미지 해상도',self.dpi)
        self.image_mode=QComboBox();self.image_mode.addItem('표 배경으로 채우기 (기본)','background');self.image_mode.addItem('표 안에 이미지 넣기','inline');self.image_mode.setCurrentIndex(max(0,self.image_mode.findData(window.settings.value('image_mode','background'))));form.addRow('이미지 → 한글 배치',self.image_mode)
        self.compress_profile=QComboBox();add_profiles(self.compress_profile);self.compress_profile.setCurrentIndex(self.compress_profile.findData(read_options(window.settings)['profile']));form.addRow('해상도 축소 기본값',self.compress_profile)
        self.compress_protect=QCheckBox('글자 보호 강화 · 이미지 해상도 유지');self.compress_protect.setChecked(window.settings.value('compress_protect',False,type=bool));form.addRow(self.compress_protect)
        self.compress_strip=QCheckBox('용량 축소 시 위치정보 등 메타데이터 삭제');self.compress_strip.setChecked(window.settings.value('compress_strip',False,type=bool));form.addRow(self.compress_strip)
        self.compress_direct=QCheckBox('팝업에서 설정창 없이 용량 축소 실행');self.compress_direct.setChecked(window.settings.value('compress_direct',False,type=bool));form.addRow(self.compress_direct)
        self.notify=QCheckBox('변환 완료 알림'); self.notify.setChecked(window.settings.value('notify',True,type=bool)); form.addRow(self.notify)
        buttons=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); buttons.accepted.connect(self.save); buttons.rejected.connect(self.reject); form.addRow(buttons)
    def restore_menu(self):
        try:
            from windows import register_menu
            register_menu(True)
            self.window.settings.setValue('explorer',True);self.window.settings.sync()
            self.explorer.setChecked(True)
            QMessageBox.information(self,'우클릭 메뉴 등록','현재 사용자 계정에 등록했습니다. 탐색기에서 파일을 다시 우클릭해 주세요.')
        except Exception as exc:QMessageBox.warning(self,'우클릭 메뉴를 추가하지 못했어요',friendly_error(exc,'menu'))
    def save(self):
        try:
            if sys.platform=='win32':
                from windows import set_startup,register_menu
                set_startup(self.auto.isChecked()); register_menu(self.explorer.isChecked())
            s=self.window.settings; s.setValue('startup_enabled',self.auto.isChecked()); s.setValue('hotkey_enabled',self.enabled.isChecked()); s.setValue('hotkey',self.key.currentText()); s.setValue('notify',self.notify.isChecked()); s.setValue('explorer',self.explorer.isChecked()); s.setValue('dpi',int(self.dpi.currentText()));s.setValue('image_mode',self.image_mode.currentData());s.setValue('compress_profile',self.compress_profile.currentData());s.setValue('compress_protect',self.compress_protect.isChecked());s.setValue('compress_strip',self.compress_strip.isChecked());s.setValue('compress_direct',self.compress_direct.isChecked()); s.sync();
            if hasattr(self.window,'watcher'): self.window.watcher.update_settings(s)
            self.accept()
        except Exception as e: QMessageBox.warning(self,'설정을 저장하지 못했어요',friendly_error(e,'settings'))

