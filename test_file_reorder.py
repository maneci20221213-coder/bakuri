"""Reorder is a view-only transaction: preserve rows, cancel safely, anchor the destination."""

import os

os.environ["QT_QPA_PLATFORM"] = "offscreen"
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PySide6.QtCore import QPoint, Qt, QMimeData, QUrl, QPointF, QEvent
from PySide6.QtGui import QDropEvent, QMouseEvent
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

    def test_mouse_capture_commits_on_release_and_escape_restores_order(self):
        source = self.view.visualItemRect(self.original[0]).center()
        source.setX(250)
        destination = self.view.visualItemRect(self.original[3]).center()
        destination.setX(250)
        QTest.mousePress(self.view.viewport(), Qt.LeftButton, Qt.NoModifier, source)
        move = QMouseEvent(
            QEvent.MouseMove,
            QPointF(destination),
            QPointF(self.view.viewport().mapToGlobal(destination)),
            Qt.NoButton,
            Qt.LeftButton,
            Qt.NoModifier,
        )
        APP.sendEvent(self.view.viewport(), move)
        self.assertTrue(self.view.reorder.active)
        QTest.mouseRelease(self.view.viewport(), Qt.LeftButton, Qt.NoModifier, destination)
        QTest.qWait(20)
        self.assertFalse(self.view.reorder.active)
        self.assertEqual(self.view.indexOfTopLevelItem(self.original[0]), 2)
        order = self.names()
        source = self.view.visualItemRect(self.original[0]).center()
        source.setX(250)
        destination = QPoint(250, 5)
        QTest.mousePress(self.view.viewport(), Qt.LeftButton, Qt.NoModifier, source)
        move = QMouseEvent(
            QEvent.MouseMove,
            QPointF(destination),
            QPointF(self.view.viewport().mapToGlobal(destination)),
            Qt.NoButton,
            Qt.LeftButton,
            Qt.NoModifier,
        )
        APP.sendEvent(self.view.viewport(), move)
        self.assertTrue(self.view.reorder.active)
        QTest.keyClick(self.view, Qt.Key_Escape)
        QTest.mouseRelease(self.view.viewport(), Qt.LeftButton, Qt.NoModifier, destination)
        self.assertFalse(self.view.reorder.active)
        self.assertEqual(self.names(), order)

    def test_clearing_list_during_drag_cancels_before_items_are_deleted(self):
        self.select([0])
        self.view.reorder.update_at(QPoint(250, self.view.viewport().height() - 15))
        self.view.clear()
        self.assertFalse(self.view.reorder.active)
        self.assertEqual(self.view.count(), 0)
        self.assertTrue(all(p.read_bytes() == b"original" for p in self.paths))

    def test_ctrl_and_shift_selected_groups_survive_press_and_drag(self):
        for modifier, indexes in [(Qt.ControlModifier, [1, 3]), (Qt.ShiftModifier, [1, 2, 3])]:
            with self.subTest(modifier=modifier):
                self.view.clearSelection()
                for i, item in enumerate(self.original):
                    if self.view.indexOfTopLevelItem(item) != i:
                        self.view.takeTopLevelItem(self.view.indexOfTopLevelItem(item))
                        self.view.insertTopLevelItem(i, item)
                self.view.doItemsLayout()

                def point(item):
                    value = self.view.visualItemRect(item).center()
                    value.setX(250)
                    return value

                QTest.mouseClick(
                    self.view.viewport(), Qt.LeftButton, Qt.NoModifier, point(self.original[1])
                )
                QTest.mouseClick(
                    self.view.viewport(), Qt.LeftButton, modifier, point(self.original[3])
                )
                self.assertEqual(
                    {id(x) for x in self.view.selectedItems()},
                    {id(self.original[i]) for i in indexes},
                )
                source = point(self.original[1])
                destination = self.view.visualItemRect(self.original[5]).topLeft() + QPoint(250, 1)
                QTest.mousePress(self.view.viewport(), Qt.LeftButton, Qt.NoModifier, source)
                self.assertEqual(len(self.view.selectedItems()), len(indexes))
                move = QMouseEvent(
                    QEvent.MouseMove,
                    QPointF(destination),
                    QPointF(self.view.viewport().mapToGlobal(destination)),
                    Qt.NoButton,
                    Qt.LeftButton,
                    Qt.NoModifier,
                )
                APP.sendEvent(self.view.viewport(), move)
                self.assertEqual(
                    [id(x) for x in self.view.reorder.moving],
                    [id(self.original[i]) for i in indexes],
                )
                QTest.mouseRelease(self.view.viewport(), Qt.LeftButton, Qt.NoModifier, destination)
                QTest.qWait(20)
                rows = [self.view.indexOfTopLevelItem(self.original[i]) for i in indexes]
                self.assertEqual(rows, list(range(rows[0], rows[0] + len(rows))))
                self.assertGreater(rows[0], 1)

    def test_click_without_drag_collapses_existing_multiselection(self):
        for item in self.original[:3]:
            item.setSelected(True)
        point = self.view.visualItemRect(self.original[1]).center()
        point.setX(250)
        QTest.mouseClick(self.view.viewport(), Qt.LeftButton, Qt.NoModifier, point)
        self.assertEqual(self.view.selectedItems(), [self.original[1]])
        self.assertFalse(self.view.reorder.active)

    def test_four_file_drag_snapshot_survives_jitter_modifiers_and_each_start_row(self):
        for start in range(4):
            for modifier in (Qt.NoModifier, Qt.ControlModifier, Qt.ShiftModifier):
                with self.subTest(start=start, modifier=modifier):
                    self.view.finish_reorder(False)
                    self.view.clearSelection()
                    while self.view.count():
                        self.view.takeTopLevelItem(0)
                    self.view.addTopLevelItems(self.original)
                    self.view.verticalScrollBar().setValue(0)
                    self.view.setCurrentItem(self.original[0], 2)
                    for item in self.original[:4]:
                        item.setSelected(True)
                    self.view.doItemsLayout()
                    source = self.view.visualItemRect(self.original[start]).center()
                    source.setX(250)
                    QTest.mousePress(self.view.viewport(), Qt.LeftButton, modifier, source)
                    for offset in (QPoint(1, 0), QPoint(3, 1), QPoint(5, 1)):
                        point = source + offset
                        move = QMouseEvent(
                            QEvent.MouseMove,
                            QPointF(point),
                            QPointF(self.view.viewport().mapToGlobal(point)),
                            Qt.NoButton,
                            Qt.LeftButton,
                            modifier,
                        )
                        APP.sendEvent(self.view.viewport(), move)
                    target = self.view.visualItemRect(self.original[5]).topLeft() + QPoint(250, 1)
                    move = QMouseEvent(
                        QEvent.MouseMove,
                        QPointF(target),
                        QPointF(self.view.viewport().mapToGlobal(target)),
                        Qt.NoButton,
                        Qt.LeftButton,
                        modifier,
                    )
                    APP.sendEvent(self.view.viewport(), move)
                    captured = tuple(self.view.reorder.moving)
                    QTest.mouseRelease(self.view.viewport(), Qt.LeftButton, modifier, target)
                    QTest.qWait(10)
                    self.assertEqual(
                        [id(item) for item in captured], [id(item) for item in self.original[:4]]
                    )
                    rows = [self.view.indexOfTopLevelItem(item) for item in self.original[:4]]
                    self.assertEqual(rows, list(range(rows[0], rows[0] + 4)))

    def test_ctrl_and_shift_click_without_drag_keep_normal_selection_rules(self):
        def point(i):
            result = self.view.visualItemRect(self.original[i]).center()
            result.setX(250)
            return result

        QTest.mouseClick(self.view.viewport(), Qt.LeftButton, Qt.NoModifier, point(0))
        QTest.mouseClick(self.view.viewport(), Qt.LeftButton, Qt.ShiftModifier, point(3))
        self.assertEqual(len(self.view.selectedItems()), 4)
        QTest.mouseClick(self.view.viewport(), Qt.LeftButton, Qt.ControlModifier, point(2))
        self.assertEqual(
            {id(x) for x in self.view.selectedItems()}, {id(self.original[i]) for i in (0, 1, 3)}
        )
        QTest.mouseClick(self.view.viewport(), Qt.LeftButton, Qt.NoModifier, point(0))
        QTest.mouseClick(self.view.viewport(), Qt.LeftButton, Qt.ShiftModifier, point(3))
        QTest.mouseClick(self.view.viewport(), Qt.LeftButton, Qt.ShiftModifier, point(1))
        self.assertEqual(
            {id(x) for x in self.view.selectedItems()}, {id(self.original[i]) for i in (0, 1)}
        )

    def test_double_click_drag_on_selected_block_keeps_all_four_files(self):
        for item in self.original[:4]:
            item.setSelected(True)
        source = self.view.visualItemRect(self.original[2]).center()
        source.setX(250)
        press = QMouseEvent(
            QEvent.MouseButtonDblClick,
            QPointF(source),
            QPointF(self.view.viewport().mapToGlobal(source)),
            Qt.LeftButton,
            Qt.LeftButton,
            Qt.NoModifier,
        )
        APP.sendEvent(self.view.viewport(), press)
        target = self.view.visualItemRect(self.original[5]).topLeft() + QPoint(250, 1)
        move = QMouseEvent(
            QEvent.MouseMove,
            QPointF(target),
            QPointF(self.view.viewport().mapToGlobal(target)),
            Qt.NoButton,
            Qt.LeftButton,
            Qt.NoModifier,
        )
        APP.sendEvent(self.view.viewport(), move)
        self.assertEqual(len(self.view.reorder.moving), 4)
        QTest.mouseRelease(self.view.viewport(), Qt.LeftButton, Qt.NoModifier, target)
        rows = [self.view.indexOfTopLevelItem(item) for item in self.original[:4]]
        self.assertEqual(rows, list(range(rows[0], rows[0] + 4)))

    def test_multiple_file_destination_box_has_one_row_height(self):
        for indexes in ([1], [1, 2], [1, 2, 3, 4]):
            self.select(indexes)
            self.view.reorder.show_gap()
            gap = self.view.reorder.gap
            self.assertTrue(gap.isVisible())
            self.assertEqual(gap.height(), self.view.visualItemRect(self.original[1]).height())
            self.assertEqual(gap.text(), f"{len(indexes)}개 파일을 이 위치로 이동")
            self.view.reorder.finish()
