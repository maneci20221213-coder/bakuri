"""Developer-only verification of a saved Windows shortcut and its real target."""
import os
import sys
from pathlib import Path
import pythoncom
from win32com.shell import shell,shellcon


def verify(link,root):
    pythoncom.CoInitialize()
    try:
        shortcut=pythoncom.CoCreateInstance(shell.CLSID_ShellLink,None,
                                           pythoncom.CLSCTX_INPROC_SERVER,shell.IID_IShellLink)
        shortcut.QueryInterface(pythoncom.IID_IPersistFile).Load(str(link))
        target=shortcut.GetPath(0)[0]
        print('Saved shortcut target:',repr(target),flush=True)
        print('Installation directory:',repr(str(root)),flush=True)
        candidates=[root/'BakuriFileConverter.exe',root/'바꾸리.exe',root/'current'/'BakuriFileConverter.exe']
        if not os.path.isfile(target) or not any(p.is_file() and os.path.samefile(target,p) for p in candidates):
            raise RuntimeError('Shortcut target does not match an installed executable')
        if not shortcut.GetDescription():raise RuntimeError('Shortcut description missing')
    finally:
        pythoncom.CoUninitialize()

if __name__=='__main__':verify(Path(sys.argv[1]),Path(sys.argv[2]))
