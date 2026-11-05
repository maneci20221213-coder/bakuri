"""Application preferences and their Windows integration."""

import sys

from PySide6.QtCore import QEvent, QKeyCombination, Qt
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
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

from bakuri.domain.quick_actions import ACTIONS, DIRECTIONS, PROFILE_CHOICES
from build_channel import DEFAULT_HOTKEY, DEVELOPMENT
from user_messages import friendly_error
from work_ui import add_profiles, read_options


class ShortcutEdit(QLineEdit):
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
        self.setAccessibleName("빠른 실행 단축키")

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
        categories.setFixedWidth(110)
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
        self.auto.setChecked(settings.value("startup_enabled", True, type=bool))
        self.auto.setEnabled(sys.platform == "win32" and not DEVELOPMENT)
        if self.auto.isEnabled():
            from windows import startup_enabled

            self.auto.setChecked(startup_enabled())
        elif DEVELOPMENT:
            self.auto.setChecked(False)
        form.addRow(self.auto)
        self.explorer = QCheckBox("탐색기 우클릭 메뉴 추가")
        self.explorer.setChecked(not DEVELOPMENT and settings.value("explorer", True, type=bool))
        self.explorer.setEnabled(not DEVELOPMENT)
        form.addRow(self.explorer)
        self.notify = QCheckBox("작업 진행률 및 완료 알림")
        self.notify.setChecked(settings.value("notify", True, type=bool))
        form.addRow(self.notify)

        form = page("빠른 실행")
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
        hint = QLabel(
            "입력칸을 클릭한 뒤 키 또는 조합을 누르세요. Windows 예약 단축키는 사용이 제한될 수 있습니다."
        )
        hint.setWordWrap(True)
        form.addRow(hint)

        self.profile = QComboBox()
        for profile, label in PROFILE_CHOICES.items():
            self.profile.addItem(label, profile)
        form.addRow("선택한 파일 유형", self.profile)
        self.quick_menu = {
            (profile, key): settings.value(f"quick_menu/{profile}/{key}", "")
            for profile in PROFILE_CHOICES
            for key in DIRECTIONS
        }
        self.direction_boxes = {}
        for key, label in DIRECTIONS.items():
            combo = QComboBox()
            combo.addItem("기본 동작", "")
            for action, (name, _) in ACTIONS.items():
                combo.addItem(name, action)
            combo.activated.connect(
                lambda index, key=key, combo=combo: self.change_direction(
                    key, combo.itemData(index)
                )
            )
            self.direction_boxes[key] = combo
            form.addRow(label, combo)
        note = QLabel("선택한 파일에서 실행할 수 없는 기능은 팝업에서 비활성화됩니다.")
        note.setWordWrap(True)
        form.addRow(note)
        self.profile.currentIndexChanged.connect(self.load_directions)
        self.load_directions()

        form = page("변환")
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

    def reset_shortcut(self):
        self.key.binding = ""
        self.key.setText(DEFAULT_HOTKEY)

    def change_direction(self, key, action):
        self.quick_menu[self.profile.currentData(), key] = action

    def load_directions(self):
        for key, combo in self.direction_boxes.items():
            action = self.quick_menu[self.profile.currentData(), key]
            combo.setCurrentIndex(max(0, combo.findData(action)))

    def save(self):
        try:
            if sys.platform == "win32" and not DEVELOPMENT:
                from windows import register_menu, set_startup

                set_startup(self.auto.isChecked())
                register_menu(self.explorer.isChecked())
            s = self.window.settings
            values = {
                "startup_enabled": self.auto.isChecked(),
                "hotkey_enabled": self.enabled.isChecked(),
                "hotkey": self.key.text(),
                "hotkey_binding": self.key.binding,
                "notify": self.notify.isChecked(),
                "explorer": self.explorer.isChecked(),
                "dpi": int(self.dpi.currentText()),
                "image_mode": self.image_mode.currentData(),
                "compress_profile": self.compress_profile.currentData(),
                "compress_protect": self.compress_protect.isChecked(),
                "compress_strip": self.compress_strip.isChecked(),
            }
            for key, value in values.items():
                s.setValue(key, value)
            for (profile, key), action in self.quick_menu.items():
                setting = f"quick_menu/{profile}/{key}"
                if action:
                    s.setValue(setting, action)
                else:
                    s.remove(setting)
            s.sync()
            if hasattr(self.window, "watcher"):
                self.window.watcher.update_settings(s)
            self.accept()
        except Exception as error:
            QMessageBox.warning(self, "설정을 저장하지 못했어요", friendly_error(error, "settings"))
