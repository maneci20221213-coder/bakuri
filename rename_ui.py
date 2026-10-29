"""Live rename preview for the checked files in the shared input list."""
import json
from pathlib import Path
from PySide6.QtCore import Qt,QStandardPaths
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLineEdit,QLabel,QSpinBox,QPushButton,QMessageBox,QFormLayout
from rename_engine import preview,apply,undo

class RenamePanel(QWidget):
    def __init__(self,window):
        super().__init__();self.window=window;self.files=window.files;self.rows=[]
        self.journal=Path(QStandardPaths.writableLocation(QStandardPaths.GenericDataLocation))/'BakuriDevelopment'/'rename-history.json'
        layout=QVBoxLayout(self);form=QFormLayout();layout.addLayout(form)
        self.find=QLineEdit();self.replace=QLineEdit();line=QHBoxLayout();line.addWidget(self.find);line.addWidget(QLabel('→'));line.addWidget(self.replace);form.addRow('찾아 바꾸기',line)
        self.prefix=QLineEdit();self.suffix=QLineEdit();line=QHBoxLayout();line.addWidget(self.prefix);line.addWidget(QLabel('뒤에 추가'));line.addWidget(self.suffix);form.addRow('앞에 추가',line)
        self.base=QLineEdit();self.base.setPlaceholderText('비워 두면 현재 이름 유지 · 입력하면 이름_001 형식');self.start=QSpinBox();self.start.setRange(0,999999);self.start.setValue(1);self.digits=QSpinBox();self.digits.setRange(1,8);self.digits.setValue(3)
        line=QHBoxLayout();line.addWidget(self.base,1);line.addWidget(QLabel('시작 번호'));line.addWidget(self.start);line.addWidget(QLabel('자리 수'));line.addWidget(self.digits);form.addRow('이름 통일',line)
        self.message=QLabel('확장자는 유지됩니다. 체크한 파일을 목록 순서대로 변경합니다.');self.message.setWordWrap(True);layout.addWidget(self.message)
        line=QHBoxLayout();self.restore=QPushButton('마지막 변경 되돌리기');self.run=QPushButton('이름 변경 적용');self.run.setObjectName('convert');line.addWidget(self.restore);line.addStretch();line.addWidget(self.run);layout.addLayout(line)
        for field in [self.find,self.replace,self.prefix,self.suffix,self.base]:field.textChanged.connect(self.refresh)
        self.start.valueChanged.connect(self.refresh);self.digits.valueChanged.connect(self.refresh);self.files.changed.connect(self.refresh)
        self.run.clicked.connect(self.execute);self.restore.clicked.connect(self.undo)
        self.refresh()
    def refresh(self,*args):
        self.rows=preview(self.files.checked_paths(),find=self.find.text(),replace=self.replace.text(),prefix=self.prefix.text(),suffix=self.suffix.text(),base=self.base.text(),start=self.start.value(),digits=self.digits.value())
        by_source={r['source']:r for r in self.rows}
        self.files.blockSignals(True)
        for i in range(self.files.count()):
            item=self.files.item(i);row=by_source.get(item.data(0,Qt.UserRole))
            item.setText(4,row['name'] if row else '');item.setText(5,row['error'] or ('변경 가능' if row['changed'] else '변경 없음') if row else '선택 안 됨')
            item.setToolTip(4,row['target'] if row else '');item.setToolTip(5,row['error'] if row else '')
            item.setForeground(5,QColor('#C42B1C' if row and row['error'] else '#60718A'))
        self.files.blockSignals(False)
        count=sum(r['changed'] for r in self.rows);errors=sum(bool(r['error']) for r in self.rows)
        self.run.setEnabled(bool(count) and not errors and not self.window.busy)
        state=''
        try:state=json.loads(self.journal.read_text(encoding='utf-8')).get('state','')
        except (OSError,ValueError):pass
        self.restore.setEnabled(state=='complete' and not self.window.busy)
        self.message.setText(f'{count}개 변경 예정 · 오류 {errors}개 · 확장자 유지 · 목록 순서대로 번호 부여'+(' · 미완료 기록이 있습니다. 기록 확인 전 추가 변경을 피해주세요.' if state in {'working','recovery_needed'} else ''))
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
        # Apply the displayed snapshot; the engine rejects any changed source.
        try:
            entries=apply(self.rows,self.journal);self.update_paths(entries)
            self.message.setText(f'{len(entries)}개 이름 변경 완료 · 마지막 변경 되돌리기 가능')
        except Exception as exc:
            self.refresh();QMessageBox.warning(self,'이름 변경 안내',str(exc))
    def undo(self):
        if self.window.busy:return
        try:
            entries=undo(self.journal);self.update_paths(entries);self.message.setText(f'{len(entries)}개 원래 이름으로 복원했습니다.')
        except Exception as exc:QMessageBox.warning(self,'되돌리기 안내',str(exc))
