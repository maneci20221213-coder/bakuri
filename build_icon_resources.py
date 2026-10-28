"""Embed the approved ICO and current version metadata in the portable Windows launcher.
Developer-only dependency: lief. Does not change executable code or imports.
"""
from pathlib import Path
import struct
import lief
from version import VERSION
ROOT=Path(__file__).resolve().parent

def block(key,value=b'',children=b'',kind=1,value_length=None):
    data=bytearray(b'\0'*6+key.encode('utf-16le')+b'\0\0')
    data.extend(b'\0'*((-len(data))%4));data.extend(value)
    if children:data.extend(b'\0'*((-len(data))%4));data.extend(children)
    struct.pack_into('<HHH',data,0,len(data),len(value)//2 if value_length is None and kind==1 else len(value) if value_length is None else value_length,kind)
    return bytes(data)

def resource_tree():
    root=lief.PE.ResourceDirectory()
    def add(kind,ident,data):
        branch=next((c for c in root.childs if c.id==kind),None)
        if branch is None:
            node=lief.PE.ResourceDirectory();node.id=kind;branch=root.add_child(node)
        node=lief.PE.ResourceDirectory();node.id=ident;node=branch.add_child(node)
        leaf=lief.PE.ResourceData(list(data),0);leaf.id=1033;node.add_child(leaf)
    ico=(ROOT/'assets/app.ico').read_bytes();_,_,count=struct.unpack_from('<HHH',ico)
    group=bytearray(struct.pack('<HHH',0,1,count))
    for i in range(count):
        w,h,colors,res,planes,bits,size,offset=struct.unpack_from('<BBBBHHII',ico,6+16*i)
        add(3,i+1,ico[offset:offset+size]);group.extend(struct.pack('<BBBBHHIH',w,h,colors,res,planes,bits,size,i+1))
    add(14,1,group)
    strings=b''
    for key,value in {'FileDescription':'바꾸리 파일 변환기','ProductName':'Bakuri','FileVersion':VERSION,'ProductVersion':VERSION,'OriginalFilename':'BakuriFileConverter.exe'}.items():
        item=block(key,(value+'\0').encode('utf-16le'));strings+=item+b'\0'*((-len(item))%4)
    major,minor,patch=map(int,VERSION.split('.'));ms=(major<<16)|minor;ls=patch<<16
    fixed=struct.pack('<13I',0xFEEF04BD,0x10000,ms,ls,ms,ls,0x3F,0,0x40004,1,0,0,0)
    children=block('StringFileInfo',children=block('040904b0',children=strings))
    children+=b'\0'*((-len(children))%4)
    children+=block('VarFileInfo',children=block('Translation',struct.pack('<HH',1033,1200),kind=0))
    add(16,1,block('VS_VERSION_INFO',fixed,children,kind=0))
    return root

if __name__=='__main__':
    exe=ROOT/'BakuriFileConverter.exe';data=exe.read_bytes()
    old='Bakuri Python Trial'.encode('utf-16le');new='Bakuri'.encode('utf-16le')
    data=data.replace(old,new+b'\0'*(len(old)-len(new)))
    binary=lief.PE.parse(list(data));binary.set_resources(resource_tree())
    config=lief.PE.Builder.config_t();config.resources=True
    builder=lief.PE.Builder(binary,config);builder.build();builder.write(str(exe))
