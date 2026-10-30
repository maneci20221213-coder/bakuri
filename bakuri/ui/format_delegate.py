"""Disabled output formats remain legible and unselectable."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QStyleOptionViewItem, QStyledItemDelegate


class OutputFormatDelegate(QStyledItemDelegate):
    def paint(self, painter, option, index):
        if not index.flags() & Qt.ItemIsEnabled:
            opt = QStyleOptionViewItem(option)
            self.initStyleOption(opt, index)
            painter.save()
            painter.fillRect(opt.rect, QColor("#F2F5F9"))
            painter.setPen(QColor("#A4AFBD"))
            painter.setFont(opt.font)
            painter.drawText(
                opt.rect.adjusted(6, 0, -4, 0), Qt.AlignVCenter | Qt.AlignLeft, opt.text
            )
            painter.restore()
        else:
            super().paint(painter, option, index)
