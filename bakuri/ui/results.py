"""Completion-only notifications, recent results and output folder actions."""

from pathlib import Path
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QCursor
from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QHBoxLayout,
    QPushButton,
    QMessageBox,
    QMenu,
)
from work_ui import CompressionResults
from user_messages import friendly_error
from bakuri.domain.models import JobReport
from .completion_toast import CompletionToast


class ResultsPresenter:
    def __init__(self, window):
        self.window = window
        self.toast = CompletionToast(
            self.show_last_result, lambda: self.open_folders(window.notification_folders)
        )
        window.destroyed.connect(self.toast.deleteLater)

    def show_completion(self, summary, folders, rows=None, warning=False):
        window = self.window
        folders = list(dict.fromkeys(folders))
        window.notification_folders = folders[:]
        window.last_result = dict(summary=summary, folders=folders, rows=list(rows or []))
        window.tray_result_action.setEnabled(True)
        window.tray.setToolTip(("바꾸리 · " + summary)[:127])
        if window.settings.value("notify", True, type=bool):
            self.toast.present(summary, bool(folders), warning, window.tray.geometry())
        else:
            self.toast.hide()

    def show_last_result(self):
        window = self.window
        if not window.last_result:
            return
        result = window.last_result
        dialog = QDialog(window)
        dialog.setWindowTitle("최근 작업 결과")
        dialog.setMinimumWidth(440)
        layout = QVBoxLayout(dialog)
        label = QLabel(result["summary"])
        label.setTextFormat(Qt.PlainText)
        label.setWordWrap(True)
        layout.addWidget(label)
        buttons = QHBoxLayout()
        folder = QPushButton("저장 폴더 열기")
        folder.setEnabled(bool(result["folders"]))
        folder.clicked.connect(lambda: window.open_folders(result["folders"]))
        buttons.addWidget(folder)
        if result["rows"]:
            details = QPushButton("파일별 상세 결과")
            details.clicked.connect(lambda: CompressionResults(result["rows"], dialog).exec())
            buttons.addWidget(details)
        close = QPushButton("닫기")
        close.clicked.connect(dialog.accept)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        dialog.exec()

    def status_link(self, link):
        window = self.window
        if link == "details":
            CompressionResults(window.compression_rows, window).exec()
        else:
            window.open_folders(window.output_folders)

    def open_folders(self, folders):
        window = self.window
        if not folders:
            return

        def show(folder):
            if not Path(folder).is_dir():
                QMessageBox.warning(window, "폴더 열기", "저장 폴더가 이동되거나 삭제되었습니다.")
                return
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

        if len(folders) == 1:
            show(folders[0])
            return
        menu = QMenu(window)
        for folder in folders:
            menu.addAction(folder, lambda folder=folder: show(folder))
        menu.exec(QCursor.pos())

    def finished(self, result):
        window = self.window
        if isinstance(result, JobReport):
            result = dict(
                paths=list(result.paths),
                rows=[row.as_dict() for row in result.rows],
                outcome=result.outcome.value,
                error=result.error,
                kind=result.kind.value,
            )
        if isinstance(result, list):
            result = dict(paths=result, rows=[], outcome="done", error="", kind="convert")
        paths = result["paths"]
        outcome = result["outcome"]
        window.reset()
        window.compression_rows = result.get("rows", [])
        window.output_folders = list(dict.fromkeys(str(Path(p).parent) for p in paths))
        window.notification_folders = window.output_folders[:]
        saved = f"{len(paths)}개 저장 완료"
        summary = (
            "작업 중지 · " + saved
            if outcome == "cancelled"
            else "작업 실패 · " + saved if outcome == "failed" else saved
        )
        if result.get("kind") == "compress":
            skipped = sum(
                row["status"] in ("건너뜀", "축소 효과 없음") for row in window.compression_rows
            )
            failed = sum(row["status"] == "실패" for row in window.compression_rows)
            summary += f" · 건너뜀 {skipped}개 · 실패 {failed}개"
            from tray_results import compression_savings

            savings = compression_savings(window.compression_rows)
            if savings:
                summary += "\n" + savings
        links = []
        if paths:
            links.append(
                '<a style="color:#2E83F2;text-decoration:none" href="open">저장 폴더 열기</a>'
            )
        if window.compression_rows:
            links.append(
                '<a style="color:#2E83F2;text-decoration:none" href="details">상세 결과</a>'
            )
        window.status.setText(summary + (" · " + " · ".join(links) if links else ""))
        if outcome == "failed":
            summary += (
                "\n"
                + friendly_error(result.get("error", ""))
                + "\n원본과 이미 저장된 결과는 그대로 남아 있습니다."
            )
        window.show_completion(
            summary,
            window.output_folders,
            window.compression_rows,
            warning=outcome == "failed"
            or any(r.get("status") == "실패" for r in window.compression_rows),
        )
