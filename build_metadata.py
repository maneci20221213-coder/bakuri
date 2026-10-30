"""Generate PyInstaller version metadata from version.py (Windows build input)."""
from pathlib import Path
from version import VERSION

def generate(root=None):
 root=Path(root or Path(__file__).resolve().parent)
 a,b,c=map(int,VERSION.split('-',1)[0].split('.'));quad=(a,b,c,0);flags=0x2 if '-' in VERSION else 0x0
 data=f'''VSVersionInfo(ffi=FixedFileInfo(filevers={quad!r},prodvers={quad!r},mask=0x3f,flags={flags:#x},OS=0x40004,fileType=0x1,subtype=0x0,date=(0,0)),kids=[StringFileInfo([StringTable('040904B0',[StringStruct('FileDescription','바꾸리 파일 변환기'),StringStruct('FileVersion',{VERSION!r}),StringStruct('ProductName','Bakuri'),StringStruct('ProductVersion',{VERSION!r}),StringStruct('OriginalFilename','BakuriFileConverter.exe')])]),VarFileInfo([VarStruct('Translation',[1033,1200])])])'''
 path=root/'version-resource.txt';path.write_text(data,encoding='utf-8');return path
def generate_icons(root=None):
 from PySide6.QtCore import Qt
 from PySide6.QtGui import QImage,QPainter
 from PySide6.QtSvg import QSvgRenderer
 from PIL import Image
 root=Path(root or Path(__file__).resolve().parent)
 renderer=QSvgRenderer(str(root/'assets/app-mark.svg'))
 if not renderer.isValid():raise ValueError('Invalid application SVG')
 canvas=QImage(1024,1024,QImage.Format_ARGB32_Premultiplied);canvas.fill(Qt.transparent)
 painter=QPainter(canvas);renderer.render(painter);painter.end()
 if not canvas.save(str(root/'assets/app.png')):raise OSError('Unable to write application PNG')
 with Image.open(root/'assets/app.png') as image:
  image.save(root/'assets/app.ico',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
 generate_tray(root)
def generate_tray(root=None):
 from shutil import copyfile
 root=Path(root or Path(__file__).resolve().parent)
 copyfile(root/'assets/app.png',root/'assets/tray.png')
if __name__=='__main__':
 print(generate());generate_icons()
