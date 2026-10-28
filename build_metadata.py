"""Generate PyInstaller version metadata from version.py (Windows build input)."""
from pathlib import Path
from version import VERSION

def generate(root=None):
 root=Path(root or Path(__file__).resolve().parent)
 a,b,c=map(int,VERSION.split('.'));quad=(a,b,c,0)
 data=f'''VSVersionInfo(ffi=FixedFileInfo(filevers={quad!r},prodvers={quad!r},mask=0x3f,flags=0x0,OS=0x40004,fileType=0x1,subtype=0x0,date=(0,0)),kids=[StringFileInfo([StringTable('040904B0',[StringStruct('FileDescription','바꾸리 파일 변환기'),StringStruct('FileVersion',{VERSION!r}),StringStruct('ProductName','Bakuri'),StringStruct('ProductVersion',{VERSION!r}),StringStruct('OriginalFilename','BakuriFileConverter.exe')])]),VarFileInfo([VarStruct('Translation',[1033,1200])])])'''
 path=root/'version-resource.txt';path.write_text(data,encoding='utf-8');return path
def generate_tray(root=None):
 from PIL import Image,ImageChops
 root=Path(root or Path(__file__).resolve().parent)
 with Image.open(root/'assets/app.png') as source:
  source=source.convert('RGBA')
  coverage=source.getchannel('R').point(lambda r:round(max(0,min(1,(255-r)/209))*255))
  alpha=ImageChops.multiply(source.getchannel('A'),coverage)
  tray=Image.new('RGBA',source.size,(46,131,242,0));tray.putalpha(alpha)
  tray.save(root/'assets/tray.png',optimize=True)
if __name__=='__main__':
 print(generate());generate_tray()
