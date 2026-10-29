import os,unittest
from unittest.mock import patch
os.environ['QT_QPA_PLATFORM']='offscreen'
from PySide6.QtWidgets import QApplication,QDialog
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from rename_engine import fill_down
from rename_ui import PasteTextDialog
APP=QApplication.instance() or QApplication([])

class FillDownTests(unittest.TestCase):
 def test_one_line_fills_all_selected_files(self):
  self.assertEqual(fill_down('서울',4),['서울']*4)
  self.assertEqual(fill_down('서울\r\n',1),['서울'])
 def test_gaps_and_missing_rows_repeat_nearest_value(self):
  self.assertEqual(fill_down('서울\n\n부산\n   \n대전',7),['서울','서울','부산','부산','대전','대전','대전'])
  self.assertEqual(fill_down('\n서울\n\n부산',5),['','서울','서울','부산','부산'])
  self.assertEqual(fill_down(' 서울 ',2),[' 서울 ',' 서울 '])
 def test_rejects_empty_extra_or_multi_column_without_truncation(self):
  for text,count in [('',3),(' \n ',3),('a\nb\nc',2),('a\tb',1),('a',0)]:
   with self.assertRaises(ValueError):fill_down(text,count)
 def test_button_preview_and_confirm_auto_fill(self):
  APP.clipboard().clear();dialog=PasteTextDialog(4)
  dialog.text.setPlainText('서울');QTest.mouseClick(dialog.fill,Qt.LeftButton)
  self.assertEqual(dialog.text.toPlainText(),'서울\n서울\n서울\n서울');self.assertEqual(dialog.values,[])
  dialog.text.setPlainText('서울\n\n부산');dialog.assign()
  self.assertEqual(dialog.values,['서울','서울','부산','부산']);self.assertEqual(dialog.result(),QDialog.Accepted)
  other=PasteTextDialog(2);other.text.setPlainText('하나\n둘\n셋')
  with patch('rename_ui.QMessageBox.information') as notice:
   other.fill_blanks();notice.assert_called_once();self.assertEqual(other.text.toPlainText(),'하나\n둘\n셋')
  self.assertEqual(other.values,[]);other.reject()
