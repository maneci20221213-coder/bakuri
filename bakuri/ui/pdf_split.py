"""Shared PDF split/extract dialog for the quick popup and main conversion view."""

from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLabel,
    QComboBox,
    QSpinBox,
    QLineEdit,
    QCheckBox,
    QDialogButtonBox,
)
from bakuri.domain.pdf_selection import page_groups
from theme import stylesheet


class PdfSplitDialog(QDialog):
    def __init__(self, path, count, parent=None):
        super().__init__(parent)
        self.count = count
        self.setWindowTitle("PDF 페이지 나누기 / 추출")
        self.setMinimumWidth(480)
        self.setStyleSheet(stylesheet())
        layout = QVBoxLayout(self)
        title = QLabel(f"{Path(path).name} · 전체 {count}페이지")
        title.setWordWrap(True)
        layout.addWidget(title)
        form = QFormLayout()
        layout.addLayout(form)
        self.mode = QComboBox()
        self.mode.addItem("일정 페이지마다 나누기", "interval")
        self.mode.addItem("원하는 페이지 추출", "extract")
        form.addRow("방식", self.mode)
        self.every = QSpinBox()
        self.every.setRange(1, count)
        self.every.setSuffix("페이지마다")
        form.addRow("나눌 단위", self.every)
        self.selection = QLineEdit()
        self.selection.setPlaceholderText("예: 1-3, 5, 8-10")
        form.addRow("추출할 페이지", self.selection)
        self.separate = QCheckBox("범위별로 각각 저장")
        form.addRow(self.separate)
        hint = QLabel("페이지는 1쪽부터 셉니다. 원본 문서 순서대로 새 PDF에 저장합니다.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.PlainText)
        layout.addWidget(self.summary)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Ok).setText("새 PDF 만들기")
        self.buttons.button(QDialogButtonBox.Cancel).setText("취소")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.mode.currentIndexChanged.connect(self.refresh)
        self.every.valueChanged.connect(self.refresh)
        self.selection.textChanged.connect(self.refresh)
        self.separate.toggled.connect(self.refresh)
        self.refresh()

    def options(self):
        return dict(
            mode=self.mode.currentData(),
            every=self.every.value(),
            selection=self.selection.text(),
            separate=self.separate.isChecked(),
        )

    def refresh(self):
        extract = self.mode.currentData() == "extract"
        self.every.setEnabled(not extract)
        self.selection.setEnabled(extract)
        self.separate.setEnabled(extract)
        try:
            groups = page_groups(self.count, **self.options())
            self.summary.setText(
                f"PDF {len(groups)}개 생성 예정 · 총 {sum(map(len, groups))}페이지"
            )
            valid = True
        except ValueError as error:
            self.summary.setText(str(error))
            valid = False
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(valid)
