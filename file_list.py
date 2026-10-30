"""Ordered, checked input files with batched duplicate lookup."""

import os, re
from pathlib import Path
from PySide6.QtCore import Qt, Signal, QSize, QTimer, QEvent, QItemSelectionModel
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QTreeWidget,
    QTreeWidgetItem,
    QHeaderView,
    QAbstractItemView,
    QLabel,
    QCheckBox,
    QMenu,
)
from bakuri.domain.formats import SUPPORTED, SPREADSHEETS, IMAGES
from theme import icon, stylesheet
from file_names import FileNameDelegate
from bakuri.domain.models import InputFile
from bakuri.ui.file_reorder import FileReorder


def natural_key(text):
    return tuple(
        (1, int(p)) if p.isdigit() else (0, p.casefold()) for p in re.split(r"(\d+)", text)
    )


class Files(QTreeWidget):
    changed = Signal()
    paste_requested = Signal()

    def __init__(self, allow_all=False):
        super().__init__()
        self.allow_all = allow_all
        self.setColumnCount(4)
        self.setHeaderLabels(["", "미리보기", "파일명", "용량"])
        self.setRootIsDecorated(False)
        self.setAlternatingRowColors(False)
        self.setStyleSheet(stylesheet())
        self.setUniformRowHeights(False)
        self.setIndentation(0)
        self.setItemDelegate(FileNameDelegate(self))

        self.header().setStretchLastSection(False)
        self.header().setSectionResizeMode(QHeaderView.Interactive)
        self.setColumnWidth(0, 84)
        self.setColumnWidth(1, 100)
        self.setColumnWidth(2, 420)
        self.setColumnWidth(3, 115)
        self.setIconSize(QSize(34, 38))
        self.setAcceptDrops(True)
        self.setDragDropMode(QAbstractItemView.DropOnly)
        self.setAutoScroll(False)
        self.setVerticalScrollMode(QAbstractItemView.ScrollPerPixel)
        self.setDropIndicatorShown(False)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.context_menu)
        self.selection_caption = QLabel("선택", self.header().viewport())
        self.selection_caption.setObjectName("selectionCaption")
        self.selection_caption.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.master = QCheckBox(self.header().viewport())
        self.master.setTristate(True)
        self.master.setToolTip("전체 선택 / 해제")
        self.master.setAccessibleName("전체 선택")
        self.master.clicked.connect(
            lambda: self.check_all(
                Qt.Checked if self.master.checkState() != Qt.Unchecked else Qt.Unchecked
            )
        )
        self.header().sectionResized.connect(self.place_master)
        self.header().geometriesChanged.connect(self.place_master)
        self.header().sectionMoved.connect(self.place_master)
        self.itemChanged.connect(lambda item, column: self.sync_master() if column == 0 else None)
        self.place_master()
        self.manual_sizing = False
        self.header().viewport().installEventFilter(self)
        self.fit_timer = QTimer(self)
        self.fit_timer.setSingleShot(True)
        self.fit_timer.timeout.connect(self.fit_name_columns)
        self.reflow_timer = QTimer(self)
        self.reflow_timer.setSingleShot(True)
        self.reflow_timer.timeout.connect(self.reflow_names)
        self.changed.connect(self.request_name_fit)
        self.header().sectionResized.connect(self.name_column_resized)
        self.reorder = FileReorder(self)
        self.drag_origin = None
        self.deferred_selection = None

    def name_column_resized(self, column, *_):
        self.reflow_timer.start(0)
        if column == 5:
            self.request_name_fit()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if hasattr(self, "fit_timer"):
            self.request_name_fit()

    def eventFilter(self, obj, event):
        if obj is self.header().viewport():
            if event.type() == QEvent.MouseButtonPress:
                self.manual_sizing = True
                self.fit_timer.stop()
            elif event.type() == QEvent.MouseButtonRelease:
                self.manual_sizing = False
        return super().eventFilter(obj, event)

    def request_name_fit(self):
        if not self.manual_sizing and not self.reorder.active:
            self.fit_timer.start(0)

    def reflow_names(self):
        self.scheduleDelayedItemsLayout()
        self.viewport().update()

    def fit_name_columns(self):
        columns = [c for c in (2, 4) if c < self.columnCount() and not self.isColumnHidden(c)]
        if not columns:
            return
        other = sum(
            self.columnWidth(c)
            for c in range(self.columnCount())
            if c not in columns and not self.isColumnHidden(c)
        )
        budget = max(1, self.viewport().width() - other - 2)
        metrics = self.fontMetrics()
        desired = [
            max(
                160,
                max(
                    (
                        metrics.horizontalAdvance(self.item(i).text(c)) + 24
                        for i in range(self.count())
                    ),
                    default=0,
                ),
            )
            for c in columns
        ]
        if sum(desired) > budget:
            minimum = min(160, budget // len(columns))
            extra = max(0, budget - minimum * len(columns))
            weights = [max(1, d - minimum) for d in desired]
            widths = [minimum + int(extra * w / sum(weights)) for w in weights]
            widths[-1] += budget - sum(widths)
        else:
            widths = desired
        for column, width in zip(columns, widths):
            self.setColumnWidth(column, width)
        self.reflow_names()

    def delete_selected(self):
        if hasattr(self, "reorder") and self.reorder.active:
            self.finish_reorder(False)
        if not self.isEnabled():
            return
        for item in self.selectedItems():
            self.takeTopLevelItem(self.indexOfTopLevelItem(item))
        self.sync_master()

    def keyPressEvent(self, event):
        if self.reorder.active:
            if event.key() == Qt.Key_Escape:
                self.finish_reorder(False)
            event.accept()
            return
        if event.key() == Qt.Key_Delete:
            self.delete_selected()
            event.accept()
        else:
            super().keyPressEvent(event)

    def context_menu(self, point):
        item = self.itemAt(point)
        menu = QMenu(self)
        paste = menu.addAction("파일 붙여넣기 (Ctrl+V)", self.paste_requested.emit)
        mime = QApplication.clipboard().mimeData()
        paste.setEnabled(
            bool(mime and any(u.isLocalFile() for u in mime.urls())) and self.isEnabled()
        )
        if item is not None:
            if not item.isSelected():
                self.clearSelection()
                item.setSelected(True)
            menu.addSeparator()
            menu.addAction("목록에서 삭제", self.delete_selected)
        menu.exec(self.viewport().mapToGlobal(point))

    def place_master(self, *_):
        x = self.header().sectionViewportPosition(0)
        h = max(36, self.header().height())
        self.master.setGeometry(x + 8, (h - 24) // 2, 20, 24)
        self.selection_caption.setGeometry(x + 34, 0, 39, h)

    def sync_master(self):
        n = self.count()
        c = sum(self.item(i).checkState(0) == Qt.Checked for i in range(n))
        self.master.setCheckState(
            Qt.Unchecked if c == 0 else Qt.Checked if c == n else Qt.PartiallyChecked
        )
        self.changed.emit()

    def count(self):
        return self.topLevelItemCount()

    def item(self, i):
        return self.topLevelItem(i)

    def takeItem(self, i):
        if hasattr(self, "reorder") and self.reorder.active:
            self.finish_reorder(False)
        item = self.takeTopLevelItem(i)
        self.sync_master()
        return item

    def clear(self):
        if hasattr(self, "reorder") and self.reorder.active:
            self.finish_reorder(False)
        super().clear()
        self.sync_master()

    def mousePressEvent(self, event):
        point = event.position().toPoint()
        item = self.itemAt(point)
        self.deferred_selection = None
        # Keep an existing block until release decides between click and drag.
        if (
            event.button() == Qt.LeftButton
            and event.modifiers() == Qt.NoModifier
            and point.x() > 36
            and item is not None
            and item.isSelected()
            and len(self.selectedItems()) > 1
        ):
            self.deferred_selection = item
            self.setCurrentItem(
                item, max(0, self.columnAt(point.x())), QItemSelectionModel.NoUpdate
            )
            self.setFocus(Qt.MouseFocusReason)
            event.accept()
        else:
            super().mousePressEvent(event)
        self.drag_origin = (
            point
            if event.button() == Qt.LeftButton and item is not None and point.x() > 36
            else None
        )

    def mouseMoveEvent(self, event):
        if self.drag_origin is not None and event.buttons() & Qt.LeftButton and self.isEnabled():
            if (
                not self.reorder.active
                and (event.position().toPoint() - self.drag_origin).manhattanLength()
                >= QApplication.startDragDistance()
            ):
                if self.reorder.begin():
                    self.viewport().grabMouse()
                    self.viewport().setCursor(Qt.ClosedHandCursor)
            if self.reorder.active:
                self.reorder.update_at(event.position().toPoint())
                event.accept()
                return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self.reorder.active and event.button() == Qt.LeftButton:
            self.finish_reorder(
                self.viewport().rect().contains(event.position().toPoint()),
                event.position().toPoint(),
            )
            event.accept()
            return
        self.drag_origin = None
        if self.deferred_selection is not None and event.button() == Qt.LeftButton:
            item = self.deferred_selection
            self.deferred_selection = None
            self.setCurrentItem(
                item,
                max(0, self.columnAt(int(event.position().x()))),
                QItemSelectionModel.ClearAndSelect | QItemSelectionModel.Rows,
            )
            self.setState(QAbstractItemView.NoState)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def finish_reorder(self, commit, point=None):
        if self.reorder.active:
            if commit:
                self.reorder.drop(point)
            self.reorder.finish()
        self.drag_origin = None
        self.deferred_selection = None
        self.viewport().releaseMouse()
        self.viewport().unsetCursor()
        self.setState(QAbstractItemView.NoState)

    def viewportEvent(self, event):
        if event.type() == QEvent.UngrabMouse and hasattr(self, "reorder") and self.reorder.active:
            self.reorder.finish()
            self.drag_origin = None
            self.deferred_selection = None
            self.viewport().unsetCursor()
        return super().viewportEvent(event)

    def hideEvent(self, event):
        if hasattr(self, "reorder") and self.reorder.active:
            self.finish_reorder(False)
        super().hideEvent(event)

    def dragEnterEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            e.ignore()

    def dragMoveEvent(self, e):
        if e.mimeData().hasUrls():
            e.acceptProposedAction()
        else:
            e.ignore()

    def dropEvent(self, e):
        if e.mimeData().hasUrls():
            self.add_paths([u.toLocalFile() for u in e.mimeData().urls()])
            e.acceptProposedAction()
        else:
            e.ignore()

    def add_paths(self, paths):
        if hasattr(self, "reorder") and self.reorder.active:
            self.finish_reorder(False)
        existing = {
            os.path.normcase(self.item(i).data(0, Qt.UserRole)) for i in range(self.count())
        }
        for p in paths:
            path = Path(p).absolute() if self.allow_all else Path(p).resolve()
            key = os.path.normcase(str(path))
            if (
                path.is_file()
                and (self.allow_all or path.suffix.lower() in SUPPORTED)
                and key not in existing
            ):
                existing.add(key)
                size = path.stat().st_size
                label = f"{size/1048576:.1f} MB" if size >= 1048576 else f"{size/1024:.1f} KB"
                item = QTreeWidgetItem(["", "", path.name, label])
                item.setData(0, Qt.UserRole, str(path))
                item.setData(0, Qt.UserRole + 1, InputFile(str(path)))
                item.setToolTip(2, str(path))
                item.setIcon(
                    1,
                    (
                        QIcon(str(path))
                        if path.suffix.lower() in IMAGES
                        else icon(
                            "xlsx"
                            if path.suffix.lower() in SPREADSHEETS
                            else (
                                "hwpx"
                                if path.suffix.lower() in {".hwp", ".hwpx"}
                                else "pdf" if path.suffix.lower() == ".pdf" else "odt"
                            )
                        )
                    ),
                )
                item.setFlags((item.flags() | Qt.ItemIsUserCheckable) & ~Qt.ItemIsDropEnabled)
                item.setCheckState(0, Qt.Checked)
                item.setSizeHint(0, QSize(70, 48 if self.property("compactRows") else 60))
                self.addTopLevelItem(item)
        self.sync_master()

    def sort_names(self):
        if hasattr(self, "reorder") and self.reorder.active:
            self.finish_reorder(False)
        items = [self.takeTopLevelItem(0) for _ in range(self.count())]
        self.addTopLevelItems(sorted(items, key=lambda item: natural_key(item.text(2))))
        self.sync_master()

    def check_all(self, state):
        self.blockSignals(True)
        for i in range(self.count()):
            self.item(i).setCheckState(0, state)
        self.blockSignals(False)
        self.sync_master()

    def checked_paths(self):
        return [
            self.item(i).data(0, Qt.UserRole)
            for i in range(self.count())
            if self.item(i).checkState(0) == Qt.Checked
        ]

    def inputs_for(self, paths):
        """Freeze ordered inputs on the GUI thread, preserving IDs when listed."""
        by_path = {
            self.item(i).data(0, Qt.UserRole): self.item(i).data(0, Qt.UserRole + 1)
            for i in range(self.count())
        }
        return tuple(by_path.get(str(path)) or InputFile(str(path)) for path in paths)
