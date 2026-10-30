"""A completion-only card independent of OS balloon-notification visibility."""

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
        actions = QHBoxLayout()
        self.folder = QPushButton("저장 폴더 열기")
        self.folder.clicked.connect(lambda: self.activate_action(open_folder))
        actions.addWidget(self.folder)
        result = QPushButton("결과 보기")
        result.clicked.connect(lambda: self.activate_action(open_result))
        actions.addWidget(result)
        actions.addStretch()
        layout.addLayout(actions)
        for button in (close, self.folder, result):
            button.setFocusPolicy(Qt.NoFocus)
        self.timer = QTimer(self)
        self.timer.setSingleShot(True)
        self.timer.timeout.connect(self.hide)

    def activate_action(self, action):
        self.hide()
        action()

    def present(self, summary, has_folder, warning=False, tray_rect=None):
        self.title.setText("작업 결과를 확인해 주세요" if warning else "바꾸리 작업 결과")
        self.summary.setText(summary)
        self.folder.setEnabled(has_folder)
        self.adjustSize()
        position = (
            tray_rect.center() if tray_rect is not None and tray_rect.isValid() else QCursor.pos()
        )
        screen = QApplication.screenAt(position) or QApplication.primaryScreen()
        area = screen.availableGeometry()
        self.move(
            max(area.left(), area.right() - self.width() - 15),
            max(area.top(), area.bottom() - self.height() - 15),
        )
        self.show()
        self.timer.start(12000)

    def hideEvent(self, event):
        self.timer.stop()
        super().hideEvent(event)
