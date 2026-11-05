"""A tray card for progress and completion, independent of OS notifications."""

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QApplication,
    QWidget,
    QFrame,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QProgressBar,
)


class CompletionToast(QWidget):
    def __init__(self, open_result, open_folder):
        super().__init__(
            None,
            Qt.Tool
            | Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.WindowDoesNotAcceptFocus,
        )
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFocusPolicy(Qt.NoFocus)
        self.setWindowTitle("바꾸리 작업 결과")
        self.setFixedWidth(380)
        self.setStyleSheet("""
            QWidget {font-family:"Malgun Gothic","Noto Sans CJK KR",sans-serif;
                font-size:13px;color:#26354A;}
            QFrame#card {background:#FFFFFF;border:1px solid #AECDF6;border-radius:12px;}
            QLabel {background:transparent;border:0;}
            QLabel#title {font-weight:600;color:#2E83F2;}
            QPushButton {background:#F1F6FE;border:1px solid #DCE3EE;border-radius:6px;
                padding:7px 10px;color:#26354A;}
            QPushButton:hover {background:#E3EFFF;}
            QPushButton#close {background:transparent;border:0;padding:0;font-size:18px;}
        """)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        card = QFrame()
        card.setObjectName("card")
        outer.addWidget(card)
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 12, 16, 14)
        layout.setSpacing(10)
        heading = QHBoxLayout()
        self.title = QLabel("바꾸리 작업 결과")
        self.title.setObjectName("title")
        heading.addWidget(self.title)
        heading.addStretch()
        close = QPushButton("×")
        close.setObjectName("close")
        close.setAccessibleName("알림 닫기")
        close.setFixedSize(24, 24)
        close.clicked.connect(self.hide)
        heading.addWidget(close)
        layout.addLayout(heading)
        self.summary = QLabel()
        self.summary.setTextFormat(Qt.PlainText)
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(1)
        self.progress_bar.hide()
        layout.addWidget(self.progress_bar)
        self.notice = QLabel()
        self.notice.setTextFormat(Qt.PlainText)
        self.notice.setWordWrap(True)
        self.notice.hide()
        layout.addWidget(self.notice)
        self.actions = QWidget()
        actions = QHBoxLayout(self.actions)
        actions.setContentsMargins(0, 0, 0, 0)
        self.folder = QPushButton("저장 폴더 열기")
        self.folder.clicked.connect(lambda: self.activate_action(open_folder))
        actions.addWidget(self.folder)
        result = QPushButton("결과 보기")
        result.clicked.connect(lambda: self.activate_action(open_result))
        actions.addWidget(result)
        actions.addStretch()
        layout.addWidget(self.actions)
        for button in (close, self.folder, result):
            button.setFocusPolicy(Qt.NoFocus)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)
        self.showing_progress = False
        self.anchor = None

    def activate_action(self, action):
        self.hide()
        action()

    def start_progress(self, text, tray_rect):
        self.timer.stop()
        self.showing_progress = True
        self.title.setText("바꾸리 작업 중")
        self.actions.hide()
        self.progress_bar.setValue(1)
        self.progress_bar.show()
        self.notice.hide()
        self.progress_rect = tray_rect
        self.update_progress(text)
        self.show()

    def update_progress(self, text):
        if self.showing_progress:
            self.summary.setText(text)
            self.place(self.progress_rect)

    def set_progress(self, percent):
        self.progress_bar.setValue(percent)

    def set_notice(self, text):
        self.notice.setText(text)
        self.notice.setVisible(bool(text))
        self.place(getattr(self, "progress_rect", None))

    def queued(self, progress, count, tray_rect):
        if not self.showing_progress:
            self.start_progress(progress, tray_rect)
        self.set_notice(f"대기열에 추가했습니다 · 대기 {count}개")
        self.show()

    def present(self, summary, has_folder, warning=False, tray_rect=None):
        self.showing_progress = False
        self.actions.show()
        self.progress_bar.hide()
        self.notice.hide()
        self.title.setText("작업 결과를 확인해 주세요" if warning else "바꾸리 작업 결과")
        self.summary.setText(summary)
        self.folder.setEnabled(has_folder)
        self.place(tray_rect)
        self.show()
        self.timer.start(12000)

    def place(self, tray_rect):
        self.anchor = (
            tray_rect.center() if tray_rect is not None and tray_rect.isValid() else QCursor.pos()
        )
        layout = self.layout()
        layout.invalidate()
        layout.activate()
        # The content wraps at a fixed width; calculate the height at that width
        # before anchoring, even when the previous card is still on screen.
        self.resize(self.width(), layout.totalHeightForWidth(self.width()))
        self.move_to_anchor()

    def move_to_anchor(self):
        if self.anchor is None:
            return
        screen = QApplication.screenAt(self.anchor) or QApplication.primaryScreen()
        area = screen.availableGeometry()
        self.move(
            max(area.left(), area.right() + 1 - self.width() - 15),
            max(area.top(), area.bottom() + 1 - self.height() - 15),
        )

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.move_to_anchor()

    def hideEvent(self, event):
        self.showing_progress = False
        self.timer.stop()
        super().hideEvent(event)
