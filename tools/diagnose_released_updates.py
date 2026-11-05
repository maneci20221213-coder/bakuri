"""Exercise the real released executable, not a replacement Python updater."""
import json, os, subprocess, time, winreg
from pathlib import Path
import win32con, win32gui
from PIL import ImageGrab

root = Path('UpdateDiagnostics').resolve()
root.mkdir(exist_ok=True)
installed = Path(os.environ['TEMP']) / 'BakuriOld102'
log = Path(os.environ['LOCALAPPDATA']) / 'Bakuri/errors.log'
env = dict(os.environ, QT_QPA_PLATFORM='windows', BAKURI_DISABLE_SHELL_INTEGRATION='1')

def kill():
    subprocess.run(['taskkill','/IM','BakuriFileConverter.exe','/T','/F'],capture_output=True)
    time.sleep(1)

def windows():
    found=[]
    def visit(hwnd, _):
        try:
            title=win32gui.GetWindowText(hwnd)
            if win32gui.IsWindowVisible(hwnd) and ('바꾸리' in title or 'Bakuri' in title):
                found.append((hwnd,title))
        except win32gui.error:
            pass
    win32gui.EnumWindows(visit,None)
    return found

def check(exe, label, wait=75):
    log.unlink(missing_ok=True)
    subprocess.Popen([str(exe)],env=env)
    deadline=time.monotonic()+wait
    observed=[]
    while time.monotonic()<deadline:
        observed=windows()
        if any(title=='바꾸리 업데이트' for _,title in observed):
            break
        time.sleep(.25)
    ImageGrab.grab().save(root/(label+'.png'))
    report={'label':label,'windows':[title for _,title in observed],
            'prompt':any(title=='바꾸리 업데이트' for _,title in observed),
            'errors':log.read_text(encoding='utf-8') if log.exists() else ''}
    print(json.dumps(report,ensure_ascii=False),flush=True)
    (root/(label+'.json')).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return observed

kill()
subprocess.run([str(Path('Old/BakuriSetup.exe').resolve()),'--silent','--desktop-shortcut=0','--installto',str(installed)],check=True,env=env)
kill()
try:
    key=winreg.CreateKey(winreg.HKEY_CURRENT_USER,r'Software\Bakuri\FileConverter')
    try:winreg.DeleteValue(key,'update_skipped_version')
    except FileNotFoundError:pass
    winreg.CloseKey(key)
    exe=installed/'current/BakuriFileConverter.exe'
    visible=check(exe,'installed-first')
    for hwnd,title in visible:
        if title=='바꾸리 업데이트':
            win32gui.PostMessage(hwnd,win32con.WM_CLOSE,0,0)
    time.sleep(.5)
    for hwnd,title in windows():
        if '파일 변환기' in title:
            win32gui.PostMessage(hwnd,win32con.WM_CLOSE,0,0)
    time.sleep(.5)
    check(exe,'installed-reopen',wait=12)
    kill()
    portable=next(Path('Old/Portable').rglob('BakuriFileConverter.exe')).resolve()
    check(portable,'portable-first')
finally:
    kill()
