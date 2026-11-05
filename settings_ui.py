"""Application preferences and their Windows integration."""

import os
import sys
from pathlib import Path

from PySide6.QtCore import QEvent, QKeyCombination, Qt, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from bakuri.domain.quick_actions import ACTIONS, DIRECTIONS, PROFILES
from build_channel import DEFAULT_HOTKEY, DEVELOPMENT
from user_messages import friendly_error
from work_ui import add_profiles, read_options


class ShortcutEdit(QLineEdit):
    capture_changed = Signal(bool)

    modifiers = {
        Qt.ShiftModifier: 0x10,
        Qt.ControlModifier: 0x11,
        Qt.AltModifier: 0x12,
        Qt.MetaModifier: 0x5B,
    }

    def __init__(self, text, binding):
        super().__init__(text)
        self.binding = binding
        self.setReadOnly(True)
        self.setAccessibleName("빠른 변환 단축키")
        self.setToolTip("Windows 예약 단축키는 사용이 제한될 수 있습니다.")
        self.setStyleSheet(
            "QLineEdit { border: 1px solid #c3cddb; border-radius: 5px; padding: 5px; }"
            "QLineEdit:focus { border: 2px solid #2e83f2; padding: 4px; background: #edf5ff; }"
        )

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.capture_changed.emit(True)

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.capture_changed.emit(False)

    def event(self, event):
        if event.type() == QEvent.ShortcutOverride:
            event.accept()
            return True
        if event.type() == QEvent.KeyPress:
            self.keyPressEvent(event)
            return True
        return super().event(event)

    def keyPressEvent(self, event):
        key = event.key()
        if event.isAutoRepeat() or key in (
            Qt.Key_Shift,
            Qt.Key_Control,
            Qt.Key_Alt,
            Qt.Key_Meta,
            Qt.Key_AltGr,
            Qt.Key_unknown,
        ):
            return
        vk = event.nativeVirtualKey()
        if sys.platform != "win32":
            vk = key if 0x30 <= key <= 0x5A else 0
            if Qt.Key_F1 <= key <= Qt.Key_F24:
                vk = 0x70 + key - Qt.Key_F1
        if not 0 < vk <= 0xFE:
            return
        mods = [value for flag, value in self.modifiers.items() if event.modifiers() & flag]
        self.binding = ",".join(str(value) for value in (vk, *mods))
        self.setText(QKeySequence(QKeyCombination(event.modifiers(), Qt.Key(key))).toString())


class SettingsDialog(QDialog):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.setWindowTitle("바꾸리 설정")
        self.setMinimumWidth(520)
        layout = QVBoxLayout(self)
        categories = QListWidget()
        categories.setAccessibleName("설정 분류")
        categories.setFixedWidth(124)
        categories.setSpacing(5)
        categories.setStyleSheet("QListWidget::item { padding: 7px 9px; }")
        pages = QStackedWidget()
        content = QHBoxLayout()
        content.addWidget(categories)
        content.addWidget(pages, 1)
        layout.addLayout(content)
        categories.currentRowChanged.connect(pages.setCurrentIndex)

        def page(title):
            widget = QWidget()
            pages.addWidget(widget)
            categories.addItem(title)
            return QFormLayout(widget)

        settings = window.settings
        form = page("일반")
        self.auto = QCheckBox("윈도우 로그인 시 백그라운드 실행")
        windows_available = sys.platform == "win32"
        self.shell_integration = (
            windows_available and os.environ.get("BAKURI_DISABLE_SHELL_INTEGRATION") != "1"
        )
        startup = settings.value("startup_enabled", not DEVELOPMENT, type=bool)
        if self.shell_integration:
            from windows import startup_enabled

            startup = startup_enabled(development=DEVELOPMENT)
        self.auto.setChecked(startup)
        self.auto.setEnabled(windows_available)
        form.addRow(self.auto)
        self.explorer = QCheckBox("탐색기 우클릭 메뉴 추가")
        self.explorer.setChecked(settings.value("explorer", not DEVELOPMENT, type=bool))
        self.explorer.setEnabled(windows_available)
        form.addRow(self.explorer)
        self.notify = QCheckBox("작업 진행률 및 완료 알림")
        self.notify.setChecked(settings.value("notify", True, type=bool))
        form.addRow(self.notify)

        form = page("빠른 변환")
        self.enabled = QCheckBox("단축키 사용")
        self.enabled.setChecked(settings.value("hotkey_enabled", True, type=bool))
        form.addRow(self.enabled)
        self.key = ShortcutEdit(
            settings.value("hotkey", DEFAULT_HOTKEY), settings.value("hotkey_binding", "")
        )
        keys = QHBoxLayout()
        keys.addWidget(self.key)
        reset = QPushButton("기본값")
        reset.clicked.connect(self.reset_shortcut)
        keys.addWidget(reset)
        form.addRow("단축키", keys)
        idle_hint = "입력칸을 클릭한 뒤 키 또는 조합을 누르세요."
        hint = QLabel(idle_hint)
        hint.setWordWrap(True)
        self.key.capture_changed.connect(
            lambda active: hint.setText(
                "입력 준비됨 · 원하는 키를 누르세요." if active else idle_hint
            )
        )
        form.addRow(hint)
        divider = QFrame()
        divider.setFrameShape(QFrame.HLine)
        form.addRow(divider)
        title = QLabel("빠른 변환 팝업 설정")
        title.setStyleSheet("font-weight: bold; padding-top: 5px;")
        form.addRow(title)

        self.profile = QComboBox()
        for profile, label in PROFILES.items():
            self.profile.addItem(label, profile)
        form.addRow("선택한 파일 유형", self.profile)
        self.quick_menu = {
            (profile, key): settings.value(f"quick_menu/{profile}/{key}", "")
            for profile in PROFILES
            for key in DIRECTIONS
        }
        self.direction_boxes = {}
        for key, label in DIRECTIONS.items():
            combo = QComboBox()
            combo.addItem("기본 동작", "")
            for action, (name, _) in ACTIONS.items():
                combo.addItem(name, action)
            combo.currentIndexChanged.connect(
                lambda index, key=key, combo=combo: self.change_direction(
                    key, combo.itemData(index)
                )
            )
            self.direction_boxes[key] = combo
            form.addRow(label, combo)
        note = QLabel("선택한 파일에서 실행할 수 없는 기능은 팝업에서 비활성화됩니다.")
        note.setWordWrap(True)
        form.addRow(note)
        reset_menu = QPushButton("모든 유형 기본값으로")
        reset_menu.clicked.connect(self.reset_quick_menu)
        form.addRow(reset_menu)
        self.profile.currentIndexChanged.connect(self.load_directions)
        self.load_directions()

        form = page("변환")
        self.output_mode = QComboBox()
        for label, value in (
            ("같은 위치", "source"),
            ("새 폴더", "subfolder"),
            ("폴더 지정", "custom"),
        ):
            self.output_mode.addItem(label, value)
        self.output_mode.setCurrentIndex(
            max(0, self.output_mode.findData(settings.value("output_mode", "source")))
        )
        form.addRow("변환 파일 생성 위치", self.output_mode)
        self.output_folder = QLineEdit(settings.value("output_folder", ""))
        self.output_folder.setReadOnly(True)
        self.output_browse = QPushButton("찾아보기")
        self.output_browse.clicked.connect(self.choose_output_folder)
        location = QHBoxLayout()
        location.addWidget(self.output_folder)
        location.addWidget(self.output_browse)
        form.addRow("지정 폴더", location)
        self.output_mode.currentIndexChanged.connect(self.update_output_folder)
        self.update_output_folder()
        note = QLabel("새 폴더를 선택하면 원본 폴더 안의 ‘바꾸리 변환’에 저장합니다.")
        note.setWordWrap(True)
        form.addRow(note)
        self.dpi = QComboBox()
        self.dpi.addItems(["96", "150", "200", "300"])
        self.dpi.setCurrentText(str(settings.value("dpi", 150, type=int)))
        form.addRow("PDF·CAD 이미지 해상도", self.dpi)
        self.image_mode = QComboBox()
        self.image_mode.addItem("표 배경으로 채우기 (기본)", "background")
        self.image_mode.addItem("표 안에 이미지 넣기", "inline")
        self.image_mode.setCurrentIndex(
            max(0, self.image_mode.findData(settings.value("image_mode", "background")))
        )
        form.addRow("이미지 → 한글 배치", self.image_mode)

        form = page("용량 축소")
        self.compress_profile = QComboBox()
        add_profiles(self.compress_profile)
        self.compress_profile.setCurrentIndex(
            self.compress_profile.findData(read_options(settings)["profile"])
        )
        form.addRow("해상도 축소 기본값", self.compress_profile)
        self.compress_protect = QCheckBox("글자 보호 강화 · 이미지 해상도 유지")
        self.compress_protect.setChecked(settings.value("compress_protect", False, type=bool))
        form.addRow(self.compress_protect)
        self.compress_strip = QCheckBox("용량 축소 시 위치정보 등 메타데이터 삭제")
        self.compress_strip.setChecked(settings.value("compress_strip", False, type=bool))
        form.addRow(self.compress_strip)

        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.save)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        categories.setCurrentRow(0)

    def update_output_folder(self):
        enabled = self.output_mode.currentData() == "custom"
        self.output_folder.setEnabled(enabled)
        self.output_browse.setEnabled(enabled)

    def choose_output_folder(self):
        selected = QFileDialog.getExistingDirectory(
            self, "변환 파일 저장 폴더", self.output_folder.text()
        )
        if selected:
            self.output_folder.setText(selected)

    def reset_shortcut(self):
        self.key.binding = ""
        self.key.setText(DEFAULT_HOTKEY)

    def reset_quick_menu(self):
        self.quick_menu = dict.fromkeys(self.quick_menu, "")
        self.load_directions()

    def change_direction(self, key, action):
        self.quick_menu[self.profile.currentData(), key] = action

    def load_directions(self):
        for key, combo in self.direction_boxes.items():
            action = self.quick_menu[self.profile.currentData(), key]
            blocked = combo.blockSignals(True)
            combo.setCurrentIndex(max(0, combo.findData(action)))
            combo.blockSignals(blocked)

    def save(self):
        if (
            self.output_mode.currentData() == "custom"
            and not Path(self.output_folder.text()).is_absolute()
        ):
            QMessageBox.information(self, "저장 위치", "변환 파일을 저장할 폴더를 지정해 주세요.")
            return
        try:
            if self.shell_integration:
                from windows import register_menu, set_startup

                set_startup(self.auto.isChecked(), development=DEVELOPMENT)
                register_menu(self.explorer.isChecked(), development=DEVELOPMENT)
            s = self.window.settings
            values = {
                "startup_enabled": self.auto.isChecked(),
                "hotkey_enabled": self.enabled.isChecked(),
                "hotkey": self.key.text(),
                "hotkey_binding": self.key.binding,
                "notify": self.notify.isChecked(),
                "explorer": self.explorer.isChecked(),
                "dpi": int(self.dpi.currentText()),
                "output_mode": self.output_mode.currentData(),
                "output_folder": self.output_folder.text(),
                "image_mode": self.image_mode.currentData(),
                "compress_profile": self.compress_profile.currentData(),
                "compress_protect": self.compress_protect.isChecked(),
                "compress_strip": self.compress_strip.isChecked(),
            }
            for key, value in values.items():
                s.setValue(key, value)
            s.remove("quick_menu")
            for (profile, key), action in self.quick_menu.items():
                if action:
                    s.setValue(f"quick_menu/{profile}/{key}", action)
            s.sync()
            if hasattr(self.window, "watcher"):
                self.window.watcher.update_settings(s)
            self.accept()
        except Exception as error:
            QMessageBox.warning(self, "설정을 저장하지 못했어요", friendly_error(error, "settings"))
