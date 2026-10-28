import pefile,struct
from unicorn import Uc,UC_ARCH_X86,UC_MODE_64,UC_HOOK_CODE
from unicorn.x86_const import *
pe=pefile.PE(str(__import__('pathlib').Path(__file__).with_name('BakuriFileConverter.exe')));base=pe.OPTIONAL_HEADER.ImageBase
u=Uc(UC_ARCH_X86,UC_MODE_64);u.mem_map(base,(pe.OPTIONAL_HEADER.SizeOfImage+4095)&~4095);u.mem_write(base,pe.get_memory_mapped_image())
u.mem_map(0x50000000,0x10000);u.mem_map(0x60000000,0x10000);u.mem_map(0x70000000,0x200000)
path='C:\\테스트 폴더\\바꾸리\\BakuriFileConverter.exe';cmd='"'+path+'" --add-files "D:\\문서 폴더\\사진 1.png"'
u.mem_write(0x60000000,cmd.encode('utf-16-le')+b'\0\0')
functions={};calls=[]
for idx,e in enumerate(x for d in pe.DIRECTORY_ENTRY_IMPORT for x in d.imports):
 addr=0x50000000+idx*16;functions[addr]=e.name.decode();u.mem_write(e.address,struct.pack('<Q',addr));u.mem_write(addr,b'\xc3')
def readstr(addr):
 data=bytearray()
 while True:
  w=u.mem_read(addr,2);addr+=2
  if w==b'\0\0':return data.decode('utf-16-le')
  data+=w

def hook(u,addr,size,_):
 if addr not in functions:return
 name=functions[addr];calls.append(name);args=[u.reg_read(r) for r in [UC_X86_REG_RCX,UC_X86_REG_RDX,UC_X86_REG_R8,UC_X86_REG_R9]];rsp=u.reg_read(UC_X86_REG_RSP);ret=1
 if name=='GetModuleFileNameW':u.mem_write(args[1],path.encode('utf-16-le')+b'\0\0');ret=len(path)
 elif name=='GetCommandLineW':ret=0x60000000
 elif name=='CreateProcessW':
  exe=readstr(args[0]);command=readstr(args[1]);assert exe=='C:\\테스트 폴더\\바꾸리\\runtime\\pythonw.exe',exe
  assert command=='"'+exe+'" "C:\\테스트 폴더\\바꾸리\\app.py"  --add-files "D:\\문서 폴더\\사진 1.png"',command
  si=struct.unpack('<Q',u.mem_read(rsp+72,8))[0];pi=struct.unpack('<Q',u.mem_read(rsp+80,8))[0]
  assert struct.unpack('<I',u.mem_read(si,4))[0]==104
  u.mem_write(pi,struct.pack('<QQII',111,222,333,444))
 elif name=='GetExitCodeProcess':u.mem_write(args[1],struct.pack('<I',0))
 elif name=='ExitProcess':assert args[0]==0,args[0];u.emu_stop()
 u.reg_write(UC_X86_REG_RAX,ret)
u.hook_add(UC_HOOK_CODE,hook);u.reg_write(UC_X86_REG_RSP,0x701fffe8);u.emu_start(base+pe.OPTIONAL_HEADER.AddressOfEntryPoint,base+pe.OPTIONAL_HEADER.SizeOfImage,count=200000)
assert 'CreateProcessW' in calls and calls[-1]=='ExitProcess',calls
print('PASS native Windows launcher emulation: Unicode/spaces, argument forwarding, STARTUPINFO x64 layout, process wait/exit')
