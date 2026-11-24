"""Sheet selection stays responsive while Excel reads workbook metadata."""

from pathlib import Path
from threading import Thread
from PySide6.QtCore import QObject, Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)
from bakuri.application.control import JobControl, Cancelled
from bakuri.conversion.spreadsheets import inspect_sheets
from theme import stylesheet
from user_messages import friendly_error


class _SheetSignals(QObject):
    loaded = Signal(object)
    failed = Signal(str)


class SheetsDialog(QDialog):
    def __init__(self, paths, merge=False, parent=None):
        super().__init__(parent)
        self.merge = merge
        self.fingerprint = ()
        self.control = JobControl()
        self.setWindowTitle("시트 합치기" if merge else "시트 나누기")
        self.setMinimumWidth(480)
        self.setStyleSheet(stylesheet())
        layout = QVBoxLayout(self)
        title = QLabel(f"선택한 Excel 파일 {len(paths)}개" if merge else Path(paths[0]).name)
        title.setTextFormat(Qt.PlainText)
        title.setWordWrap(True)
        layout.addWidget(title)
        self.sheets = QListWidget(self)
        self.sheets.setVisible(not merge)
        self.sheets.setAccessibleName("저장할 Excel 시트")
        self.sheets.setMinimumHeight(180)
        self.summary = QLabel(
            "선택한 파일 순서대로 모든 시트를 한 파일에 넣습니다."
            if merge
            else "시트 목록을 불러오는 중입니다…"
        )
        self.summary.setTextFormat(Qt.PlainText)
        self.summary.setWordWrap(True)
        if not merge:
            layout.addWidget(self.sheets)
            actions = QHBoxLayout()
            for text, checked in (("전체 선택", True), ("전체 해제", False)):
                button = QPushButton(text)
                button.clicked.connect(lambda _, checked=checked: self.select_all(checked))
                actions.addWidget(button)
            actions.addStretch()
            layout.addLayout(actions)
        layout.addWidget(self.summary)
        self.values_only = QCheckBox("수식을 현재 값으로 저장")
        layout.addWidget(self.values_only)
        note = QLabel(
            "기본은 수식 유지입니다. 다른 시트를 참조하는 수식은 원본 파일에 연결될 수 있습니다.\n"
            "결과는 XLSX로 저장하며, 같은 시트 이름에는 파일명이나 번호를 붙입니다."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Ok).setText(
            "한 파일로 합치기" if merge else "선택한 시트 저장"
        )
        self.buttons.button(QDialogButtonBox.Cancel).setText("취소")
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(merge)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.sheets.itemChanged.connect(self.refresh)
        self.finished.connect(lambda _: self.control.cancel())
        self.loader = _SheetSignals()
        self.loader.loaded.connect(self.loaded)
        self.loader.failed.connect(self.failed)
        if not merge:
            path, signals, control = paths[0], self.loader, self.control

            def read():
                try:
                    signals.loaded.emit(inspect_sheets(path, control))
                except Cancelled:
                    pass
                except Exception as error:
                    signals.failed.emit(friendly_error(error))

            self.worker = Thread(target=read, daemon=True)
            QTimer.singleShot(0, self.worker.start)

    def loaded(self, result):
        if self.control.cancelled.is_set():
            return
        names, self.fingerprint = result
        for name, hidden in names:
            item = QListWidgetItem(name + (" (숨김)" if hidden else ""))
            item.setData(Qt.UserRole, name)
            item.setCheckState(Qt.Checked)
            self.sheets.addItem(item)
        self.refresh()

    def failed(self, message):
        if not self.control.cancelled.is_set():
            self.summary.setText(message)

    def select_all(self, checked):
        for index in range(self.sheets.count()):
            self.sheets.item(index).setCheckState(Qt.Checked if checked else Qt.Unchecked)

    def selected_sheets(self):
        return tuple(
            self.sheets.item(i).data(Qt.UserRole)
            for i in range(self.sheets.count())
            if self.sheets.item(i).checkState() == Qt.Checked
        )

    def refresh(self):
        count = len(self.selected_sheets())
        self.summary.setText(f"{count}개 시트를 각각 새 파일로 저장합니다.")
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(count > 0)
