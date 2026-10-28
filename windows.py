"""Explorer selection and keyboard events run outside the Qt UI thread."""
import sys, threading, ctypes, subprocess, winreg, queue, time, logging, os
from pathlib import Path
RUN=r'Software\Microsoft\Windows\CurrentVersion\Run'
NAME='Bakuri'
KEYS={'` (백틱)':(0xC0,()),'F8':(0x77,()),'F9':(0x78,()),'Ctrl+Alt+B':(0x42,(0x11,0x12))}
def startup_enabled():
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,RUN) as key:
        for name in (NAME,'Bakuri Python Trial','FileFlip'):
            try: winreg.QueryValueEx(key,name); return True
            except FileNotFoundError: pass
    return False
def set_startup(enabled):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,RUN) as key:
        if enabled:
            exe=Path(sys.executable)
            args=[str(exe),'--background'] if getattr(sys,'frozen',False) else [str(exe.with_name('pythonw.exe')),str(Path(__file__).with_name('app.py')),'--background']
            winreg.SetValueEx(key,NAME,0,winreg.REG_SZ,subprocess.list2cmdline(args))
        else:
            try: winreg.DeleteValue(key,NAME)
            except FileNotFoundError: pass
        for legacy in ('Bakuri Python Trial','FileFlip'):
            try: winreg.DeleteValue(key,legacy)
            except FileNotFoundError: pass
class GUIINFO(ctypes.Structure):
    _fields_=[('cbSize',ctypes.c_ulong),('flags',ctypes.c_ulong),('hwndActive',ctypes.c_void_p),('hwndFocus',ctypes.c_void_p),('hwndCapture',ctypes.c_void_p),('hwndMenuOwner',ctypes.c_void_p),('hwndMoveSize',ctypes.c_void_p),('hwndCaret',ctypes.c_void_p),('rcCaret',ctypes.c_long*4)]
class SelectionWatcher(threading.Thread):
    def __init__(self,callback,error,settings,dismiss=lambda:None,popup_key=lambda vk:None):
        super().__init__(daemon=True); self.callback=callback; self.error=error; self.jobs=queue.Queue(maxsize=8); self.pressed=set(); self.intercepted=set(); self.restart=threading.Event()
        self.dismiss=dismiss;self.popup_open=False;self.popup_key=popup_key;self.popup_windows=()
        self.update_settings(settings)
        folder=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'Bakuri'; folder.mkdir(parents=True,exist_ok=True)
        self.log=logging.getLogger('bakuri.hotkey'); self.log.setLevel(logging.INFO)
        if not self.log.handlers:
            from logging.handlers import RotatingFileHandler
            handler=RotatingFileHandler(folder/'hotkey.log',maxBytes=262144,backupCount=1,encoding='utf-8');handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'));self.log.addHandler(handler)
    def update_settings(self,settings):
        self.enabled=settings.value('hotkey_enabled',True,type=bool)
        self.binding=KEYS.get(settings.value('hotkey','` (백틱)'),KEYS['` (백틱)'])
    def request_restart(self): self.restart.set()
    def on_press(self,key):
        import win32gui,win32process
        vk=getattr(key,'vk',None) or getattr(getattr(key,'value',None),'vk',None)
        if vk in self.pressed: return
        self.pressed.add(vk)
        if not self.enabled: return
        target,mods=self.binding
        if vk!=target: return
        if any(bool(ctypes.windll.user32.GetAsyncKeyState(k)&0x8000)!=(k in mods) for k in (0x10,0x11,0x12)): return
        hwnd=win32gui.GetForegroundWindow(); klass=win32gui.GetClassName(hwnd)
        if klass not in ('CabinetWClass','ExploreWClass','Progman','WorkerW'): return
        tid,_=win32process.GetWindowThreadProcessId(hwnd); info=GUIINFO(); info.cbSize=ctypes.sizeof(info)
        if ctypes.windll.user32.GetGUIThreadInfo(tid,ctypes.byref(info)):
            focus=win32gui.GetClassName(info.hwndFocus) if info.hwndFocus else ''
            # Search boxes and inline file-name editors must retain ordinary key input.
            if any(x in focus.lower() for x in ('edit','search','richedit')): return
        try: self.jobs.put_nowait(hwnd)
        except queue.Full: pass
        return True
    def on_release(self,key):
        self.pressed.discard(getattr(key,'vk',None) or getattr(getattr(key,'value',None),'vk',None))
    def filter_event(self,msg,data):
        from types import SimpleNamespace
        suppress=False
        try:
            vk=int(data.vkCode); key=SimpleNamespace(vk=vk)
            popup_key=vk in (0x25,0x26,0x27,0x28,0x0D,0x1B,0x09,0x20)
            if msg in (0x100,0x104) and popup_key and self.popup_open:
                import win32gui
                # Foreground-only check: never enumerate COM/Explorer tabs in the hook.
                if not self.popup_windows or win32gui.GetForegroundWindow() in self.popup_windows:
                    if vk not in self.intercepted:
                        if vk==0x1B:self.dismiss()
                        else:self.popup_key(vk)
                    self.intercepted.add(vk);suppress=True
            elif msg in (0x100,0x104):
                if vk in self.intercepted or self.on_press(key): self.intercepted.add(vk); suppress=True
            elif msg in (0x101,0x105):
                self.on_release(key)
                if vk in self.intercepted: self.intercepted.discard(vk); suppress=True
        except Exception:
            # Never let a disappearing Explorer window terminate the hook thread.
            self.restart.set()
        if suppress: self.listener.suppress_event()
        return True
    def query(self,hwnd,tab,result):
        import pythoncom,win32com.client,win32gui
        pythoncom.CoInitialize()
        try:
            shell=win32com.client.Dispatch('Shell.Application'); paths=[]
            for window in shell.Windows():
                try:
                    if (int(window.HWND)&0xffffffff)!=(hwnd&0xffffffff): continue
                    if tab and browser_hwnd(window) not in (0,hwnd,tab): continue
                    paths=[item.Path for item in window.Document.SelectedItems() if not item.IsFolder]
                    if paths: break
                except Exception: continue
            if not paths and win32gui.GetClassName(hwnd) in ('Progman','WorkerW'):
                desktop=shell.Windows().FindWindowSW(0,0,8,0,1)
                if isinstance(desktop,tuple): desktop=win32com.client.Dispatch(next(v for v in desktop if not isinstance(v,(int,str,type(None)))))
                paths=[item.Path for item in desktop.Document.SelectedItems() if not item.IsFolder]
            result.put((paths,None))
        except Exception as exc: result.put(([],str(exc)))
        finally: pythoncom.CoUninitialize()
    def run(self):
        from pynput import keyboard
        import win32gui
        listener=None; renewed=0; workers=[]
        while True:
            try:
                # A timed-out Windows low-level hook can be removed without notification.
                if listener is None or not listener.is_alive() or self.restart.is_set() or time.monotonic()-renewed>30:
                    if listener is not None:
                        try: listener.stop(); listener.join(timeout=1)
                        except Exception: self.log.exception('Previous listener stopped with error')
                    self.pressed.clear();self.intercepted.clear(); self.restart.clear()
                    listener=keyboard.Listener(win32_event_filter=self.filter_event);self.listener=listener;listener.start();renewed=time.monotonic();self.log.info('Keyboard listener connected')
                try: hwnd=self.jobs.get(timeout=.25)
                except queue.Empty: continue
                if win32gui.GetForegroundWindow()!=hwnd: continue
                tab=active_tab(hwnd);workers=[t for t in workers if t.is_alive()]
                if len(workers)>=2:
                    self.error('탐색기 응답을 기다리고 있습니다. 잠시 후 다시 시도해 주세요.');continue
                result=queue.Queue(maxsize=1);thread=threading.Thread(target=self.query,args=(hwnd,tab,result),daemon=True);workers.append(thread);thread.start()
                try: paths,error=result.get(timeout=3)
                except queue.Empty:
                    self.log.warning('Explorer selection timed out');self.error('탐색기 파일 조회가 지연됐습니다. 다시 시도해 주세요.');continue
                if error:
                    self.log.warning('Explorer selection failed: %s',error);self.error('선택 파일 조회 실패: '+error);continue
                if win32gui.GetForegroundWindow()==hwnd and active_tab(hwnd)==tab: self.callback((paths,hwnd,tab))
            except Exception:
                self.log.exception('Hotkey supervisor recovered');self.restart.set();time.sleep(.25)

def active_tab(hwnd):
    import win32gui
    tabs=[]
    def visit(child,_):
        if win32gui.GetClassName(child)=='ShellTabWindowClass' and win32gui.IsWindowVisible(child): tabs.append(child)
    try: win32gui.EnumChildWindows(hwnd,visit,None)
    except Exception: pass
    return tabs[0] if tabs else 0

def browser_hwnd(window):
    try:
        import pythoncom
        from win32com.shell import shell
        service=window._oleobj_.QueryInterface(pythoncom.IID_IServiceProvider)
        browser=service.QueryService(pythoncom.MakeIID('{4C96BE40-915C-11CF-99D3-00AA004AE837}'),shell.IID_IShellBrowser)
        return browser.GetWindow()
    except Exception: return 0

def source_active(hwnd,tab,popup):
    import win32gui
    return win32gui.IsWindow(hwnd) and win32gui.IsWindowVisible(hwnd) and not win32gui.IsIconic(hwnd) and win32gui.GetForegroundWindow() in (hwnd,popup) and active_tab(hwnd)==tab

def register_hancom(app):
    try:
        module=Path(__file__).with_name('FilePathCheckerModuleExample.dll').resolve()
        for view in (winreg.KEY_WOW64_32KEY,winreg.KEY_WOW64_64KEY):
            with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,r'Software\HNC\HwpAutomation\Modules',0,winreg.KEY_WRITE|view) as key:
                winreg.SetValueEx(key,'BakuriPythonTrial',0,winreg.REG_SZ,str(module))
        return app.RegisterModule('FilePathCheckDLL','BakuriPythonTrial')
    except Exception: return False

def menu_roots():
    from engine import SUPPORTED
    extensions=set(SUPPORTED)
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Classes\SystemFileAssociations') as key:
            index=0
            while True:
                try: extensions.add(winreg.EnumKey(key,index));index+=1
                except OSError:break
    except FileNotFoundError:pass
    return [r'Software\Classes\SystemFileAssociations'+chr(92)+ext+r'\shell' for ext in sorted(extensions)]+[r'Software\Classes\*\shell',r'Software\Classes\AllFilesystemObjects\shell']

def delete_menu_key(path):
    # Only called on our exact verb names, never on file associations/OpenWith.
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,path) as key:
            children=[];index=0
            while True:
                try:children.append(winreg.EnumKey(key,index));index+=1
                except OSError:break
        for child in children:delete_menu_key(path+chr(92)+child)
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER,path)
    except FileNotFoundError:pass

def migrate_menu(enabled):
    # Explicitly disabled settings stay disabled; first launch defaults are handled by the UI.
    register_menu(enabled)
    return enabled

def register_menu(enabled):
    from engine import SUPPORTED
    for root in menu_roots():
        delete_menu_key(root+r'\BakuriConvert')
        delete_menu_key(root+r'\BakuriPythonTrial')
    if enabled:
        executable=Path(sys.executable)
        if not getattr(sys,'frozen',False):executable=executable.with_name('pythonw.exe')
        args=[str(executable)] if getattr(sys,'frozen',False) else [str(executable),str(Path(__file__).with_name('app.py').resolve())]
        for ext in sorted(SUPPORTED):
            path=r'Software\Classes\SystemFileAssociations'+chr(92)+ext+r'\shell\BakuriPythonTrial'
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER,path) as key:
                winreg.SetValueEx(key,'',0,winreg.REG_SZ,'바꾸리 파일 변환')
                winreg.SetValueEx(key,'MultiSelectModel',0,winreg.REG_SZ,'Player')
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER,path+r'\command') as key:
                winreg.SetValueEx(key,'',0,winreg.REG_SZ,subprocess.list2cmdline(args)+' --add-files "%1"')
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,path+r'\command') as key:
                if winreg.QueryValueEx(key,'')[0]!=subprocess.list2cmdline(args)+' --add-files "%1"':
                    raise RuntimeError('우클릭 메뉴 실행 명령 확인에 실패했습니다.')
    ctypes.windll.shell32.SHChangeNotify(0x08000000,0,None,None)

def escape_pressed():
    return bool(ctypes.windll.user32.GetAsyncKeyState(0x1B)&0x8000)

class MouseWatcher(threading.Thread):
    def __init__(self,callback): super().__init__(daemon=True); self.callback=callback
    def run(self):
        from pynput import mouse
        while True:
            listener=None
            try:
                def clicked(x,y,button,pressed):
                    if pressed: self.callback((int(x),int(y)))
                listener=mouse.Listener(on_click=clicked);listener.start()
                while listener.is_alive(): listener.join(timeout=1)
            except Exception: time.sleep(1)
            finally:
                if listener is not None: listener.stop()
