"""Separate task guides and released-version history, available offline."""

from pathlib import Path
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QVBoxLayout,
    QTextBrowser,
    QDialogButtonBox,
    QTabWidget,
)
from build_channel import DEFAULT_HOTKEY
from theme import stylesheet


class HelpDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("바꾸리 사용 설명")
        self.setStyleSheet(stylesheet())
        screen = self.screen() or QApplication.primaryScreen()
        area = screen.availableGeometry()
        self.resize(min(720, area.width() - 40), min(650, area.height() - 60))
        layout = QVBoxLayout(self)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        self.text = self.add_page(
            "파일 형식 변환",
            "USER-GUIDE.md",
            "파일 추가 → 체크 → 출력 형식 → 변환 시작 순서로 사용하세요.",
        )
        self.rename_text = self.add_page(
            "파일명 변경",
            "RENAME-GUIDE.md",
            "파일 추가 → 파일명 변경 → 미리보기 → 이름 변경 적용 순서로 사용하세요.",
        )
        self.notes = self.add_page(
            "패치노트",
            "PATCH-NOTES.md",
            "패치노트를 불러오지 못했습니다. 다운로드 페이지에서 확인해 주세요.",
        )
        buttons = QDialogButtonBox()
        buttons.addButton("닫기", QDialogButtonBox.RejectRole)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def add_page(self, title, filename, fallback):
        text = QTextBrowser()
        text.setAccessibleName("바꾸리 " + title + " 본문")
        text.setOpenExternalLinks(True)
        text.setStyleSheet(
            "QTextBrowser {background:white;border:1px solid #DCE3EE;border-radius:7px;padding:14px;font-size:14px;}"
        )
        try:
            content = Path(__file__).with_name(filename).read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            content = fallback
        content = content.replace("{{HOTKEY}}", DEFAULT_HOTKEY)
        text.setMarkdown(content)
        self.tabs.addTab(text, title)
        return text
