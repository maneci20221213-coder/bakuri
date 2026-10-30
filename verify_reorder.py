"""CI-only Windows OLE drag: native mouse input, outside-edge scroll and destination anchor."""

import os

os.environ["QT_QPA_PLATFORM"] = "windows"
from pathlib import Path
import tempfile
import win32api, win32con, win32gui
from PySide6.QtCore import QPoint, QTimer
from PySide6.QtWidgets import QApplication
from PySide6.QtTest import QTest
from file_list import Files

app = QApplication([])
Path("DevArtifacts").mkdir(exist_ok=True)
previous_cursor = win32api.GetCursorPos()
with tempfile.TemporaryDirectory() as folder:
    view = Files(allow_all=True)
    paths = [Path(folder) / f"{i:02}_자료.pdf" for i in range(40)]
    for path in paths:
        path.write_bytes(b"original")
    view.add_paths(list(map(str, paths)))
    view.resize(900, 420)
    view.move(30, 30)
    view.show()
    view.activateWindow()
    QTest.qWait(150)
    original = [view.item(i) for i in range(view.count())]
    observations = []

    def cursor(point):
        # Native child HWND coordinates handle Windows DPI conversion explicitly.
        ratio = view.viewport().devicePixelRatioF()
        native = win32gui.ClientToScreen(
            int(view.viewport().winId()), (round(point.x() * ratio), round(point.y() * ratio))
        )
        win32api.SetCursorPos(native)

    def release():
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)

    try:
        source = view.visualItemRect(original[0]).center()
        source.setX(250)
        cursor(source)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
        QTimer.singleShot(80, lambda: cursor(source + QPoint(20, 12)))
        bottom = view.viewport().height()
        QTimer.singleShot(180, lambda: cursor(QPoint(250, bottom + 22)))
        QTimer.singleShot(
            750,
            lambda: observations.append((view.reorder.active, view.verticalScrollBar().value())),
        )
        QTimer.singleShot(
            1100, lambda: view.viewport().grab().save("DevArtifacts/native-drag-preview.png")
        )
        QTimer.singleShot(1250, lambda: cursor(QPoint(250, bottom - 16)))
        QTimer.singleShot(1450, release)
        QTest.qWait(1900)
        assert observations and observations[0][0], ("Native drag did not start", observations)
        assert observations[0][1] > 100, ("Outside pointer did not scroll", observations)
        assert not view.reorder.active
        assert view.indexOfTopLevelItem(original[0]) > 5
        assert view.verticalScrollBar().value() > 100, "Returned to the source scroll position"
        assert view.visualItemRect(original[0]).intersects(view.viewport().rect())
        assert view.count() == len(paths)
        assert len({view.item(i).data(0, 256) for i in range(view.count())}) == len(paths)
        # Second real drag, upward beyond the viewport, then return inside and drop.
        first_moved = original[0]
        source = view.visualItemRect(first_moved).center()
        source.setX(250)
        cursor(source)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
        QTimer.singleShot(80, lambda: cursor(source + QPoint(20, -12)))
        QTimer.singleShot(180, lambda: cursor(QPoint(250, -22)))
        QTimer.singleShot(1250, lambda: cursor(QPoint(250, 8)))
        QTimer.singleShot(1450, release)
        QTest.qWait(1900)
        assert not view.reorder.active
        assert view.indexOfTopLevelItem(first_moved) < 5, "Upward edge scrolling failed"
        assert view.verticalScrollBar().value() < 200
        assert view.count() == len(paths)
        assert all(path.read_bytes() == b"original" for path in paths)
        print(
            "Native Windows drag insertion, continuous outside-edge scrolling and destination anchoring passed."
        )
    finally:
        release()
        view.reorder.finish()
        view.hide()
        win32api.SetCursorPos(previous_cursor)
