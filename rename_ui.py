"""Live preview, stable per-file text assignments, and reversible batch renaming."""

import json
from dataclasses import replace
from pathlib import Path
from PySide6.QtCore import Qt, QStandardPaths
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLineEdit,
    QLabel,
    QSpinBox,
    QPushButton,
    QMessageBox,
    QFormLayout,
    QComboBox,
    QCheckBox,
    QApplication,
    QStyledItemDelegate,
    QHeaderView,
)
from file_names import FileNameDelegate
from build_channel import DEVELOPMENT
from bakuri.renaming.planner import plan_rename
from bakuri.renaming.transaction import apply, undo
from bakuri.domain.rename_rules import fill_down, _text_lines
from bakuri.domain.models import RenameOptions


class TextDelegate(FileNameDelegate):
    def createEditor(self, parent, option, index):
        return (
            super().createEditor(parent, option, index)
            if index.column() in {4, 6}
            and self.parent().window().mode_tabs.currentIndex() == 1
            and not self.parent().window().busy
            else None
        )


def positions(combo):
    for label, value in [
        ("이름 앞", "before"),
        ("이름 뒤", "after"),
        ("특정 문자 앞", "before_marker"),
        ("특정 문자 뒤", "after_marker"),
    ]:
        combo.addItem(label, value)


class RenamePanel(QWidget):
    def __init__(self, window):
        super().__init__()
        self.window = window
        self.files = window.files
        self.setObjectName("renamePanel")
        self.setStyleSheet("""
            QWidget#renamePanel QComboBox {padding:5px 12px;min-height:18px;}
        """)
        self.rows = []
        self.journal = (
            Path(QStandardPaths.writableLocation(QStandardPaths.GenericDataLocation))
            / ("BakuriDevelopment" if DEVELOPMENT else "Bakuri")
            / "rename-history.json"
        )
        self.files.setColumnCount(7)
        self.files.headerItem().setText(6, "추가할 문자열")
        self.files.setColumnWidth(6, 210)
        self.files.setItemDelegate(TextDelegate(self.files))
        self.files.headerItem().setToolTip(
            4,
            "두 번 클릭해 직접 수정하거나, 셀 선택 후 Ctrl+V로 한 열을 붙여넣으세요. 확장자는 유지합니다. 빈 값은 자동 이름으로 돌아갑니다.",
        )
        self.files.headerItem().setToolTip(
            6,
            "두 번 클릭해 수정 · Ctrl+V로 선택 셀부터 체크한 파일에 한 줄씩 붙여넣기 · 빈 줄은 위 문구로 채움",
        )
        self.files.header().setSectionResizeMode(5, QHeaderView.ResizeToContents)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 8, 20, 8)
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form.setVerticalSpacing(6)
        form.setHorizontalSpacing(14)
        layout.addLayout(form)
        self.find = QLineEdit()
        self.replace = QLineEdit()
        line = QHBoxLayout()
        line.setSpacing(8)
        line.addWidget(self.find)
        line.addWidget(QLabel("→"))
        line.addWidget(self.replace)
        form.addRow("찾아 바꾸기", line)
        self.string = QLineEdit()
        self.string_position = QComboBox()
        positions(self.string_position)
        self.string_marker = QLineEdit()
        self.string_marker.setPlaceholderText("처음 일치하는 기준 문자")
        self.string_marker.hide()
        self.text_enabled = QCheckBox("파일별 문구")
        line = QHBoxLayout()
        line.setSpacing(8)
        line.addWidget(self.string, 1)
        line.addWidget(self.text_enabled)
        line.addWidget(self.string_position)
        line.addWidget(self.string_marker)
        self.string_label = QLabel("문자열 추가")
        self.string_label.setMinimumHeight(32)
        self.string_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        form.addRow(self.string_label, line)
        self.base = QLineEdit()
        form.addRow("파일명 새로 쓰기", self.base)
        self.number_enabled = QCheckBox("연번 추가")
        self.start = QSpinBox()
        self.start.setRange(0, 999999)
        self.start.setValue(1)
        self.digits = QSpinBox()
        self.digits.setRange(1, 8)
        self.digits.setValue(1)
        self.number_position = QComboBox()
        positions(self.number_position)
        self.number_position.setCurrentIndex(1)
        self.number_enabled.setMinimumHeight(32)
        self.number_marker = QLineEdit()
        self.number_marker.setPlaceholderText("처음 일치하는 기준 문자")
        self.number_marker.hide()
        self.separator = QComboBox()
        for label, value in [
            ("밑줄 _", "_"),
            ("하이픈 -", "-"),
            ("공백", " "),
            ("마침표 .", "."),
            ("없음", ""),
        ]:
            self.separator.addItem(label, value)
        line = QHBoxLayout()
        line.setSpacing(8)
        line.addWidget(QLabel("시작 번호"))
        line.addWidget(self.start)
        line.addWidget(QLabel("자릿수"))
        line.addWidget(self.digits)
        line.addWidget(self.number_position)
        line.addWidget(self.number_marker)
        line.addWidget(QLabel("구분자"))
        line.addWidget(self.separator)
        form.addRow(self.number_enabled, line)
        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setToolTip(
            "목록: 추가한 전체 파일 · 변경 예정: 체크한 파일 중 이름이 달라지는 파일 · 오류: 체크한 파일의 미리보기 오류"
        )
        layout.addWidget(self.message)
        line = QHBoxLayout()
        line.setSpacing(8)
        self.restore = QPushButton("실행 취소")
        self.restore.setEnabled(False)
        self.run = QPushButton("이름 변경 적용")
        self.run.setObjectName("convert")
        self.run.setFixedSize(164, 44)
        self.restore.setFixedSize(164, 44)
        line.addStretch()
        line.addWidget(self.run)
        line.addWidget(self.restore)
        layout.addLayout(line)
        self.base.textChanged.connect(self.base_changed)
        for field in [self.find, self.replace, self.string, self.string_marker, self.number_marker]:
            field.textChanged.connect(self.refresh)
        for combo in [self.number_position, self.string_position, self.separator]:
            combo.currentIndexChanged.connect(self.refresh)
        for check in [self.number_enabled, self.text_enabled]:
            check.toggled.connect(self.refresh)
        self.start.valueChanged.connect(self.refresh)
        self.digits.valueChanged.connect(self.refresh)
        self.files.changed.connect(self.refresh)
        self.run.clicked.connect(self.execute)
        self.restore.clicked.connect(self.undo)
        self.files.itemChanged.connect(self.cell_changed)
        self.refresh()

    def base_changed(self, value):
        if value:
            self.number_enabled.setChecked(True)
        self.refresh()

    def assign_values(self, values, items=None):
        if items is None:
            items = [
                self.files.item(i)
                for i in range(self.files.count())
                if self.files.item(i).checkState(0) == Qt.Checked
            ]
        if len(items) != len(values):
            raise ValueError("선택 파일 수가 바뀌었습니다. 다시 붙여넣어 주세요.")
        self.files.blockSignals(True)
        try:
            for item, value in zip(items, values):
                item.setText(6, value)
        finally:
            self.files.blockSignals(False)
        self.refresh()

    def cell_changed(self, item, column):
        if column == 4:
            self.files.blockSignals(True)
            try:
                item.setData(4, Qt.UserRole, item.text(4) or None)
            finally:
                self.files.blockSignals(False)
        if column in {4, 6}:
            self.refresh()

    def paste_cells(self, focus):
        if self.window.busy or not (focus is self.files or self.files.isAncestorOf(focus)):
            return False
        mime = QApplication.clipboard().mimeData()
        column = self.files.currentColumn()
        if (
            not mime
            or mime.hasUrls()
            or not mime.hasText()
            or column not in {4, 6}
            or self.files.isColumnHidden(column)
        ):
            return False
        text = mime.text()
        # A normal single-line paste inside an active editor keeps its caret behavior.
        if (
            isinstance(focus, QLineEdit)
            and "\n" not in text
            and "\r" not in text
            and "\t" not in text
        ):
            return False
        first = self.files.indexOfTopLevelItem(self.files.currentItem())
        items = [
            self.files.item(i)
            for i in range(max(0, first), self.files.count())
            if self.files.item(i).checkState(0) == Qt.Checked
        ]
        try:
            values = fill_down(text, len(items)) if column == 6 else _text_lines(text)
            if not values or len(values) > len(items):
                raise ValueError("붙여넣을 줄 수가 남은 체크 파일 수보다 많거나 내용이 없습니다.")
        except ValueError as exc:
            QMessageBox.information(self, "붙여넣기 확인", str(exc))
            return True
        if isinstance(focus, QLineEdit):
            delegate = self.files.itemDelegate()
            delegate.closeEditor.emit(focus, QStyledItemDelegate.RevertModelCache)
        if column == 6:
            self.assign_values(values, items)
            return True
        self.files.blockSignals(True)
        try:
            for item, value in zip(items, values):
                if column == 4:
                    item.setData(4, Qt.UserRole, value or None)
                item.setText(column, value)
        finally:
            self.files.blockSignals(False)
        self.refresh()
        return True

    def refresh(self, *args):
        active = self.text_enabled.isChecked()
        self.files.setColumnHidden(6, self.window.mode_tabs.currentIndex() != 1 or not active)
        self.string.setEnabled(not active)
        self.string_position.setToolTip(
            "파일별 문자열을 붙일 위치" if active else "공통 문자열을 붙일 위치"
        )
        self.string_marker.setVisible(
            self.string_position.currentData() in {"before_marker", "after_marker"}
        )
        self.number_marker.setVisible(
            self.number_position.currentData() in {"before_marker", "after_marker"}
        )
        values = {
            self.files.item(i).data(0, Qt.UserRole): self.files.item(i).text(6)
            for i in range(self.files.count())
        }
        self.rows = plan_rename(
            self.files.checked_paths(),
            RenameOptions(
                find=self.find.text(),
                replace=self.replace.text(),
                string=self.string.text() if not active else "",
                string_position=self.string_position.currentData(),
                string_marker=self.string_marker.text(),
                manual_names={
                    self.files.item(i).data(0, Qt.UserRole): self.files.item(i).data(4, Qt.UserRole)
                    for i in range(self.files.count())
                    if self.files.item(i).data(4, Qt.UserRole) is not None
                },
                base=self.base.text(),
                start=self.start.value(),
                digits=self.digits.value(),
                number_enabled=self.number_enabled.isChecked(),
                number_position=self.number_position.currentData(),
                number_marker=self.number_marker.text(),
                separator=self.separator.currentData(),
                text_by_source=values if active else {},
                text_position=self.string_position.currentData(),
                text_marker=self.string_marker.text(),
            ),
        )
        by_source = {r["source"]: r for r in self.rows}
        self.files.blockSignals(True)
        try:
            for i in range(self.files.count()):
                item = self.files.item(i)
                row = by_source.get(item.data(0, Qt.UserRole))
                item.setFlags(item.flags() | Qt.ItemIsEditable)
                item.setText(4, row["name"] if row else "")
                item.setText(
                    5,
                    (
                        row["error"] or ("변경 가능" if row["changed"] else "변경 없음")
                        if row
                        else "선택 안 됨"
                    ),
                )
                item.setToolTip(4, row["target"] if row else "")
                item.setToolTip(5, row["error"] if row else "")
                item.setForeground(5, QColor("#C42B1C" if row and row["error"] else "#60718A"))
        finally:
            self.files.blockSignals(False)
        count = sum(r["changed"] for r in self.rows)
        errors = sum(bool(r["error"]) for r in self.rows)
        self.run.setEnabled(bool(count) and not errors and not self.window.busy)
        state = ""
        try:
            state = json.loads(self.journal.read_text(encoding="utf-8")).get("state", "")
        except (OSError, ValueError):
            pass
        self.restore.setEnabled(state == "complete" and not self.window.busy)
        self.message.setText(
            f"목록 {self.files.count()}개 / 변경 예정 {count}개 / 오류 {errors}개"
            + (
                " · 미완료 기록을 먼저 확인해 주세요."
                if state in {"working", "recovery_needed"}
                else ""
            )
        )
        if state in {"working", "recovery_needed"}:
            self.run.setEnabled(False)
        self.files.request_name_fit()

    def update_paths(self, entries):
        mapping = {e["original"]: e["current"] for e in entries}
        self.files.blockSignals(True)
        try:
            for i in range(self.files.count()):
                item = self.files.item(i)
                old = item.data(0, Qt.UserRole)
                if old in mapping:
                    path = mapping[old]
                    record = item.data(0, Qt.UserRole + 1)
                    if record:
                        item.setData(0, Qt.UserRole + 1, replace(record, path=path))
                    item.setData(4, Qt.UserRole, None)
                    item.setData(0, Qt.UserRole, path)
                    item.setText(2, Path(path).name)
                    item.setToolTip(2, path)
        finally:
            self.files.blockSignals(False)
        self.files.sync_master()

    def execute(self):
        if self.window.busy:
            return
        try:
            entries = apply(self.rows, self.journal)
            self.update_paths(entries)
            summary = f"{len(entries)}개 이름 변경 완료 · 실행 취소 가능"
            if entries:
                self.window.show_completion(
                    summary, [str(Path(e["current"]).parent) for e in entries]
                )
        except Exception as exc:
            self.refresh()
            QMessageBox.warning(self, "이름 변경 안내", str(exc))

    def undo(self):
        if self.window.busy:
            return
        try:
            entries = undo(self.journal)
            self.update_paths(entries)
            summary = f"{len(entries)}개 원래 이름으로 복원했습니다."
            self.window.show_completion(summary, [str(Path(e["current"]).parent) for e in entries])
        except Exception as exc:
            QMessageBox.warning(self, "되돌리기 안내", str(exc))
