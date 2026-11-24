"""Build the main controls. Business rules and workers live outside this view."""

from PySide6.QtCore import QSize
from PySide6.QtGui import QShortcut
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabBar,
    QVBoxLayout,
)
from build_channel import BUILD_LABEL
from file_list import Files
from theme import stylesheet, icon
from work_ui import add_profiles, read_options
from .format_delegate import OutputFormatDelegate


def build_main_view(self):
    self.setWindowTitle(f"바꾸리 파일 변환기 {BUILD_LABEL}")
    self.resize(840, min(740, self.screen().availableGeometry().height() - 60))
    self.setMinimumSize(760, 540)
    self.setObjectName("mainWindow")
    self.setStyleSheet(stylesheet())
    layout = QVBoxLayout(self)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    toolbar = QFrame()
    self.toolbar = toolbar
    toolbar.setObjectName("toolbar")
    row = QHBoxLayout(toolbar)
    row.setContentsMargins(16, 16, 16, 14)
    row.setSpacing(10)
    add = QPushButton("파일 추가")
    add.setObjectName("addFiles")
    add.setIcon(icon("plus"))
    add.clicked.connect(self.choose)
    row.addWidget(add)
    sort = QPushButton("이름순 정렬")
    sort.setIcon(icon("sort"))
    sort.clicked.connect(lambda: self.files.sort_names())
    row.addWidget(sort)
    remove = QPushButton("선택 제거")
    remove.setIcon(icon("delete"))
    remove.setToolTip("체크한 파일을 목록에서 제거합니다. 원본은 보존됩니다.")
    remove.clicked.connect(self.remove)
    row.addWidget(remove)
    row.addStretch()
    self.count_label = QLabel("0 / 0개 선택")
    self.count_label.setObjectName("selectionCount")
    row.addWidget(self.count_label)
    settings_button = QPushButton()
    settings_button.setObjectName("settings")
    settings_button.setIcon(icon("gear"))
    settings_button.setAccessibleName("설정")
    settings_button.setToolTip("설정")
    settings_button.clicked.connect(self.open_settings)
    row.addWidget(settings_button)
    self.help_button = QPushButton("?")
    self.help_button.setObjectName("help")
    self.help_button.setAccessibleName("사용 설명")
    self.help_button.setToolTip("사용 설명 (F1)")
    self.help_button.clicked.connect(self.open_help)
    row.addWidget(self.help_button)
    settings_button.setFixedSize(40, 40)
    self.help_button.setFixedSize(40, 40)
    self.help_shortcut = QShortcut("F1", self)
    self.help_shortcut.activated.connect(self.open_help)
    layout.addWidget(toolbar)
    self.mode_tabs = QTabBar()
    self.mode_tabs.setStyleSheet(
        "QTabBar::tab {background:#FFFFFF;color:#60718A;padding:12px 24px;"
        "border-bottom:2px solid #E2E8F0;}"
        "QTabBar::tab:selected {color:#2E83F2;border-bottom:2px solid #2E83F2;font-weight:600;}"
        "QTabBar::tab:hover {background:#EAF3FF;color:#216ABC;}"
    )
    self.mode_tabs.addTab("파일 변환")
    self.mode_tabs.addTab("파일명 변경")
    layout.addWidget(self.mode_tabs)
    self.files = Files(allow_all=True)
    self.files.changed.connect(self.refresh_count)
    layout.addWidget(self.files, 1)
    options = QFrame()
    options.setObjectName("options")
    row = QHBoxLayout(options)
    row.setContentsMargins(18, 14, 18, 14)
    row.setSpacing(12)
    row.addWidget(QLabel("출력 형식"))
    self.fmt = QComboBox()
    self.fmt.setItemDelegate(OutputFormatDelegate(self.fmt))
    self.fmt.addItems(
        [
            "PDF",
            "PNG",
            "JPEG",
            "HWPX",
            "DOCX",
            "PPTX",
            "XLSX",
            "용량 축소",
            "페이지 나누기",
            "시트 합치기",
            "시트 나누기",
        ]
    )
    self.fmt.setFixedWidth(150)
    self.fmt.setToolTip("XLSX 출력은 매크로를 저장하지 않습니다. 원본 파일은 보존됩니다.")
    row.addWidget(self.fmt)
    self.paper_label = QLabel("용지 방향")
    self.paper_orientation = QComboBox()
    for label, value in (("자동", "auto"), ("가로", "landscape"), ("세로", "portrait")):
        self.paper_orientation.addItem(label, value)
    self.paper_orientation.setAccessibleName("PDF 용지 방향")
    row.addWidget(self.paper_label)
    row.addWidget(self.paper_orientation)
    self.paper_label.hide()
    self.paper_orientation.hide()
    self.compression_profile = QComboBox()
    add_profiles(self.compression_profile)
    self.compression_profile.setMinimumWidth(140)
    self.compression_profile.setMaximumWidth(260)
    self.compression_profile.setCurrentIndex(
        self.compression_profile.findData(read_options(self.settings)["profile"])
    )
    self.compression_profile.hide()
    row.addWidget(self.compression_profile)
    row.addStretch()
    self.individual = QPushButton("각각 저장")
    self.individual.setObjectName("separate")
    self.individual.setCheckable(True)
    self.individual.setChecked(True)
    self.merge = QPushButton("하나로 합치기")
    self.merge.setObjectName("merge")
    self.merge.setCheckable(True)
    self.save_mode = QButtonGroup(self)
    self.save_mode.setExclusive(True)
    self.save_mode.addButton(self.individual)
    self.save_mode.addButton(self.merge)
    segment = QHBoxLayout()
    segment.setSpacing(0)
    segment.addWidget(self.individual)
    segment.addWidget(self.merge)
    row.addLayout(segment)
    self.pdf_pages = QPushButton("페이지 나누기 / 추출")
    self.pdf_pages.clicked.connect(lambda: self.start_pdf_pages(self.files.checked_paths()))
    self.pdf_pages.hide()
    row.addWidget(self.pdf_pages)
    self.fmt.currentTextChanged.connect(self.output_changed)
    layout.addWidget(options)
    footer = QFrame()
    footer.setObjectName("footer")
    row = QHBoxLayout(footer)
    row.setContentsMargins(18, 12, 18, 14)
    row.setSpacing(12)
    folder = QLabel()
    folder.setPixmap(icon("folder").pixmap(20, 20))
    row.addWidget(folder)
    self.output_folders = []
    self.notification_folders = []
    self.status = QLabel(self.output_location_text())
    self.status.setObjectName("status")
    self.status.setWordWrap(True)
    self.status.linkActivated.connect(self.status_link)
    row.addWidget(self.status, 1)
    self.stop_job = QPushButton("작업 중지")
    self.stop_job.clicked.connect(self.request_stop)
    self.stop_job.hide()
    row.addWidget(self.stop_job)
    self.run = QPushButton("변환 시작  →")
    self.run.setObjectName("convert")
    self.run.setMinimumWidth(184)
    self.run.clicked.connect(self.start)
    row.addWidget(self.run)
    layout.addWidget(footer)
    self.files.setColumnCount(6)
    self.files.headerItem().setText(4, "변경될 이름")
    self.files.headerItem().setText(5, "상태")
    self.files.setColumnWidth(4, 250)
    self.files.setColumnWidth(5, 210)
    from rename_ui import RenamePanel

    self.rename_panel = RenamePanel(self)
    layout.insertWidget(layout.count() - 2, self.rename_panel)
    self.files.header().moveSection(
        self.files.header().visualIndex(6), self.files.header().visualIndex(4)
    )
    self.conversion_size = self.size()
    self.previous_mode = 0

    def change_mode(index):
        if index == 1 and self.previous_mode == 0:
            self.conversion_size = self.size()
        self.setMinimumWidth(1100 if index == 1 else 760)
        self.files.setProperty("compactRows", index == 1)
        for row_index in range(self.files.count()):
            self.files.item(row_index).setSizeHint(0, QSize(70, 48 if index == 1 else 60))
        self.rename_panel.setVisible(index == 1)
        options.setVisible(index == 0)
        footer.setVisible(index == 0)
        for column in [4, 5]:
            self.files.setColumnHidden(column, index == 0)
        self.files.setColumnHidden(6, index == 0 or not self.rename_panel.text_enabled.isChecked())
        for column in [1, 3]:
            self.files.setColumnHidden(column, index == 1)
        self.layout().invalidate()
        self.layout().activate()
        if not self.isMaximized():
            if index == 1 and self.previous_mode == 0:
                available = self.screen().availableGeometry().height() - 40
                self.resize(self.width(), min(max(self.height(), 820), available))
            elif index == 0 and self.previous_mode == 1:
                self.resize(self.conversion_size)
        self.previous_mode = index
        self.rename_panel.refresh()
        self.files.use_column_layout(lambda: self.settings, "rename" if index == 1 else "convert")

    self.mode_tabs.currentChanged.connect(change_mode)
    change_mode(0)
