"""Compression controls, completion details, and transparent job percentage UI."""
from pathlib import Path
from PySide6.QtCore import Qt,Signal,QPoint,QUrl
from PySide6.QtGui import QColor,QDesktopServices
from PySide6.QtWidgets import (QApplication,QWidget,QLabel,QPushButton,QVBoxLayout,QFormLayout,QComboBox,QCheckBox,QDialog,QDialogButtonBox,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QGraphicsDropShadowEffect)
from compression import PROFILES,RATIO_PROFILES
from theme import stylesheet

def add_profiles(combo):
    for value,settings in RATIO_PROFILES.items():combo.addItem(settings['label'],value)

def read_options(settings):
    profile=settings.value('compress_profile','p80')
    return dict(profile=profile if profile in RATIO_PROFILES else 'p80',protect_text=settings.value('compress_protect',False,type=bool),strip_metadata=settings.value('compress_strip',False,type=bool))

class CompressionDialog(QDialog):
    def __init__(self,settings,parent=None):
        super().__init__(parent);self.settings=settings;self.setWindowTitle('용량 축소');self.setStyleSheet(stylesheet());self.setMinimumWidth(400)
        form=QFormLayout(self);self.profile=QComboBox();add_profiles(self.profile);options=read_options(settings);self.profile.setCurrentIndex(self.profile.findData(options['profile']));form.addRow('해상도 축소',self.profile)
        self.hint=QLabel();self.hint.setWordWrap(True);self.hint.setMaximumWidth(430);form.addRow(self.hint);self.profile.currentIndexChanged.connect(self.update_hint);self.update_hint()
        self.protect=QCheckBox('글자 보호 강화 · 이미지 해상도 유지');self.protect.setChecked(options['protect_text']);form.addRow(self.protect)
        self.strip=QCheckBox('위치정보 등 메타데이터 삭제');self.strip.setChecked(options['strip_metadata']);form.addRow(self.strip)
        self.remember=QCheckBox('다음부터 팝업에서 이 설정으로 바로 실행');self.remember.setChecked(settings.value('compress_direct',False,type=bool));form.addRow(self.remember)
        note=QLabel('원본은 보존하며 파일명 뒤에 _용량축소를 붙입니다. 사진은 JPEG로 저장될 수 있고, 투명 이미지는 투명도를 유지합니다.');note.setWordWrap(True);note.setMaximumWidth(430);form.addRow(note)
        buttons=QDialogButtonBox();buttons.addButton('용량 축소 시작',QDialogButtonBox.AcceptRole);buttons.addButton('취소',QDialogButtonBox.RejectRole);buttons.accepted.connect(self.save);buttons.rejected.connect(self.reject);form.addRow(buttons)
    def update_hint(self):
        ratio=RATIO_PROFILES[self.profile.currentData()]['ratio']
        self.hint.setText(f'가로·세로를 각각 원본의 {ratio:.0%}로 줄입니다. 예: 4000×3000 → {round(4000*ratio)}×{round(3000*ratio)}. PDF는 내부 이미지에 적용하며 글자·도형·용지 크기는 유지합니다. 파일 용량이 줄어드는 정도는 파일마다 다릅니다. 작은 글자는 흐려질 수 있습니다.')
    def options(self):return dict(profile=self.profile.currentData(),protect_text=self.protect.isChecked(),strip_metadata=self.strip.isChecked())
    def save(self):
        options=self.options();s=self.settings;s.setValue('compress_profile',options['profile']);s.setValue('compress_protect',options['protect_text']);s.setValue('compress_strip',options['strip_metadata']);s.setValue('compress_direct',self.remember.isChecked());s.sync();self.accept()

def size_text(value):return f'{value/1_000_000:.2f} MB' if value>=1_000_000 else f'{value/1000:.1f} KB'

class CompressionResults(QDialog):
    def __init__(self,rows,parent=None):
        super().__init__(parent);self.setWindowTitle('용량 축소 결과');self.resize(820,400);self.setStyleSheet(stylesheet());layout=QVBoxLayout(self)
        self.table=QTableWidget(len(rows),5);self.table.setHorizontalHeaderLabels(['파일명','변경 전','변경 후','절감','결과']);self.table.setEditTriggers(QAbstractItemView.NoEditTriggers);self.table.setSelectionBehavior(QAbstractItemView.SelectRows);self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.Stretch);self.table.horizontalHeader().setSectionResizeMode(4,QHeaderView.ResizeToContents)
        for index,row in enumerate(rows):
            reduction=(1-row['after']/row['before'])*100 if row['before'] else 0
            values=[Path(row['source']).name,size_text(row['before']),size_text(row['after']),f'{reduction:.1f}%',row['status']]
            for column,value in enumerate(values):
                item=QTableWidgetItem(value);item.setToolTip(row['detail']);self.table.setItem(index,column,item)
            self.table.item(index,0).setData(Qt.UserRole,row.get('output') or row['source'])
        self.table.cellDoubleClicked.connect(self.open_folder);layout.addWidget(self.table)
        hint=QLabel('결과에 마우스를 올리면 상세 이유를 볼 수 있습니다. 행을 두 번 클릭하면 저장 폴더를 엽니다.');layout.addWidget(hint)
        close=QPushButton('닫기');close.clicked.connect(self.accept);layout.addWidget(close,0,Qt.AlignRight)
    def open_folder(self,row,column):
        path=Path(self.table.item(row,0).data(Qt.UserRole));QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent)))
