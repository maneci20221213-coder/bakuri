"""Quick menu appearance, focus and keyboard navigation."""

import sys
from pathlib import Path
from PySide6.QtCore import Qt, Signal, QTimer, QEvent, QPoint
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import (
    QApplication,
    QGraphicsDropShadowEffect,
    QGridLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)
from bakuri.domain.formats import IMAGES, HANCOM, SPREADSHEETS
from theme import icon


class QuickPopup(QWidget):
    chosen = Signal(str)
    visibility = Signal(bool)

    def __init__(self, animate=None):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setFixedSize(350, 264)
        self.setFocusPolicy(Qt.StrongFocus)
        self.preparing = False
        self.setStyleSheet(
            'QuickPopup {background:transparent;} QPushButton {background:rgba(255,255,255,225);color:#26354A;border:1px solid rgba(218,228,242,230);border-radius:12px;padding:0;} QPushButton:hover {background:rgba(239,246,255,245);border-color:#96C1F8;} QPushButton[selected="true"] {background:rgba(244,249,255,245);border:2px solid #2E83F2;} QLabel {background:transparent;border:0;color:#26354A;font-family:"Malgun Gothic","Noto Sans CJK KR",sans-serif;}'
        )

        self.actions = {}
        self.origin = 0
        self.origin_tab = 0
        self.monitor = QTimer(self)
        self.monitor.setInterval(25)
        self.monitor.timeout.connect(self.check_source)

        grid = QGridLayout(self)
        grid.setContentsMargins(12, 12, 12, 12)
        grid.setSpacing(8)
        self.buttons = {}
        for key, label, arrow, pos in [
            ("pdf", "PDF", "↑", (0, 1)),
            ("png", "PNG", "←", (1, 0)),
            ("jpeg", "JPEG", "→", (1, 2)),
            ("more", "확장 기능", "↓", (2, 1)),
            ("hwpx", "HWPX", "", (1, 1)),
            ("xlsx", "XLSX", "", (1, 1)),
            ("compress", "용량 축소", "", (1, 1)),
        ]:
            button = QPushButton()
            button.setFocusPolicy(Qt.NoFocus)
            button.setAutoDefault(False)
            button.setDefault(False)
            button.setAccessibleName(label)
            button.setCursor(Qt.PointingHandCursor)
            button.setFixedSize(
                88 if key in {"hwpx", "xlsx", "compress"} else 100,
                68 if key in {"hwpx", "xlsx", "compress"} else 74,
            )
            content = QVBoxLayout(button)
            content.setContentsMargins(6, 5, 6, 6)
            content.setSpacing(1)
            image = QLabel()
            image.setAttribute(Qt.WA_TransparentForMouseEvents)
            image.setAlignment(Qt.AlignCenter)
            image.setPixmap(icon("plus" if key == "more" else key).pixmap(30, 32))
            content.addWidget(image)
            text = QLabel(label)
            text.setAttribute(Qt.WA_TransparentForMouseEvents)
            text.setAlignment(Qt.AlignCenter)
            text.setStyleSheet("font-size:12px;font-weight:600;")
            content.addWidget(text)
            if arrow:
                indicator = QLabel(arrow, button)
                indicator.setAttribute(Qt.WA_TransparentForMouseEvents)
                indicator.setGeometry(button.width() - 25, 8, 15, 18)
                indicator.setStyleSheet("color:#60718A;font-size:14px;")
            shadow = QGraphicsDropShadowEffect(button)
            shadow.setBlurRadius(12)
            shadow.setOffset(0, 3)
            shadow.setColor(__import__("PySide6.QtGui", fromlist=["QColor"]).QColor(20, 43, 76, 28))
            button.setGraphicsEffect(shadow)
            button.setProperty("selected", False)
            button.installEventFilter(self)
            button.clicked.connect(lambda checked=False, k=key: self.pick(k))
            grid.addWidget(button, *pos, Qt.AlignCenter)
            self.buttons[key] = button
        self.note = QLabel("방향키 → Enter · Esc 닫기")
        self.note.setAlignment(Qt.AlignCenter)
        self.note.hide()
        from popup_motion import PopupMotion

        self.motion = PopupMotion(self, animate)
        self.current = "pdf"
        QApplication.instance().installEventFilter(self)

    def clicked_at(self, point):
        if not self.isVisible():
            return
        if sys.platform == "win32":
            import win32gui

            x, y = win32gui.ScreenToClient(int(self.winId()), tuple(point))
            rect = win32gui.GetClientRect(int(self.winId()))
            w = max(1, rect[2])
            h = max(1, rect[3])
            position = QPoint(round(x * self.width() / w), round(y * self.height() / h))
        else:
            position = self.mapFromGlobal(QPoint(*point))
        if not any(
            b.isVisible() and b.geometry().contains(position) for b in self.buttons.values()
        ):
            self.hide()

    def check_source(self):
        if sys.platform == "win32" and self.origin:
            from windows import source_active, escape_pressed

            if escape_pressed():
                self.hide()
                return
            if not source_active(self.origin, self.origin_tab, int(self.winId())):
                self.hide()

    def showEvent(self, event):
        super().showEvent(event)
        self.visibility.emit(True)

    def hideEvent(self, event):
        self.monitor.stop()
        self.visibility.emit(False)
        super().hideEvent(event)

    def event(self, event):
        if event.type() == QEvent.WindowDeactivate and self.isVisible():
            if self.origin:
                self.check_source()
            else:
                self.hide()
        return super().event(event)

    def hide(self):
        self.motion.close()

    def present(self, paths, origin=0, tab=0):
        self.preparing = True
        self.motion.reset()
        self.current = "pdf"
        for button in self.buttons.values():
            button.setProperty("selected", False)
            button.clearFocus()
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()
        self.origin = origin
        self.origin_tab = tab
        extensions = {Path(p).suffix.lower() for p in paths}
        images = bool(paths) and extensions <= IMAGES
        pdfs = extensions == {".pdf"}
        self.actions = {}
        labels = {"pdf": ("PDF", "pdf"), "png": ("PNG", "png"), "jpeg": ("JPEG", "jpeg")}
        if images:
            target = "jpeg" if extensions == {".png"} else "png"
            self.actions = {"png": target, "jpeg": "hwpx"}
            labels["png"] = (target.upper(), target)
            labels["jpeg"] = ("한글", "hwpx")
        elif pdfs:
            self.actions = {"pdf": "pdf_merge", "jpeg": "hwpx"}
            labels["pdf"] = ("PDF 합치기", "pdf")
            labels["jpeg"] = ("한글", "hwpx")
        elif extensions and extensions <= HANCOM and len(paths) > 1:
            self.actions = {"pdf": "hwp_merge"}
            labels["pdf"] = ("한글 합치기", "hwpx")
        for key, (label, asset) in labels.items():
            button = self.buttons[key]
            button.setAccessibleName(label)
            button.layout().itemAt(0).widget().setPixmap(icon(asset).pixmap(30, 32))
            button.layout().itemAt(1).widget().setText(label)
        self.buttons["pdf"].setEnabled(True)
        self.buttons["pdf"].setToolTip(
            "PDF 파일을 두 개 이상 선택해 주세요." if pdfs and len(paths) < 2 else ""
        )
        self.buttons["hwpx"].setVisible(
            bool(paths) and all(Path(p).suffix.lower() == ".hwp" for p in paths)
        )
        self.buttons["xlsx"].setVisible(
            bool(paths) and all(Path(p).suffix.lower() in SPREADSHEETS - {".xlsx"} for p in paths)
        )
        self.buttons["compress"].setVisible(
            bool(paths) and all(Path(p).suffix.lower() in IMAGES | {".pdf"} for p in paths)
        )
        self.note.setText(f"{len(paths)}개 파일 · 방향키 → Enter · Esc 닫기")
        self.current = "pdf"
        point = QCursor.pos()
        screen = QApplication.screenAt(point) or QApplication.primaryScreen()
        rect = screen.availableGeometry()
        self.move(
            max(rect.left(), min(point.x() - self.width() // 2, rect.right() - self.width() + 1)),
            max(rect.top(), min(point.y() - self.height() // 2, rect.bottom() - self.height() + 1)),
        )
        if self.motion.enabled:
            self.setWindowOpacity(0.0)
        self.show()
        self.activateWindow()
        self.setFocus(Qt.PopupFocusReason)
        self.monitor.start()
        self.visibility.emit(True)
        self.motion.open()
        self.preparing = False

    def select(self, key):
        if (
            key not in self.buttons
            or not self.buttons[key].isVisible()
            or not self.buttons[key].isEnabled()
        ):
            return
        self.current = key
        for name, button in self.buttons.items():
            button.setProperty("selected", name == key)
            button.style().unpolish(button)
            button.style().polish(button)
            button.update()
        self.setFocus(Qt.OtherFocusReason)

    def native_key(self, vk):
        if not self.isVisible() or self.motion.closing:
            return
        mapping = {
            0x26: Qt.Key_Up,
            0x28: Qt.Key_Down,
            0x25: Qt.Key_Left,
            0x27: Qt.Key_Right,
            0x0D: Qt.Key_Return,
            0x1B: Qt.Key_Escape,
            0x09: Qt.Key_Tab,
            0x20: Qt.Key_Space,
        }
        key = mapping.get(vk)
        if key is not None:
            self.handle_key(key)

    def pick(self, key):
        if not self.isVisible() or self.motion.closing:
            return
        action = self.actions.get(key, key)
        self.motion.close(lambda: self.chosen.emit(action))

    def eventFilter(self, obj, event):
        if self.preparing or (hasattr(self, "motion") and self.motion.closing):
            return super().eventFilter(obj, event)
        if self.isVisible() and event.type() == QEvent.Enter:
            key = next((k for k, b in self.buttons.items() if b is obj), None)
            if key:
                self.select(key)
        if self.isVisible() and event.type() == QEvent.MouseButtonPress:
            point = self.mapFromGlobal(event.globalPosition().toPoint())
            if not any(
                b.isVisible() and b.geometry().contains(point) for b in self.buttons.values()
            ):
                self.hide()
        if (
            self.isVisible()
            and event.type() == QEvent.KeyPress
            and event.key()
            in (
                Qt.Key_Up,
                Qt.Key_Down,
                Qt.Key_Left,
                Qt.Key_Right,
                Qt.Key_Return,
                Qt.Key_Enter,
                Qt.Key_Escape,
                Qt.Key_Tab,
                Qt.Key_Space,
            )
        ):
            self.keyPressEvent(event)
            return True
        return super().eventFilter(obj, event)

    def move_selection(self, key):
        center = next(
            (name for name in ("hwpx", "xlsx", "compress") if self.buttons[name].isVisible()), None
        )
        middle = center or "pdf"
        neighbors = {
            "pdf": {Qt.Key_Left: "png", Qt.Key_Right: "jpeg", Qt.Key_Down: center or "more"},
            "png": {Qt.Key_Up: "pdf", Qt.Key_Down: "more", Qt.Key_Right: center or "jpeg"},
            "jpeg": {Qt.Key_Up: "pdf", Qt.Key_Down: "more", Qt.Key_Left: center or "png"},
            "more": {Qt.Key_Up: middle, Qt.Key_Left: "png", Qt.Key_Right: "jpeg"},
        }
        if center:
            neighbors[center] = {
                Qt.Key_Up: "pdf",
                Qt.Key_Down: "more",
                Qt.Key_Left: "png",
                Qt.Key_Right: "jpeg",
            }
        target = neighbors.get(self.current, {}).get(key)
        if target:
            self.select(target)

    def handle_key(self, key):
        if self.motion.closing:
            return
        if key in (Qt.Key_Up, Qt.Key_Down, Qt.Key_Left, Qt.Key_Right):
            self.move_selection(key)
        elif key == Qt.Key_Tab:
            visible = [
                k
                for k in ("pdf", "png", "hwpx", "xlsx", "compress", "jpeg", "more")
                if self.buttons[k].isVisible() and self.buttons[k].isEnabled()
            ]
            self.select(visible[(visible.index(self.current) + 1) % len(visible)])
        elif key in (Qt.Key_Return, Qt.Key_Enter, Qt.Key_Space):
            self.pick(self.current)
        elif key == Qt.Key_Escape:
            self.hide()

    def keyPressEvent(self, event):
        self.handle_key(event.key())
        event.accept()
