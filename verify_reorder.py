"""CI-only Windows mouse capture drag; independent input guarantees mouse release."""

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import win32api, win32con, win32gui

if "--drive" in sys.argv:
    points = json.loads(sys.argv[-1])
    try:
        time.sleep(0.15)
        win32api.SetCursorPos(points[0])
        time.sleep(0.15)
        win32api.SetCursorPos(points[1])
        time.sleep(1.1)
        win32api.SetCursorPos(points[2])
        time.sleep(0.25)
    finally:
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)
    sys.exit(0)

os.environ["QT_QPA_PLATFORM"] = "windows"
from PySide6.QtCore import QPoint
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

    def native(point):
        ratio = view.viewport().devicePixelRatioF()
        return win32gui.ClientToScreen(
            int(view.viewport().winId()), (round(point.x() * ratio), round(point.y() * ratio))
        )

    def move_native(source, outside, destination):
        win32api.SetCursorPos(native(source))
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, 0, 0)
        direction = 12 if outside.y() > 0 else -12
        points = [native(source + QPoint(20, direction)), native(outside), native(destination)]
        driver = subprocess.Popen([sys.executable, __file__, "--drive", json.dumps(points)])
        try:
            QTest.qWait(2300)
            driver.wait(timeout=5)
        finally:
            if driver.poll() is None:
                driver.kill()
            win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)

    try:
        source = view.visualItemRect(original[0]).center()
        source.setX(250)
        bottom = view.viewport().height()
        print("Starting native downward drag", flush=True)
        move_native(source, QPoint(250, bottom + 22), QPoint(250, bottom - 16))
        print(
            "Downward result",
            view.reorder.active,
            view.indexOfTopLevelItem(original[0]),
            view.verticalScrollBar().value(),
            flush=True,
        )
        assert not view.reorder.active
        assert view.indexOfTopLevelItem(original[0]) > 5
        assert (
            view.verticalScrollBar().value() > 100
        ), "Outside edge did not scroll or returned to source"
        assert view.visualItemRect(original[0]).intersects(view.viewport().rect())
        assert view.count() == len(paths)
        first_moved = original[0]
        source = view.visualItemRect(first_moved).center()
        source.setX(250)
        print("Starting native upward drag", flush=True)
        move_native(source, QPoint(250, -22), QPoint(250, 8))
        print(
            "Upward result",
            view.reorder.active,
            view.indexOfTopLevelItem(first_moved),
            view.verticalScrollBar().value(),
            flush=True,
        )
        assert not view.reorder.active
        assert view.indexOfTopLevelItem(first_moved) < 5, "Upward edge scrolling failed"
        assert view.verticalScrollBar().value() < 200
        assert view.count() == len(paths)
        assert len({view.item(i).data(0, 256) for i in range(view.count())}) == len(paths)
        assert all(path.read_bytes() == b"original" for path in paths)
        # Render the insertion placeholder without holding mouse capture.
        view.reorder.begin()
        view.reorder.timer.stop()
        view.reorder.update_at(view.visualItemRect(view.item(3)).topLeft() + QPoint(250, 1))
        view.viewport().grab().save("DevArtifacts/native-drag-preview.png")
        view.reorder.finish()
        print(
            "Native Windows drag insertion, continuous outside-edge scrolling and destination anchoring passed.",
            flush=True,
        )
    finally:
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, 0, 0)
        view.reorder.finish()
        view.hide()
        win32api.SetCursorPos(previous_cursor)
