"""Shared page split/extract dialog for the quick popup and main conversion view."""

from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QSpinBox,
    QVBoxLayout,
)
from bakuri.domain.pdf_selection import page_groups
from theme import stylesheet


class PdfSplitDialog(QDialog):
    def __init__(self, path, count, parent=None):
        super().__init__(parent)
        self.count = count
        self.setWindowTitle("페이지 나누기")
        self.setMinimumWidth(480)
        self.setStyleSheet(stylesheet())
        layout = QVBoxLayout(self)
        filename = Path(path).name
        title = QLabel(f"{filename} · 전체 {count}페이지" if count is not None else filename)
        title.setTextFormat(Qt.PlainText)
        title.setWordWrap(True)
        layout.addWidget(title)
        form = QFormLayout()
        layout.addLayout(form)

        self.modes = QButtonGroup(self)
        self.mode_buttons = {}
        for mode, label in (
            ("interval", "일정하게 나누기"),
            ("boundaries", "특정 페이지 기준"),
            ("extract", "일부만 추출"),
        ):
            button = QRadioButton(label)
            self.modes.addButton(button)
            self.mode_buttons[mode] = button
        self.mode_buttons["interval"].setChecked(True)
        self.every = QSpinBox()
        self.every.setRange(1, count if count is not None else 999999)
        interval = QHBoxLayout()
        interval.addWidget(self.every)
        interval.addWidget(QLabel("페이지마다"))
        interval.addStretch()
        form.addRow(self.mode_buttons["interval"], interval)

        self.boundaries = QLineEdit()
        self.boundaries.setPlaceholderText("새 파일을 시작할 페이지 · 예: 4, 8")
        form.addRow(self.mode_buttons["boundaries"], self.boundaries)
        self.selection = QLineEdit()
        self.selection.setPlaceholderText("예: 5, 1-3, 8")
        form.addRow(self.mode_buttons["extract"], self.selection)
        self.separate = QCheckBox("입력한 범위별로 각각 저장")
        form.addRow("", self.separate)

        hint = QLabel(
            "특정 페이지 기준은 입력한 페이지부터 새 파일을 만듭니다.\n"
            "일부만 추출할 때는 입력한 순서대로 저장합니다."
        )
        output_format = Path(path).suffix[1:].upper()
        if count is None:
            hint.setText(hint.text() + f"\n원본과 같은 {output_format} 형식으로 저장합니다.")
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        self.summary.setTextFormat(Qt.PlainText)
        layout.addWidget(self.summary)
        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.button(QDialogButtonBox.Ok).setText(f"새 {output_format} 만들기")
        self.buttons.button(QDialogButtonBox.Cancel).setText("취소")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.modes.buttonToggled.connect(self.mode_changed)
        self.every.valueChanged.connect(self.refresh)
        self.boundaries.textChanged.connect(self.refresh)
        self.selection.textChanged.connect(self.refresh)
        self.separate.toggled.connect(self.refresh)
        self.refresh()

    def mode_changed(self, button, checked):
        if checked:
            self.refresh()

    def options(self):
        mode = next(mode for mode, button in self.mode_buttons.items() if button.isChecked())
        return dict(
            mode=mode,
            every=self.every.value(),
            selection=self.boundaries.text() if mode == "boundaries" else self.selection.text(),
            separate=mode == "extract" and self.separate.isChecked(),
        )

    def refresh(self):
        options = self.options()
        mode = options["mode"]
        self.every.setEnabled(mode == "interval")
        self.boundaries.setEnabled(mode == "boundaries")
        self.selection.setEnabled(mode == "extract")
        self.separate.setEnabled(mode == "extract")
        try:
            if self.count is None:
                self.summary.setText("페이지 수는 문서를 연 뒤 확인합니다.")
                valid = mode == "interval" or bool(options["selection"].strip())
            else:
                groups = page_groups(self.count, **options)
                self.summary.setText(
                    f"PDF {len(groups)}개 생성 예정 · 총 {sum(map(len, groups))}페이지"
                )
                valid = True
        except ValueError as error:
            self.summary.setText(str(error))
            valid = False
        self.buttons.button(QDialogButtonBox.Ok).setEnabled(valid)
