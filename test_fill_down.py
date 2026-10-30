import os,unittest
os.environ['QT_QPA_PLATFORM']='offscreen'
from rename_engine import fill_down

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
