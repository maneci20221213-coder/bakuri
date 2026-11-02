"""Resolve multi-photo choices before starting any worker or output file."""

from dataclasses import replace
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QVBoxLayout, QLabel, QCheckBox, QPushButton, QHBoxLayout
from bakuri.conversion.multi_image import inspect_multi_image
from theme import stylesheet


class MultiImageDialog(QDialog):
    def __init__(self, info, remaining=False, parent=None):
        super().__init__(parent)
        self.choice = None
        self.setWindowTitle("여러 이미지가 들어 있는 파일")
        self.setMinimumWidth(520)
        self.setStyleSheet(stylesheet())
        box = QVBoxLayout(self)
        label = QLabel(
            f"‘{Path(info.path).name}’ 파일 안에 이미지가 {info.count}장 들어 있습니다.\n처리할 이미지를 선택해 주세요."
        )
        label.setTextFormat(Qt.PlainText)
        label.setWordWrap(True)
        box.addWidget(label)
        hint = QLabel(
            "대표 이미지만 처리하거나, 모든 이미지를 각각 새 파일로 만듭니다. 원본은 유지합니다.\n전체 각각 저장을 선택하면 이 작업은 합치지 않고 모든 선택 파일을 각각 저장합니다."
        )
        hint.setWordWrap(True)
        box.addWidget(hint)
        self.apply_remaining = QCheckBox("나머지 다중 이미지 파일에도 같은 선택 적용")
        self.apply_remaining.setVisible(remaining)
        box.addWidget(self.apply_remaining)
        buttons = QHBoxLayout()
        self.primary = QPushButton("대표 이미지만 처리")
        self.all_images = QPushButton("모든 이미지 각각 저장")
        cancel = QPushButton("취소")
        for button in (self.primary, self.all_images, cancel):
            buttons.addWidget(button)
        box.addLayout(buttons)
        self.primary.clicked.connect(lambda: self.select("primary"))
        self.all_images.clicked.connect(lambda: self.select("all"))
        cancel.clicked.connect(self.reject)

    def select(self, mode):
        self.choice = mode
        self.accept()


def choose_multi_images(files, parent=None):
    infos = [info for file in files if (info := inspect_multi_image(file.path)) is not None]
    result, remembered = [], None
    for index, info in enumerate(infos):
        if info.auxiliary or info.count == 1:
            result.append(info)
            continue
        mode = remembered
        if mode is None:
            remaining = any(not item.auxiliary and item.count > 1 for item in infos[index + 1 :])
            dialog = MultiImageDialog(info, remaining, parent)
            if dialog.exec() != QDialog.Accepted or dialog.choice is None:
                return None
            mode = dialog.choice
            if dialog.apply_remaining.isChecked():
                remembered = mode
        result.append(replace(info, mode=mode))
    return tuple(result)
