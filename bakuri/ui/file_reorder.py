"""Live row insertion preview, continuous edge scrolling and rollback on cancelled drag."""

from PySide6.QtCore import Qt, QTimer, QPoint
from PySide6.QtGui import QCursor
from PySide6.QtCore import QItemSelectionModel
from PySide6.QtWidgets import QLabel, QAbstractItemView


class FileReorder:
    def __init__(self, view):
        self.view = view
        self.active = False
        self.committed = False
        self.original = []
        self.moving = ()
        self.original_scroll = 0
        self.gap = QLabel(view.viewport())
        self.gap.setAlignment(Qt.AlignCenter)
        self.gap.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.gap.setStyleSheet(
            "background:#EFF6FF;color:#2E83F2;border:2px dashed #2E83F2;border-radius:5px;font-weight:600;"
        )
        self.gap.hide()
        self.timer = QTimer(view)
        self.timer.setInterval(30)
        self.timer.timeout.connect(self.tick)

    def begin(self, selection=None):
        if self.active:
            return False
        view = self.view
        self.original = [view.item(i) for i in range(view.count())]
        selected_ids = None if selection is None else {id(item) for item in selection}
        self.moving = tuple(
            item
            for item in self.original
            if (item.isSelected() if selected_ids is None else id(item) in selected_ids)
        )
        if not self.moving:
            return False
        self.original_scroll = view.verticalScrollBar().value()
        self.committed = False
        self.active = True
        self.timer.start()
        return True

    def update_at(self, point):
        if not self.active:
            return
        view = self.view
        point = QPoint(
            max(0, min(point.x(), view.viewport().width() - 1)),
            max(0, min(point.y(), view.viewport().height() - 1)),
        )
        hit = view.itemAt(point)
        if hit is not None and any(hit is item for item in self.moving):
            self.show_gap()
            return
        current = [view.item(i) for i in range(view.count())]
        slot = view.indexOfTopLevelItem(hit) if hit is not None else len(current)
        if hit is not None and point.y() > view.visualItemRect(hit).center().y():
            slot += 1
        moving_ids = {id(item) for item in self.moving}
        remaining = [item for item in current if id(item) not in moving_ids]
        insertion = sum(id(item) not in moving_ids for item in current[:slot])
        desired = remaining[:insertion] + list(self.moving) + remaining[insertion:]
        if [id(item) for item in desired] != [id(item) for item in current]:
            scroll = view.verticalScrollBar().value()
            blocked = view.blockSignals(True)
            try:
                for item in self.moving:
                    view.takeTopLevelItem(view.indexOfTopLevelItem(item))
                view.insertTopLevelItems(insertion, self.moving)
                for item in self.moving:
                    item.setSelected(True)
                view.setCurrentItem(self.moving[0], 2, QItemSelectionModel.NoUpdate)
                view.doItemsLayout()
                view.verticalScrollBar().setValue(scroll)
            finally:
                view.blockSignals(blocked)
        self.show_gap()

    def show_gap(self):
        if not self.active:
            return
        view = self.view
        # Show one row-sized destination marker regardless of the selected count.
        rows = sorted(view.indexOfTopLevelItem(item) for item in self.moving)
        if not rows or rows != list(range(rows[0], rows[0] + len(rows))):
            self.gap.hide()
            return
        rect = view.visualItemRect(self.moving[0])
        rect.setLeft(1)
        rect.setRight(view.viewport().width() - 2)
        rect = rect.intersected(view.viewport().rect())
        if rect.isEmpty():
            self.gap.hide()
            return
        self.gap.setGeometry(rect)
        self.gap.setText(f"{len(self.moving)}개 파일을 이 위치로 이동")
        self.gap.show()
        self.gap.raise_()

    def tick(self):
        if not self.active:
            return
        view = self.view
        point = view.viewport().mapFromGlobal(QCursor.pos())
        if point.x() < -32 or point.x() > view.viewport().width() + 32:
            return
        height = view.viewport().height()
        # A stationary pointer just outside the list keeps scrolling until the end.
        delta = 0
        if point.y() < 28:
            delta = -min(24, max(4, (28 - point.y()) // 2))
        elif point.y() > height - 28:
            delta = min(24, max(4, (point.y() - (height - 28)) // 2))
        if delta:
            bar = view.verticalScrollBar()
            bar.setValue(bar.value() + delta)
            self.update_at(point)

    def drop(self, point):
        self.update_at(point)
        self.committed = True

    def finish(self):
        if not self.active:
            return
        view = self.view
        self.timer.stop()
        self.gap.hide()
        self.active = False
        anchor = self.moving[0]
        if not self.committed:
            blocked = view.blockSignals(True)
            try:
                while view.count():
                    view.takeTopLevelItem(0)
                view.addTopLevelItems(self.original)
                for item in self.moving:
                    item.setSelected(True)
                view.setCurrentItem(anchor, 2, QItemSelectionModel.NoUpdate)
                view.doItemsLayout()
                view.verticalScrollBar().setValue(self.original_scroll)
            finally:
                view.blockSignals(blocked)
        else:
            view.sync_master()

            # Preview refresh/column fitting may queue a layout pass; anchor after it.
            def reveal():
                if view.indexOfTopLevelItem(anchor) >= 0:
                    view.scrollToItem(anchor, QAbstractItemView.EnsureVisible)

            QTimer.singleShot(0, reveal)
        self.original = []
        self.moving = ()
