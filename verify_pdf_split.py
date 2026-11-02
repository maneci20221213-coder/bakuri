"""CI-only native Windows split dialog and both user entry points."""
import os
os.environ['QT_QPA_PLATFORM'] = 'windows'
os.environ['BAKURI_DISABLE_SHELL_INTEGRATION'] = '1'
from pathlib import Path
import tempfile
from unittest.mock import patch
import fitz
from PySide6.QtCore import QTimer, Qt, QSettings
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialogButtonBox
from app import Window
from bakuri.ui.pdf_split import PdfSplitDialog
from bakuri.application.runner import execute
from bakuri.application.control import JobControl

app = QApplication([])
output = Path('DevArtifacts'); output.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as folder:
    source = Path(folder)/'페이지_시험.pdf'
    with fitz.open() as pdf:
        for i in range(7):
            pdf.new_page().insert_text((40,40),f'Page {i+1}')
        pdf.save(source)
    w = Window()
    w.settings = QSettings(str(Path(folder)/'settings.ini'),QSettings.IniFormat)
    try:
        w.files.add_paths([str(source)])
        w.show();w.fmt.setCurrentText('PDF');QTest.qWait(80)
        assert w.pdf_pages.isVisible() and not w.merge.isVisible()
        w.grab().save(str(output/'native-pdf-split-main.png'))
        errors = []
        def configure():
            try:
                dialog = app.activeModalWidget()
                assert isinstance(dialog, PdfSplitDialog)
                dialog.mode.setCurrentIndex(1);dialog.selection.setText('9')
                assert not dialog.buttons.button(QDialogButtonBox.Ok).isEnabled()
                dialog.selection.setText('1, 3-5')
                assert '4페이지' in dialog.summary.text()
                dialog.grab().save(str(output/'native-pdf-split-dialog.png'))
                dialog.accept()
            except Exception as error:
                errors.append(error)
                if app.activeModalWidget():app.activeModalWidget().reject()
        with patch.object(w,'begin_job') as begin:
            QTimer.singleShot(50,configure)
            QTest.mouseClick(w.pdf_pages,Qt.LeftButton)
            assert not errors, errors
            request = begin.call_args.args[0]
        control = JobControl();execute(request,control)
        with fitz.open(control.outputs[0]) as pdf:
            assert len(pdf)==4 and 'Page 3' in pdf[1].get_text()
        w.quick_paths=[str(source)];w.popup.present(w.quick_paths)
        assert w.popup.actions['pdf']=='pdf_split'
        with patch.object(w,'begin_job') as begin:
            QTimer.singleShot(50,configure)
            w.quick_selected('pdf_split')
            assert not errors, errors
            assert begin.call_args.args[0].selection=='1, 3-5'
        print('Native PDF split/extract dialog, quick/main entry points and generated pages verification passed.')
    finally:
        w.popup.hide();w.results.toast.hide();w.tray.hide();w.hide()
