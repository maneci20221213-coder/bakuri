"""Offline, scrollable user manual bundled with the application."""
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication,QDialog,QVBoxLayout,QTextBrowser,QDialogButtonBox
from theme import stylesheet

class HelpDialog(QDialog):
    def __init__(self,parent=None):
        super().__init__(parent);self.setWindowTitle('바꾸리 사용 설명');self.setStyleSheet(stylesheet())
        screen=self.screen() or QApplication.primaryScreen();area=screen.availableGeometry()
        self.resize(min(720,area.width()-40),min(650,area.height()-60))
        layout=QVBoxLayout(self);self.text=QTextBrowser();self.text.setAccessibleName('바꾸리 사용 설명 본문');self.text.setOpenExternalLinks(True)
        self.text.setStyleSheet('QTextBrowser { background:white; border:1px solid #DCE3EE; border-radius:7px; padding:14px; font-size:14px; }')
        try:manual=Path(__file__).with_name('USER-GUIDE.md').read_text(encoding='utf-8')
        except (OSError,UnicodeError):manual='# 바꾸리 사용 설명\n\n파일 추가 → 체크 표시 → 출력 형식 → 변환 시작 순서로 사용하세요. 결과는 원본 폴더에 새 파일로 저장됩니다. 전체 설명은 다운로드 페이지에서 확인하실 수 있습니다.'
        self.text.setMarkdown(manual);layout.addWidget(self.text)
        buttons=QDialogButtonBox();buttons.addButton('닫기',QDialogButtonBox.RejectRole);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
