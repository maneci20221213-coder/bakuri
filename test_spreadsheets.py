import unittest,tempfile,types,sys
from pathlib import Path
from unittest.mock import patch
from engine import convert,SPREADSHEETS,text_import_options

class SpreadsheetTests(unittest.TestCase):
 def test_excel_inputs_save_as_xlsx(self):
  calls=[]
  class Book:
   def SaveAs(self,path,FileFormat):calls.append(('save',FileFormat));Path(path).write_bytes(b'xlsx')
   def Close(self,*args):calls.append(('close',))
  class Workbooks:
   def Open(self,path,**kwargs):calls.append(('open',Path(path).suffix));return Book()
   def OpenText(self,path,**kwargs):calls.append(('text',kwargs['Tab'],kwargs['Comma']))
  class App:
   def __init__(self):self.Workbooks=Workbooks()
   @property
   def ActiveWorkbook(self):return Book()
   def Quit(self):calls.append(('quit',))
  com=types.ModuleType('pythoncom');com.CoInitialize=lambda:None;com.CoUninitialize=lambda:None
  client=types.ModuleType('win32com.client');client.DispatchEx=lambda name:(calls.append(('start',name)) or App())
  package=types.ModuleType('win32com');package.client=client
  with patch.dict(sys.modules,{'pythoncom':com,'win32com':package,'win32com.client':client}),tempfile.TemporaryDirectory() as d:
   paths=[]
   for i,ext in enumerate(sorted(SPREADSHEETS)):
    p=Path(d)/(str(i)+ext);p.write_text('이름\t금액\n가\t100\n' if ext=='.tsv' else '이름,금액\n가,100\n',encoding='utf-8');paths.append(p)
   originals={p:p.read_bytes() for p in paths};outputs=convert(paths,'xlsx')
   self.assertEqual(len(outputs),len(SPREADSHEETS));self.assertTrue(all(Path(p).suffix=='.xlsx' for p in outputs))
   for p,content in originals.items():self.assertEqual(p.read_bytes(),content)
  self.assertEqual(sum(c[0]=='start' for c in calls),1);self.assertEqual([c[1] for c in calls if c[0]=='save'],[51]*len(SPREADSHEETS));self.assertEqual(sum(c[0]=='close' for c in calls),len(SPREADSHEETS));self.assertEqual(calls[-1],('quit',))
 def test_text_encoding_and_delimiters(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'korean.csv';p.write_text('이름;금액\n홍길동;123\n',encoding='cp949');options=text_import_options(p)
   self.assertEqual(options['Origin'],949);self.assertTrue(options['Semicolon'])
 def test_document_to_xlsx_rejected(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'scan.pdf';p.write_bytes(b'pdf')
   with self.assertRaises(ValueError):convert([p],'xlsx')
