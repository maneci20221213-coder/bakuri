"""Main window coordinates views, requests and platform integration."""

import sys, os, threading
from collections import deque
from pathlib import Path
from build_channel import DEVELOPMENT, SETTINGS_APP
from user_messages import friendly_error
from PySide6.QtCore import Qt, QSettings, QEvent, QTimer
from PySide6.QtGui import QColor, QBrush, QKeySequence
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QApplication,
    QFileDialog,
    QDialog,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPlainTextEdit,
    QSystemTrayIcon,
    QTextEdit,
    QWidget,
)
from bakuri.domain.formats import SUPPORTED, can_convert, can_merge, IMAGES, PAGE_SPLIT_INPUTS, CAD
from bakuri.application.control import JobControl
from bakuri.application.progress import ProgressEstimate
from settings_ui import SettingsDialog
from theme import icon
from help_ui import HelpDialog
from work_ui import read_options
from .events import Events
from .quick_popup import QuickPopup
from .main_view import build_main_view
from .settings_store import initialize_settings
from .results import ResultsPresenter
from bakuri.application.runner import run_job
from bakuri.application.settings import conversion_options, compression_options
from bakuri.domain.models import ConversionRequest, CompressionRequest, PdfPagesRequest


class Window(QWidget):
    def __init__(self):
        super().__init__()
        self.bus = Events()
        self.busy = False
        self.pending_jobs = deque()
        self.control = None
        self.estimate = ProgressEstimate()
        self.compression_rows = []
        self.job_kind = "convert"
        self.settings = QSettings("Bakuri", SETTINGS_APP)
        first_run = initialize_settings(self)
        build_main_view(self)
        app_icon = icon("app")
        self.setWindowIcon(app_icon)
        self.tray = QSystemTrayIcon(icon("tray"), self)
        menu = QMenu()
        menu.addAction("열기", lambda: self.open_main("tray"))
        menu.addAction("설정", self.open_settings)
        menu.addAction("사용 설명", self.open_help)
        self.tray.setContextMenu(menu)
        self.results = ResultsPresenter(self)
        self.progress_timer = QTimer(self)
        self.progress_timer.setInterval(1000)
        self.progress_timer.timeout.connect(self.refresh_progress)
        self.last_result = None
        self.tray_result_action = menu.addAction("최근 결과 보기", self.show_last_result)
        self.tray_result_action.setEnabled(False)
        self.tray_stop_action = menu.addAction("작업 중지", self.request_stop)
        self.tray_stop_action.setEnabled(False)
        self.tray_clear_action = menu.addAction("대기 작업 취소", self.clear_pending)
        self.tray_clear_action.setEnabled(False)
        menu.addSeparator()
        menu.addAction("완전 종료", self.quit)
        self.tray.setToolTip("바꾸리 · 대기 중")
        self.tray.activated.connect(
            lambda reason: self.open_main("tray") if reason == QSystemTrayIcon.Trigger else None
        )
        self.tray.show()
        from updater import UpdateController

        self.updater = UpdateController(self, self.settings, disabled=DEVELOPMENT)
        self.popup = QuickPopup(settings=self.settings)
        self.bus.clicked.connect(self.popup.clicked_at)
        self.bus.dismiss.connect(self.popup.hide)
        self.bus.popup_key.connect(self.popup.native_key)
        self.popup.chosen.connect(self.quick_selected)
        self.quick_paths = []
        self.bus.progress.connect(self.update_progress)
        self.bus.measured.connect(self.update_work)
        self.files.paste_requested.connect(self.paste_files)
        QApplication.instance().installEventFilter(self)
        self.bus.message.connect(self.status.setText)
        self.bus.error.connect(self.failed)
        self.bus.done.connect(self.finished)
        self.bus.selected.connect(self.receive)
        if sys.platform == "win32" and os.environ.get("BAKURI_DISABLE_SHELL_INTEGRATION") != "1":
            from windows import SelectionWatcher, MouseWatcher

            if not DEVELOPMENT:
                from windows import migrate_menu, initialize_startup

                try:
                    initialize_startup(self.settings, first_run=first_run)
                    if migrate_menu(self.settings.value("explorer", True, type=bool)):
                        self.settings.setValue("explorer", True)
                        self.settings.sync()
                except Exception as exc:
                    self.status.setText(friendly_error(exc, "menu"))
            self.watcher = SelectionWatcher(
                self.bus.selected.emit,
                self.bus.message.emit,
                self.settings,
                self.bus.dismiss.emit,
                self.bus.popup_key.emit,
            )
            self.popup.visibility.connect(self.popup_visibility)
            self.watcher.start()
            self.mouse_watcher = MouseWatcher(self.bus.clicked.emit)
            self.mouse_watcher.start()

    def eventFilter(self, obj, event):
        if (
            event.type() == QEvent.KeyPress
            and event.matches(QKeySequence.Paste)
            and isinstance(obj, QWidget)
            and (obj is self or self.isAncestorOf(obj))
        ):
            focus = QApplication.focusWidget() or obj
            if (
                not QApplication.activeModalWidget()
                and self.mode_tabs.currentIndex() == 1
                and self.rename_panel.paste_cells(focus)
            ):
                event.accept()
                return True
            if QApplication.activeModalWidget() or isinstance(
                focus, (QLineEdit, QTextEdit, QPlainTextEdit, QAbstractSpinBox)
            ):
                return super().eventFilter(obj, event)
            mime = QApplication.clipboard().mimeData()
            if mime and mime.hasUrls():
                self.paste_files()
                event.accept()
                return True
        return super().eventFilter(obj, event)

    def paste_files(self):
        if self.updater.installing:
            return
        mime = QApplication.clipboard().mimeData()
        paths = [u.toLocalFile() for u in mime.urls() if u.isLocalFile()] if mime else []
        before = self.files.count()
        self.files.add_paths(paths)
        added = self.files.count() - before
        if added:
            self.status.setText(f"{added}개 파일을 목록에 추가했습니다.")

    def show_completion(self, summary, folders, rows=None, warning=False):
        return self.results.show_completion(summary, folders, rows, warning)

    def show_last_result(self):
        return self.results.show_last_result()

    def popup_visibility(self, visible):
        self.watcher.popup_windows = (self.popup.origin, int(self.popup.winId()))
        self.watcher.popup_open = visible

    def refresh_count(self):
        self.count_label.setText(f"{len(self.files.checked_paths())} / {self.files.count()}개 선택")
        self.refresh_formats()

    def refresh_formats(self):
        paths = self.files.checked_paths()
        model = self.fmt.model()
        for index in range(self.fmt.count()):
            name = self.fmt.itemText(index)
            if name == "페이지 나누기":
                allowed = len(paths) == 1 and Path(paths[0]).suffix.lower() in PAGE_SPLIT_INPUTS
            elif name == "용량 축소":
                allowed = not paths or all(
                    Path(p).suffix.lower() in IMAGES | {".pdf"} for p in paths
                )
            else:
                allowed = not paths or all(can_convert(p, name) for p in paths)
            item = model.item(index)
            item.setEnabled(allowed)
            item.setForeground(QBrush(QColor("#26354A" if allowed else "#A4AFBD")))
            item.setToolTip(
                ""
                if allowed
                else (
                    "PDF, 한글 또는 Word 문서 한 개를 선택해 주세요."
                    if name == "페이지 나누기"
                    else "선택한 파일 중 이 형식으로 변환할 수 없는 파일이 있습니다."
                )
            )
        current = self.fmt.currentIndex()
        if current < 0 or not model.item(current).isEnabled():
            self.fmt.setCurrentIndex(
                next((i for i in range(self.fmt.count()) if model.item(i).isEnabled()), -1)
            )
        self.output_changed(self.fmt.currentText())

    def output_changed(self, format):
        paths = self.files.checked_paths()
        has_direction = format.lower() == "pdf" and any(
            Path(path).suffix.lower() in IMAGES | CAD for path in paths
        )
        self.paper_label.setVisible(has_direction)
        self.paper_orientation.setVisible(has_direction)
        self.paper_orientation.setEnabled(has_direction)
        single_pdf = (
            format.lower() == "pdf" and len(paths) == 1 and Path(paths[0]).suffix.lower() == ".pdf"
        )
        self.pdf_pages.setVisible(single_pdf)
        self.pdf_pages.setEnabled(single_pdf)
        splitting = format == "페이지 나누기"
        self.individual.setVisible(not splitting)
        self.merge.setVisible(not single_pdf and not splitting)
        self.individual.setText("전체 저장" if single_pdf else "각각 저장")
        allowed = can_merge(paths, format)
        self.merge.setEnabled(allowed)
        self.compression_profile.setVisible(format == "용량 축소")
        self.run.setText(
            "대기열에 추가"
            if self.busy
            else {"용량 축소": "용량 축소 시작", "페이지 나누기": "페이지 나누기  →"}.get(
                format, "변환 시작  →"
            )
        )
        if not allowed:
            self.individual.setChecked(True)

    def open_main(self, reason="expanded"):
        if self.isMinimized():
            self.showNormal()
        else:
            self.show()
        self.raise_()
        self.activateWindow()
        if hasattr(self, "updater"):
            self.updater.request(reason)

    def open_help(self):
        HelpDialog(self).exec()

    def output_location_text(self):
        mode = self.settings.value("output_mode", "source")
        return {
            "subfolder": "원본 폴더 안의 바꾸리 변환 폴더에 저장",
            "custom": "지정한 폴더에 새 파일로 저장",
        }.get(mode, "원본 폴더에 새 파일로 저장")

    def open_settings(self):
        if SettingsDialog(self).exec() == QDialog.Accepted:
            self.status.setText(self.output_location_text())
        self.compression_profile.setCurrentIndex(
            self.compression_profile.findData(read_options(self.settings)["profile"])
        )

    def receive(self, selection):
        if hasattr(self, "updater") and self.updater.installing:
            return
        paths, origin, tab = selection
        if sys.platform == "win32":
            import win32gui

            if win32gui.GetForegroundWindow() != origin:
                return
        self.quick_paths = [
            str(p) for p in paths if Path(p).is_file() and Path(p).suffix.lower() in SUPPORTED
        ]
        if not self.quick_paths:
            self.status.setText("지원하는 파일을 선택해 주세요.")
            return
        self.popup.present(self.quick_paths, origin, tab)

    def quick_selected(self, key):
        if hasattr(self, "updater") and self.updater.installing:
            return
        if key == "more":
            self.files.add_paths(self.quick_paths)
            self.open_main("expanded")
            return
        if key == "hwp_merge":
            self.start_conversion(self.quick_paths, "hwpx", True, self.popup.geometry().center())
        elif key == "pdf_split":
            self.start_pdf_pages(self.quick_paths)
        elif key == "pdf_merge":
            if len(self.quick_paths) < 2:
                QMessageBox.information(self, "PDF 합치기", "PDF 파일을 두 개 이상 선택해 주세요.")
                return
            self.start_conversion(self.quick_paths, "pdf", True, self.popup.geometry().center())
        elif key == "compress":
            self.start_compression(self.quick_paths, self.popup.geometry().center())
        else:
            merge = (
                len(self.quick_paths) > 1
                and key in {"pdf", "hwpx"}
                and all(Path(p).suffix.lower() in IMAGES | {".pdf"} for p in self.quick_paths)
            )
            self.start_conversion(self.quick_paths, key, merge, self.popup.geometry().center())

    def choose(self):
        self.files.add_paths(
            QFileDialog.getOpenFileNames(
                self,
                "파일 선택",
                "",
                "모든 파일 (*);;지원 변환 파일 ("
                + " ".join("*" + ext for ext in sorted(SUPPORTED))
                + ")",
            )[0]
        )

    def remove(self):
        for i in range(self.files.count() - 1, -1, -1):
            if self.files.item(i).checkState(0) == Qt.Checked:
                self.files.takeItem(i)

    def start(self):
        paths = self.files.checked_paths()
        if not paths:
            QMessageBox.information(self, "파일 선택", "변환할 파일의 체크박스를 선택해 주세요.")
            return
        if self.fmt.currentText() == "용량 축소":
            self.settings.setValue("compress_profile", self.compression_profile.currentData())
            self.start_compression(paths)
            return
        if (
            self.fmt.currentIndex() < 0
            or not self.fmt.model().item(self.fmt.currentIndex()).isEnabled()
        ):
            return
        if self.fmt.currentText() == "페이지 나누기":
            self.start_pdf_pages(paths)
            return
        fmt = self.fmt.currentText().lower()
        merge = self.merge.isChecked() and self.merge.isEnabled()
        orientation = (
            self.paper_orientation.currentData()
            if not self.paper_orientation.isHidden()
            else "auto"
        )
        self.start_conversion(paths, fmt, merge, orientation=orientation)

    def multi_image_choices(self, files):
        from .multi_image import choose_multi_images

        self.popup.hide()
        try:
            return choose_multi_images(files, self)
        except Exception as error:
            QMessageBox.information(self, "이미지 확인", friendly_error(error, "conversion"))
            return None

    def start_conversion(self, paths, fmt, merge, anchor=None, *, orientation="auto"):
        if any(not can_convert(p, fmt) for p in paths):
            QMessageBox.information(
                self,
                "출력 형식 확인",
                "선택한 파일에는 이 출력 형식을 사용할 수 없습니다. 파일의 체크 표시를 확인하고, 선택 가능한 다른 형식을 골라 주세요. 자세한 내용은 ? 버튼의 사용 설명에서 확인할 수 있습니다.",
            )
            return
        files = self.files.inputs_for(paths)
        choices = self.multi_image_choices(files)
        if choices is None:
            return
        try:
            options = conversion_options(self.settings, orientation)
        except ValueError as error:
            QMessageBox.information(self, "변환 설정", str(error))
            return
        request = ConversionRequest(files, fmt, merge, options, choices)
        self.begin_job(request, "convert", anchor)

    def start_pdf_pages(self, paths):
        if self.updater.installing:
            return
        if len(paths) != 1 or Path(paths[0]).suffix.lower() not in PAGE_SPLIT_INPUTS:
            return
        from bakuri.conversion.pdf_split import pdf_page_count
        from .pdf_split import PdfSplitDialog

        self.popup.hide()
        try:
            count = pdf_page_count(paths[0]) if Path(paths[0]).suffix.lower() == ".pdf" else None
        except Exception as error:
            QMessageBox.information(self, "PDF 확인", friendly_error(error, "conversion"))
            return
        dialog = PdfSplitDialog(paths[0], count, self)
        if dialog.exec() == QDialog.Accepted:
            request = PdfPagesRequest(self.files.inputs_for(paths)[0], **dialog.options())
            self.begin_job(request, "convert")

    def start_compression(self, paths, anchor=None):
        if any(Path(path).suffix.lower() not in IMAGES | {".pdf"} for path in paths):
            QMessageBox.information(self, "파일 확인", "용량 축소는 이미지와 PDF만 지원합니다.")
            return
        options = read_options(self.settings)
        self.compression_profile.setCurrentIndex(
            self.compression_profile.findData(options["profile"])
        )
        files = self.files.inputs_for(paths)
        choices = self.multi_image_choices(files)
        if choices is None:
            return
        request = CompressionRequest(files, compression_options(self.settings), choices)
        self.begin_job(request, "compress", anchor)

    def begin_job(self, operation, kind, anchor=None):
        if self.updater.installing:
            return
        # Requests already contain immutable paths and options, captured at submission.
        if self.busy:
            self.pending_jobs.append((operation, kind, anchor))
            self.tray_clear_action.setEnabled(True)
            self.tray_clear_action.setText(f"대기 작업 취소 ({len(self.pending_jobs)}개)")
            self.refresh_progress()
            if self.settings.value("notify", True, type=bool):
                self.results.toast.queued(
                    self.estimate.label(len(self.pending_jobs)),
                    len(self.pending_jobs),
                    self.tray.geometry(),
                )
                self.results.toast.set_progress(self.estimate.percent)
            return
        self.start_job(operation, kind, anchor)

    def start_job(self, operation, kind, anchor=None):
        # Renaming a queued input would invalidate its path. Conversion controls remain live.
        self.mode_tabs.setCurrentIndex(0)
        self.mode_tabs.setTabEnabled(1, False)
        self.rename_panel.setEnabled(False)
        self.popup.hide()
        self.busy = True
        self.job_kind = kind
        self.control = JobControl(self.bus.progress.emit, self.bus.measured.emit)
        control = self.control
        self.estimate = ProgressEstimate()
        self.stop_job.setToolTip("현재 작업만 중지합니다. 대기 작업은 이어서 처리합니다.")
        self.stop_job.show()
        self.stop_job.setEnabled(True)
        self.output_changed(self.fmt.currentText())
        self.tray_stop_action.setEnabled(True)
        if self.settings.value("notify", True, type=bool):
            self.results.toast.start_progress(
                self.estimate.label(len(self.pending_jobs)), self.tray.geometry()
            )
        self.refresh_progress()
        self.progress_timer.start()
        done = self.bus.done.emit

        def work():
            done(run_job(operation, control, kind, friendly_error))

        self.worker = threading.Thread(target=work, daemon=True)
        self.worker.start()

    def update_progress(self, percent, text):
        if not self.busy or (self.control and self.control.cancelled.is_set()):
            return
        self.estimate.update(percent, text)
        self.results.toast.set_progress(self.estimate.percent)
        self.refresh_progress()

    def update_work(self, done, total, stage):
        if not self.busy or (self.control and self.control.cancelled.is_set()):
            return
        self.estimate.measure(done, total, stage)
        self.refresh_progress()

    def refresh_progress(self):
        if not self.busy:
            return
        if self.control and self.control.cancelled.is_set():
            text = f"중지 요청 중 · 대기 {len(self.pending_jobs)}개"
        else:
            text = self.estimate.label(len(self.pending_jobs))
        self.status.setText(text)
        self.results.toast.update_progress(text)
        self.tray.setToolTip(("바꾸리 · " + text)[:127])

    def clear_pending(self):
        self.pending_jobs.clear()
        self.tray_clear_action.setEnabled(False)
        self.tray_clear_action.setText("대기 작업 취소")
        self.results.toast.set_notice("대기 작업을 취소했습니다. 진행 중인 작업은 계속합니다.")
        self.refresh_progress()

    def request_stop(self):
        if not self.busy or self.control is None:
            return
        self.control.cancel()
        self.stop_job.setText("중지 요청 중")
        self.stop_job.setEnabled(False)
        self.tray_stop_action.setEnabled(False)
        self.tray.setToolTip("바꾸리 · 중지 요청 중")
        self.status.setText("중지 요청 중 · 현재 처리 단계가 반환되면 중지합니다.")
        self.results.toast.update_progress("중지 요청 중")

    def reset(self):
        self.progress_timer.stop()
        if self.results.toast.showing_progress:
            self.results.toast.hide()
        self.busy = False
        self.control = None
        self.stop_job.hide()
        self.stop_job.setText("작업 중지")
        self.mode_tabs.setTabEnabled(1, not self.pending_jobs)
        self.rename_panel.setEnabled(not self.pending_jobs)
        self.output_changed(self.fmt.currentText())
        self.tray_stop_action.setEnabled(False)

    def failed(self, text):
        self.reset()
        self.status.setText("변환을 완료하지 못했습니다.")
        self.show()
        QMessageBox.warning(
            self,
            "변환을 완료하지 못했어요",
            friendly_error(text) + "\n\n원본과 이미 저장된 결과는 그대로 남아 있습니다.",
        )

    def finished(self, result):
        self.results.finished(result)
        # Start synchronously after presenting the result: no idle gap can reorder submissions.
        if self.pending_jobs:
            operation, kind, anchor = self.pending_jobs.popleft()
            previous = self.last_result["summary"].split("\n")[0] if self.last_result else ""
            self.tray_clear_action.setEnabled(bool(self.pending_jobs))
            self.tray_clear_action.setText(f"대기 작업 취소 ({len(self.pending_jobs)}개)")
            self.start_job(operation, kind, anchor)
            self.results.toast.set_notice("이전 작업 결과: " + previous)

    def status_link(self, link):
        return self.results.status_link(link)

    def open_folders(self, folders):
        return self.results.open_folders(folders)

    def quit(self):
        if self.busy:
            QMessageBox.information(self, "변환 중", "변환이 끝난 뒤 종료해 주세요.")
            return
        QApplication.quit()

    def closeEvent(self, e):
        if self.tray.isSystemTrayAvailable():
            self.files.clear()
            self.hide()
            e.ignore()
        elif self.busy:
            e.ignore()
        else:
            self.files.clear()
            e.accept()
