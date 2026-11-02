"""Native Windows MPO choice dialog, conversion and compression outputs."""
import os
os.environ['QT_QPA_PLATFORM']='windows'
os.environ['BAKURI_DISABLE_SHELL_INTEGRATION']='1'
from pathlib import Path
import tempfile
from unittest.mock import patch
from PySide6.QtWidgets import QApplication,QLabel
from PySide6.QtTest import QTest
from PySide6.QtCore import QTimer,Qt,QSettings
from test_multi_image import make_mpo
from bakuri.ui.multi_image import MultiImageDialog
from bakuri.application.runner import execute
from bakuri.application.control import JobControl
from app import Window

app=QApplication([])
output=Path('DevArtifacts');output.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as folder:
    source=make_mpo(Path(folder)/'여러사진.jpg')
    original=source.read_bytes()
    w=Window();w.settings=QSettings(str(Path(folder)/'settings.ini'),QSettings.IniFormat)
    errors=[]
    def choose(mode):
        try:
            dialog=app.activeModalWidget()
            assert isinstance(dialog,MultiImageDialog)
            assert any('2장' in label.text() for label in dialog.findChildren(QLabel))
            dialog.grab().save(str(output/'native-mpo-choice.png'))
            QTest.mouseClick(dialog.all_images if mode=='all' else dialog.primary,Qt.LeftButton)
        except Exception as error:
            errors.append(error)
            if app.activeModalWidget():app.activeModalWidget().reject()
    try:
        w.files.add_paths([str(source)]);w.show();QTest.qWait(50)
        with patch.object(w,'begin_job') as begin:
            QTimer.singleShot(50,lambda:choose('all'))
            w.start_conversion([str(source)],'pdf',True)
            assert not errors,errors
            request=begin.call_args.args[0]
        control=JobControl();execute(request,control)
        assert len(control.outputs)==2
        assert all(Path(p).parent==source.parent.resolve() and Path(p).is_file() for p in control.outputs)
        with patch.object(w,'begin_job') as begin:
            QTimer.singleShot(50,lambda:choose('primary'))
            w.quick_paths=[str(source)];w.quick_selected('compress')
            assert not errors,errors
            request=begin.call_args.args[0]
        control=JobControl();execute(request,control)
        assert len(control.outputs)==1 and len(control.rows)==1
        assert '대표 이미지만 선택' in control.rows[0]['detail']
        assert control.rows[0]['source']==str(source.resolve())
        assert source.read_bytes()==original
        print('Native MPO choice, individual PDF outputs and representative JPEG compression verification passed.')
    finally:
        w.popup.hide();w.results.toast.hide();w.tray.hide();w.hide()
