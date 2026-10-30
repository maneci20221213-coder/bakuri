"""Reorder is a view-only transaction: preserve rows, cancel safely, anchor the destination."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import QPoint, Qt, QMimeData, QUrl, QPointF
from PySide6.QtGui import QDropEvent
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from file_list import Files

APP = QApplication.instance() or QApplication([])


class ReorderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.paths = [Path(self.temp.name) / f"{i:02}.pdf" for i in range(35)]
        for path in self.paths:
            path.write_bytes(b"original")
        self.view = Files(allow_all=True)
        self.view.setColumnCount(7)
        self.view.add_paths(list(map(str, self.paths)))
        self.view.resize(850, 380)
        self.view.show()
        QTest.qWait(20)
        self.original = [self.view.item(i) for i in range(self.view.count())]
        for i, item in enumerate(self.original):
            item.setText(6, f"문구{i}")
            item.setData(4, Qt.UserRole, f"직접{i}.pdf")

    def tearDown(self):
        self.view.reorder.finish()
        self.view.hide()
        self.view.deleteLater()
        self.temp.cleanup()

    def names(self):
        return [self.view.item(i).text(2) for i in range(self.view.count())]

    def select(self, indexes):
        self.view.clearSelection()
        for i in indexes:
            self.original[i].setSelected(True)
        self.assertTrue(self.view.reorder.begin())
        self.view.reorder.timer.stop()

    def test_live_insertion_moves_surrounding_rows_and_preserves_per_file_values(self):
        self.select([1, 3])
        target = self.view.visualItemRect(self.original[5])
        self.view.reorder.update_at(QPoint(200, target.top()))
        self.assertEqual(
            self.names()[:7], ["00.pdf", "02.pdf", "04.pdf", "01.pdf", "03.pdf", "05.pdf", "06.pdf"]
        )
        self.assertTrue(self.view.reorder.gap.isVisible())
        self.view.reorder.committed = True
        self.view.reorder.finish()
        QTest.qWait(20)
        for i, item in enumerate(self.original):
            self.assertEqual(item.text(6), f"문구{i}")
            self.assertEqual(item.data(4, Qt.UserRole), f"직접{i}.pdf")
            self.assertEqual(item.data(0, Qt.UserRole + 1).path, str(self.paths[i]))
            self.assertIsNone(item.parent())
            self.assertEqual(item.checkState(0), Qt.Checked)
        self.assertEqual(
            len({self.view.item(i).data(0, Qt.UserRole + 1).file_id for i in range(35)}), 35
        )

    def test_cancel_restores_original_order_and_scroll_without_emitting_change(self):
        self.view.verticalScrollBar().setValue(300)
        initial = self.view.verticalScrollBar().value()
        self.select([0])
        with patch.object(self.view, "sync_master") as changed:
            self.view.reorder.update_at(QPoint(200, self.view.viewport().height() - 1))
            self.assertNotEqual(self.names(), [p.name for p in self.paths])
            self.view.reorder.finish()
            changed.assert_not_called()
        self.assertEqual(self.names(), [p.name for p in self.paths])
        self.assertEqual(self.view.verticalScrollBar().value(), initial)
        self.assertFalse(self.view.reorder.timer.isActive())
        self.assertFalse(self.view.reorder.gap.isVisible())

    def test_stationary_pointer_outside_edges_continues_scrolling_both_directions(self):
        self.select([0])
        outside_bottom = self.view.viewport().mapToGlobal(
            QPoint(200, self.view.viewport().height() + 24)
        )
        with patch("bakuri.ui.file_reorder.QCursor.pos", return_value=outside_bottom):
            for _ in range(25):
                self.view.reorder.tick()
        down = self.view.verticalScrollBar().value()
        self.assertGreater(down, 200)
        outside_top = self.view.viewport().mapToGlobal(QPoint(200, -24))
        with patch("bakuri.ui.file_reorder.QCursor.pos", return_value=outside_top):
            for _ in range(25):
                self.view.reorder.tick()
        self.assertLess(self.view.verticalScrollBar().value(), down)
        self.assertEqual(self.view.count(), 35)

    def test_commit_keeps_moved_row_visible_after_queued_layout(self):
        self.select([0])
        self.view.verticalScrollBar().setValue(1200)
        self.view.reorder.drop(QPoint(200, self.view.viewport().height() - 15))
        self.view.reorder.finish()
        QTest.qWait(50)
        self.assertGreater(self.view.indexOfTopLevelItem(self.original[0]), 15)
        self.assertGreater(self.view.verticalScrollBar().value(), 500)
        self.assertTrue(
            self.view.visualItemRect(self.original[0]).intersects(self.view.viewport().rect())
        )
        self.assertFalse(self.view.reorder.gap.isVisible())
        self.assertTrue(all(p.read_bytes() == b"original" for p in self.paths))

    def test_external_file_drop_still_adds_files_without_duplicates(self):
        source = Path(self.temp.name) / "new.txt"
        source.write_bytes(b"new")
        mime = QMimeData()
        mime.setUrls([QUrl.fromLocalFile(str(source)), QUrl.fromLocalFile(str(source))])
        event = QDropEvent(QPointF(50, 50), Qt.CopyAction, mime, Qt.LeftButton, Qt.NoModifier)
        self.view.dropEvent(event)
        self.assertTrue(event.isAccepted())
        self.assertEqual(self.view.count(), 36)
