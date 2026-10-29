"""Live preview, stable per-file text assignments, and reversible batch renaming."""
import json
from pathlib import Path
from PySide6.QtCore import Qt,QStandardPaths
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLineEdit,QLabel,QSpinBox,QPushButton,QMessageBox,QFormLayout,QComboBox,QCheckBox,QDialog,QPlainTextEdit,QDialogButtonBox,QApplication,QStyledItemDelegate)
from rename_engine import preview,apply,undo,pasted_lines

class TextDelegate(QStyledItemDelegate):
    def createEditor(self,parent,option,index):
        return super().createEditor(parent,option,index) if index.column()==6 and not self.parent().window().busy else None

def positions(combo):
    for label,value in [('이름 앞','before'),('이름 뒤','after'),('특정 문자 앞','before_marker'),('특정 문자 뒤','after_marker')]:combo.addItem(label,value)

class PasteTextDialog(QDialog):
    def __init__(self,count,parent=None):
        super().__init__(parent);self.count=count;self.values=[];self.setWindowTitle('파일별 문구 붙여넣기');self.resize(500,390)
        layout=QVBoxLayout(self);label=QLabel(f'체크한 파일 {count}개에 위에서부터 한 줄씩 연결합니다.\n엑셀 한 열이나 메모장의 여러 줄을 Ctrl+V로 붙여넣으세요.\n빈 줄은 해당 파일에 문구를 추가하지 않습니다.');label.setWordWrap(True);layout.addWidget(label)
        self.text=QPlainTextEdit();layout.addWidget(self.text)
        mime=QApplication.clipboard().mimeData()
        if mime and mime.hasText() and not mime.hasUrls():self.text.setPlainText(mime.text())
        buttons=QDialogButtonBox(QDialogButtonBox.Ok|QDialogButtonBox.Cancel);buttons.accepted.connect(self.assign);buttons.rejected.connect(self.reject);layout.addWidget(buttons)
    def assign(self):
        try:self.values=pasted_lines(self.text.toPlainText(),self.count)
        except ValueError as exc:QMessageBox.information(self,'문구 개수 확인',str(exc));return
        self.accept()

class RenamePanel(QWidget):
    def __init__(self,window):
        super().__init__();self.window=window;self.files=window.files;self.rows=[]
        self.journal=Path(QStandardPaths.writableLocation(QStandardPaths.GenericDataLocation))/'BakuriDevelopment'/'rename-history.json'
        self.files.setColumnCount(7);self.files.headerItem().setText(6,'붙일 문구 · 두 번 클릭해 수정');self.files.setColumnWidth(6,210);self.files.setItemDelegate(TextDelegate(self.files))
        layout=QVBoxLayout(self);form=QFormLayout();layout.addLayout(form)
        self.find=QLineEdit();self.replace=QLineEdit();line=QHBoxLayout();line.addWidget(self.find);line.addWidget(QLabel('→'));line.addWidget(self.replace);form.addRow('찾아 바꾸기',line)
        self.prefix=QLineEdit();self.suffix=QLineEdit();line=QHBoxLayout();line.addWidget(self.prefix);line.addWidget(QLabel('뒤에 추가'));line.addWidget(self.suffix);form.addRow('앞에 추가',line)
        self.base=QLineEdit();self.base.setPlaceholderText('비우면 기존 이름 유지 · 입력하면 번호 추가가 켜집니다.');form.addRow('이름 통일',self.base)
        self.number_enabled=QCheckBox('번호 추가');self.start=QSpinBox();self.start.setRange(0,999999);self.start.setValue(1);self.digits=QSpinBox();self.digits.setRange(1,8);self.digits.setValue(3)
        self.number_position=QComboBox();positions(self.number_position);self.number_position.setCurrentIndex(1)
        self.number_marker=QLineEdit();self.number_marker.setPlaceholderText('처음 일치하는 기준 문자');self.number_marker.hide()
        self.separator=QComboBox()
        for label,value in [('밑줄 _','_'),('하이픈 -','-'),('공백',' '),('없음','')]:self.separator.addItem(label,value)
        line=QHBoxLayout();line.addWidget(self.number_enabled);line.addWidget(QLabel('시작'));line.addWidget(self.start);line.addWidget(QLabel('자리'));line.addWidget(self.digits);line.addWidget(self.number_position);line.addWidget(self.number_marker);line.addWidget(QLabel('구분자'));line.addWidget(self.separator);form.addRow('번호 / 구분자',line)
        self.paste=QPushButton('여러 줄 붙여넣기');self.clear=QPushButton('선택 문구 비우기');self.text_position=QComboBox();positions(self.text_position)
        self.text_marker=QLineEdit();self.text_marker.setPlaceholderText('처음 일치하는 기준 문자');self.text_marker.hide()
        self.replace_name=QCheckBox('문구를 새 이름으로 사용')
        line=QHBoxLayout();line.addWidget(self.paste);line.addWidget(self.clear);line.addWidget(self.text_position);line.addWidget(self.text_marker);line.addWidget(self.replace_name);form.addRow('파일별 문구',line)
        self.message=QLabel();self.message.setWordWrap(True);layout.addWidget(self.message)
        line=QHBoxLayout();self.restore=QPushButton('마지막 변경 되돌리기');self.run=QPushButton('이름 변경 적용');self.run.setObjectName('convert');line.addWidget(self.restore);line.addStretch();line.addWidget(self.run);layout.addLayout(line)
        self.base.textChanged.connect(self.base_changed)
        for field in [self.find,self.replace,self.prefix,self.suffix,self.number_marker,self.text_marker]:field.textChanged.connect(self.refresh)
        for combo in [self.number_position,self.text_position,self.separator]:combo.currentIndexChanged.connect(self.refresh)
        for check in [self.number_enabled,self.replace_name]:check.toggled.connect(self.refresh)
        self.start.valueChanged.connect(self.refresh);self.digits.valueChanged.connect(self.refresh);self.files.changed.connect(self.refresh)
        self.run.clicked.connect(self.execute);self.restore.clicked.connect(self.undo);self.paste.clicked.connect(self.paste_text);self.clear.clicked.connect(lambda:self.assign_values(['']*len(self.files.checked_paths())))
        self.refresh()
    def base_changed(self,value):
        if value:self.number_enabled.setChecked(True)
        self.refresh()
    def assign_values(self,values):
        items=[self.files.item(i) for i in range(self.files.count()) if self.files.item(i).checkState(0)==Qt.Checked]
        if len(items)!=len(values):raise ValueError('선택 파일 수가 바뀌었습니다. 다시 붙여넣어 주세요.')
        self.files.blockSignals(True)
        try:
            for item,value in zip(items,values):item.setText(6,value)
        finally:self.files.blockSignals(False)
        self.refresh()
    def paste_text(self):
        count=len(self.files.checked_paths())
        if not count:QMessageBox.information(self,'파일 선택','문구를 붙일 파일을 먼저 체크해 주세요.');return
        dialog=PasteTextDialog(count,self)
        if dialog.exec()==QDialog.Accepted:self.assign_values(dialog.values)
    def refresh(self,*args):
        self.number_marker.setVisible(self.number_position.currentData() in {'before_marker','after_marker'});self.text_marker.setVisible(self.text_position.currentData() in {'before_marker','after_marker'} and not self.replace_name.isChecked());self.text_position.setEnabled(not self.replace_name.isChecked())
        values={self.files.item(i).data(0,Qt.UserRole):self.files.item(i).text(6) for i in range(self.files.count())}
        self.rows=preview(self.files.checked_paths(),find=self.find.text(),replace=self.replace.text(),prefix=self.prefix.text(),suffix=self.suffix.text(),base=self.base.text(),start=self.start.value(),digits=self.digits.value(),number_enabled=self.number_enabled.isChecked(),number_position=self.number_position.currentData(),number_marker=self.number_marker.text(),separator=self.separator.currentData(),text_by_source=values,text_position=self.text_position.currentData(),text_marker=self.text_marker.text(),text_mode='replace' if self.replace_name.isChecked() else 'insert')
        by_source={r['source']:r for r in self.rows};self.files.blockSignals(True)
        try:
            for i in range(self.files.count()):
                item=self.files.item(i);row=by_source.get(item.data(0,Qt.UserRole));item.setFlags(item.flags()|Qt.ItemIsEditable)
                item.setText(4,row['name'] if row else '');item.setText(5,row['error'] or ('변경 가능' if row['changed'] else '변경 없음') if row else '선택 안 됨')
                item.setToolTip(4,row['target'] if row else '');item.setToolTip(5,row['error'] if row else '');item.setForeground(5,QColor('#C42B1C' if row and row['error'] else '#60718A'))
        finally:self.files.blockSignals(False)
        count=sum(r['changed'] for r in self.rows);errors=sum(bool(r['error']) for r in self.rows);self.run.setEnabled(bool(count) and not errors and not self.window.busy)
        state=''
        try:state=json.loads(self.journal.read_text(encoding='utf-8')).get('state','')
        except (OSError,ValueError):pass
        self.restore.setEnabled(state=='complete' and not self.window.busy)
        self.message.setText(f'{count}개 변경 예정 · 오류 {errors}개 · 확장자 유지 · 문구 → 번호 → 앞뒤 글자 순서로 적용'+(' · 미완료 기록을 먼저 확인해 주세요.' if state in {'working','recovery_needed'} else ''))
        if state in {'working','recovery_needed'}:self.run.setEnabled(False)
    def update_paths(self,entries):
        mapping={e['original']:e['current'] for e in entries};self.files.blockSignals(True)
        try:
            for i in range(self.files.count()):
                item=self.files.item(i);old=item.data(0,Qt.UserRole)
                if old in mapping:
                    path=mapping[old];item.setData(0,Qt.UserRole,path);item.setText(2,Path(path).name);item.setToolTip(2,path)
        finally:self.files.blockSignals(False)
        self.files.sync_master()
    def execute(self):
        if self.window.busy:return
        try:
            entries=apply(self.rows,self.journal);self.update_paths(entries);summary=f'{len(entries)}개 이름 변경 완료 · 마지막 변경 되돌리기 가능';self.message.setText(summary)
            if entries:self.window.show_completion(summary,[str(Path(e['current']).parent) for e in entries])
        except Exception as exc:self.refresh();QMessageBox.warning(self,'이름 변경 안내',str(exc))
    def undo(self):
        if self.window.busy:return
        try:
            entries=undo(self.journal);self.update_paths(entries);summary=f'{len(entries)}개 원래 이름으로 복원했습니다.';self.message.setText(summary);self.window.show_completion(summary,[str(Path(e['current']).parent) for e in entries])
        except Exception as exc:QMessageBox.warning(self,'되돌리기 안내',str(exc))
