"""Ordered, checked input files with batched duplicate lookup."""
import os,re
from pathlib import Path
from PySide6.QtCore import Qt,Signal,QSize
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (QTreeWidget,QTreeWidgetItem,QHeaderView,QAbstractItemView,QLabel,QCheckBox,QMenu)
from engine import SUPPORTED,SPREADSHEETS,IMAGES
from theme import icon,stylesheet

def natural_key(text):
    return tuple((1,int(p)) if p.isdigit() else (0,p.casefold()) for p in re.split(r'(\d+)',text))

class Files(QTreeWidget):
    changed=Signal()
    def __init__(self):
        super().__init__(); self.setColumnCount(4); self.setHeaderLabels(['','미리보기','파일명','용량'])
        self.setRootIsDecorated(False); self.setAlternatingRowColors(False); self.setStyleSheet(stylesheet())
        self.setUniformRowHeights(True); self.setIndentation(0)

        self.setColumnWidth(0,84); self.setColumnWidth(1,100); self.setColumnWidth(3,115); self.header().setSectionResizeMode(2,QHeaderView.Stretch)
        self.setIconSize(QSize(34,38)); self.setAcceptDrops(True); self.setDragDropMode(QAbstractItemView.InternalMove)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setContextMenuPolicy(Qt.CustomContextMenu); self.customContextMenuRequested.connect(self.context_menu)
        self.selection_caption=QLabel('선택',self.header().viewport()); self.selection_caption.setObjectName('selectionCaption'); self.selection_caption.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.master=QCheckBox(self.header().viewport()); self.master.setTristate(True); self.master.setToolTip('전체 선택 / 해제'); self.master.setAccessibleName('전체 선택')
        self.master.clicked.connect(lambda:self.check_all(Qt.Checked if self.master.checkState()!=Qt.Unchecked else Qt.Unchecked))
        self.header().sectionResized.connect(self.place_master); self.header().geometriesChanged.connect(self.place_master); self.header().sectionMoved.connect(self.place_master); self.itemChanged.connect(lambda *_:self.sync_master()); self.place_master()
    def delete_selected(self):
        if not self.isEnabled(): return
        for item in self.selectedItems(): self.takeTopLevelItem(self.indexOfTopLevelItem(item))
        self.sync_master()
    def keyPressEvent(self,event):
        if event.key()==Qt.Key_Delete: self.delete_selected(); event.accept()
        else: super().keyPressEvent(event)
    def context_menu(self,point):
        item=self.itemAt(point)
        if item is None: return
        if not item.isSelected(): self.clearSelection(); item.setSelected(True)
        menu=QMenu(self); menu.addAction('목록에서 삭제',self.delete_selected); menu.exec(self.viewport().mapToGlobal(point))
    def place_master(self,*_):
        x=self.header().sectionViewportPosition(0);h=max(36,self.header().height())
        self.master.setGeometry(x+8,(h-24)//2,20,24); self.selection_caption.setGeometry(x+34,0,39,h)
    def sync_master(self):
        n=self.count(); c=sum(self.item(i).checkState(0)==Qt.Checked for i in range(n))
        self.master.setCheckState(Qt.Unchecked if c==0 else Qt.Checked if c==n else Qt.PartiallyChecked); self.changed.emit()
    def count(self): return self.topLevelItemCount()
    def item(self,i): return self.topLevelItem(i)
    def takeItem(self,i):
        item=self.takeTopLevelItem(i); self.sync_master(); return item
    def clear(self): super().clear(); self.sync_master()
    def dragEnterEvent(self,e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()
        else: super().dragEnterEvent(e)
    def dragMoveEvent(self,e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()
        else: super().dragMoveEvent(e)
    def dropEvent(self,e):
        if e.mimeData().hasUrls(): self.add_paths([u.toLocalFile() for u in e.mimeData().urls()]); e.acceptProposedAction()
        else:
            index=self.indexAt(e.position().toPoint())
            # Tree rows must stay flat: only between-row drops are allowed.
            if self.dropIndicatorPosition()==QAbstractItemView.OnItem: e.ignore(); return
            super().dropEvent(e)
        self.sync_master()
    def add_paths(self,paths):
        existing={os.path.normcase(self.item(i).data(0,Qt.UserRole)) for i in range(self.count())}
        for p in paths:
            path=Path(p).resolve()
            key=os.path.normcase(str(path))
            if path.is_file() and path.suffix.lower() in SUPPORTED and key not in existing:
                existing.add(key)
                size=path.stat().st_size; label=f'{size/1048576:.1f} MB' if size>=1048576 else f'{size/1024:.1f} KB'
                item=QTreeWidgetItem(['','',path.name,label]); item.setData(0,Qt.UserRole,str(path)); item.setToolTip(2,str(path))
                item.setIcon(1,QIcon(str(path)) if path.suffix.lower() in IMAGES else icon('xlsx' if path.suffix.lower() in SPREADSHEETS else 'hwpx' if path.suffix.lower() in {'.hwp','.hwpx'} else 'pdf' if path.suffix.lower()=='.pdf' else 'odt'))
                item.setFlags((item.flags()|Qt.ItemIsUserCheckable)&~Qt.ItemIsDropEnabled); item.setCheckState(0,Qt.Checked); item.setSizeHint(0,QSize(70,60)); self.addTopLevelItem(item)
        self.sync_master()
    def sort_names(self):
        items=[self.takeTopLevelItem(0) for _ in range(self.count())]
        self.addTopLevelItems(sorted(items,key=lambda item:natural_key(item.text(2)))); self.sync_master()
    def check_all(self,state):
        self.blockSignals(True)
        for i in range(self.count()): self.item(i).setCheckState(0,state)
        self.blockSignals(False); self.sync_master()
    def checked_paths(self): return [self.item(i).data(0,Qt.UserRole) for i in range(self.count()) if self.item(i).checkState(0)==Qt.Checked]

