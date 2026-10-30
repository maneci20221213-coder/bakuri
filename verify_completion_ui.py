"""CI-only native Windows layout, selected text and non-activating completion check."""

import os

os.environ["QT_QPA_PLATFORM"] = "windows"
os.environ["BAKURI_DISABLE_SHELL_INTEGRATION"] = "1"
from pathlib import Path
import tempfile
import win32gui
from PySide6.QtCore import QSettings, QPoint, Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QFormLayout
from PySide6.QtTest import QTest
from app import Window

app = QApplication([])
output = Path("DevArtifacts")
output.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    window = Window()
    window.settings = QSettings(str(root / "prefs.ini"), QSettings.IniFormat)
    try:
        for name in [f"월별업무실적_{i}.pdf" for i in range(1, 7)]:
            source = root / name
            source.write_bytes(b"UI fixture")
            window.files.add_paths([str(source)])
        window.show()
        window.mode_tabs.setCurrentIndex(1)
        window.files.item(0).setSelected(True)
        QTest.qWait(100)
        assert (
            window.files.visualItemRect(window.files.item(5)).bottom()
            <= window.files.viewport().height()
        ), "Six rows should fit"
        assert window.rename_panel.run.size() == window.rename_panel.restore.size()
        assert window.rename_panel.restore.x() > window.rename_panel.run.geometry().right()
        form = window.rename_panel.layout().itemAt(0).layout()
        labels = [form.itemAt(i, QFormLayout.LabelRole).widget() for i in range(3)]
        centers = [label.geometry().center().y() for label in labels]
        assert abs((centers[1] - centers[0]) - (centers[2] - centers[1])) <= 2, centers
        # Render selected text even with a white system HighlightedText palette.
        palette = window.files.palette()
        palette.setColor(QPalette.HighlightedText, QColor("white"))
        window.files.setPalette(palette)
        panel = window.rename_panel
        assert panel.start.alignment() == Qt.AlignCenter
        assert panel.digits.alignment() == Qt.AlignCenter
        for control in [panel.start, panel.digits, panel.separator]:
            caption = control.parentWidget().layout().itemAt(0).widget()
            assert 0 < control.geometry().left() - caption.geometry().right() <= 8
        assert panel.message.palette().color(QPalette.WindowText).name() == "#718096"
        assert abs(panel.message.geometry().center().y() - panel.run.geometry().center().y()) <= 1
        assert panel.grab().toImage().pixelColor(QPoint(5, 5)).name() == "#ffffff"
        window.grab().save(str(output / "native-rename-preview.png"))
        before = win32gui.GetForegroundWindow()
        window.show_completion(
            "2개 저장 완료\n12.00 MB → 4.00 MB · 8.00 MB 절감(66.7%)", [directory]
        )
        QTest.qWait(100)
        toast = window.results.toast
        assert toast.isVisible()
        assert win32gui.IsWindowVisible(int(toast.winId()))
        assert win32gui.GetForegroundWindow() == before, "Completion stole foreground focus"
        assert app.screenAt(toast.pos()).availableGeometry().contains(toast.geometry())
        toast.grab().save(str(output / "native-completion-preview.png"))
        print(
            "Native rename label spacing and completion popup visibility/focus verification passed."
        )
    finally:
        window.results.toast.hide()
        window.tray.hide()
        window.hide()
