"""Explorer selection and keyboard events run outside the Qt UI thread."""
import sys, threading, ctypes, subprocess, winreg, queue, time, logging, os
from user_messages import friendly_error
from pathlib import Path
from build_channel import DEFAULT_HOTKEY
RUN=r'Software\Microsoft\Windows\CurrentVersion\Run'
NAME='Bakuri'
DEVELOPMENT_NAME='BakuriDevelopment'
KEYS={'` (백틱)':(0xC0,()),'F8':(0x77,()),'F9':(0x78,()),'Ctrl+Alt+B':(0x42,(0x11,0x12))}
def startup_enabled(*, development=False):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,RUN) as key:
        names = (DEVELOPMENT_NAME,) if development else (NAME, 'Bakuri Python Trial', 'FileFlip')
        for name in names:
            try: winreg.QueryValueEx(key,name); return True
            except FileNotFoundError: pass
    return False
def set_startup(enabled, *, development=False):
    name = DEVELOPMENT_NAME if development else NAME
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER,RUN) as key:
        if enabled:
            exe=Path(sys.executable)
            args=[str(exe),'--background'] if getattr(sys,'frozen',False) else [str(exe.with_name('pythonw.exe')),str(Path(__file__).with_name('app.py')),'--background']
            winreg.SetValueEx(key,name,0,winreg.REG_SZ,subprocess.list2cmdline(args))
        else:
            try: winreg.DeleteValue(key,name)
            except FileNotFoundError: pass
        for legacy in (() if development else ('Bakuri Python Trial','FileFlip')):
            try: winreg.DeleteValue(key,legacy)
            except FileNotFoundError: pass
class GUIINFO(ctypes.Structure):
    _fields_=[('cbSize',ctypes.c_ulong),('flags',ctypes.c_ulong),('hwndActive',ctypes.c_void_p),('hwndFocus',ctypes.c_void_p),('hwndCapture',ctypes.c_void_p),('hwndMenuOwner',ctypes.c_void_p),('hwndMoveSize',ctypes.c_void_p),('hwndCaret',ctypes.c_void_p),('rcCaret',ctypes.c_long*4)]
class SelectionWatcher(threading.Thread):
    def __init__(self,callback,error,settings,dismiss=lambda:None,popup_key=lambda vk:None):
        super().__init__(daemon=True); self.callback=callback; self.error=error; self.jobs=queue.Queue(maxsize=8); self.pressed=set(); self.intercepted=set(); self.key_window=None; self.restart=threading.Event()
        self.dismiss=dismiss;self.popup_open=False;self.popup_key=popup_key;self.popup_windows=()
        self.update_settings(settings)
        folder=Path(os.environ.get('LOCALAPPDATA',str(Path.home())))/'Bakuri'; folder.mkdir(parents=True,exist_ok=True)
        self.log=logging.getLogger('bakuri.hotkey'); self.log.setLevel(logging.INFO)
        if not self.log.handlers:
            from logging.handlers import RotatingFileHandler
            handler=RotatingFileHandler(folder/'hotkey.log',maxBytes=262144,backupCount=1,encoding='utf-8');handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'));self.log.addHandler(handler)
    def update_settings(self, settings):
        self.enabled = settings.value('hotkey_enabled', True, type=bool)
        self.binding = KEYS.get(settings.value('hotkey', DEFAULT_HOTKEY), KEYS[DEFAULT_HOTKEY])
        try:
            vk, *mods = map(int, str(settings.value('hotkey_binding', '')).split(','))
            if 0 < vk <= 0xFE and set(mods) <= {0x10, 0x11, 0x12, 0x5B}:
                self.binding = vk, tuple(mods)
        except ValueError:
            pass

    def modifiers_match(self, mods):
        state = ctypes.windll.user32.GetAsyncKeyState
        pressed = {key for key in (0x10, 0x11, 0x12) if state(key) & 0x8000}
        if state(0x5B) & 0x8000 or state(0x5C) & 0x8000:
            pressed.add(0x5B)
        return pressed == set(mods)

    def on_press(self,key):
        import win32gui,win32process
        vk=getattr(key,'vk',None) or getattr(getattr(key,'value',None),'vk',None)
        if vk in self.pressed: return
        self.pressed.add(vk)
        if not self.enabled: return
        target,mods=self.binding
        if vk!=target: return
        if not self.modifiers_match(mods): return
        hwnd=win32gui.GetForegroundWindow()
        if self.popup_open and (not self.popup_windows or hwnd in self.popup_windows):
            self.dismiss();return True
        klass=win32gui.GetClassName(hwnd)
        if klass not in ('CabinetWClass','ExploreWClass','Progman','WorkerW'): return
        tid,_=win32process.GetWindowThreadProcessId(hwnd); info=GUIINFO(); info.cbSize=ctypes.sizeof(info)
        if ctypes.windll.user32.GetGUIThreadInfo(tid,ctypes.byref(info)) and info.hwndActive==hwnd:
            focus=win32gui.GetClassName(info.hwndFocus) if info.hwndFocus else ''
            # Search boxes and inline file-name editors must retain ordinary key input.
            if focus.lower() in {'edit', 'searchbox', 'searchboxedit'} or focus.lower().startswith('richedit'): return
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
            if msg in (0x100,0x104):
                import win32gui

                hwnd = win32gui.GetForegroundWindow()
                if self.key_window != hwnd:
                    # A key-up can be lost while switching windows or desktops.
                    if not (self.popup_open and hwnd in self.popup_windows and self.key_window in self.popup_windows):
                        self.pressed.clear()
                        self.intercepted.clear()
                    self.key_window = hwnd
                if vk in self.intercepted:
                    suppress = True
                elif (
                    self.enabled and vk == self.binding[0] and self.on_press(key)
                ):
                    self.intercepted.add(vk)
                    suppress = True
                elif popup_key and self.popup_open and (
                    not self.popup_windows or hwnd in self.popup_windows
                ):
                    if vk == 0x1B:
                        self.dismiss()
                    else:
                        self.popup_key(vk)
                    self.intercepted.add(vk)
                    suppress = True
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
                    paths=selected_file_paths(window)
                    if paths: break
                except Exception: continue
            if not paths and win32gui.GetClassName(hwnd) in ('Progman','WorkerW'):
                desktop=shell.Windows().FindWindowSW(0,0,8,0,1)
                if isinstance(desktop,tuple): desktop=win32com.client.Dispatch(next(v for v in desktop if not isinstance(v,(int,str,type(None)))))
                paths=selected_file_paths(desktop)
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
                    self.log.warning('Explorer selection failed: %s',error);self.error(friendly_error(error,'selection'));continue
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

def shell_browser(window):
    import pythoncom
    from win32com.shell import shell

    service = window._oleobj_.QueryInterface(pythoncom.IID_IServiceProvider)
    return service.QueryService(
        pythoncom.MakeIID('{4C96BE40-915C-11CF-99D3-00AA004AE837}'), shell.IID_IShellBrowser
    )


def browser_hwnd(window):
    try:
        return shell_browser(window).GetWindow()
    except Exception:
        return 0


def drop_paths(handle):
    from ctypes import wintypes

    query = ctypes.windll.shell32.DragQueryFileW
    query.argtypes = (wintypes.HANDLE, wintypes.UINT, wintypes.LPWSTR, wintypes.UINT)
    query.restype = wintypes.UINT
    paths = []
    for index in range(query(handle, 0xFFFFFFFF, None, 0)):
        size = query(handle, index, None, 0) + 1
        name = ctypes.create_unicode_buffer(size)
        if query(handle, index, name, size):
            paths.append(name.value)
    return paths


def selected_file_paths(window):
    try:
        import pythoncom
        import win32con

        view = shell_browser(window).QueryActiveShellView()
        # SVGIO_SELECTION | SVGIO_FLAG_VIEWORDER; pywin32 takes a signed int.
        flags = ctypes.c_int32(0x80000001).value
        data = view.GetItemObject(flags, pythoncom.IID_IDataObject)
        medium = data.GetData(
            (win32con.CF_HDROP, None, pythoncom.DVASPECT_CONTENT, -1, pythoncom.TYMED_HGLOBAL)
        )
        paths = drop_paths(medium.data_handle)
        if paths:
            return [path for path in paths if not Path(path).is_dir()]
    except Exception:
        # Some Explorer views do not expose a file-drop selection through COM.
        pass
    return [item.Path for item in window.Document.SelectedItems() if not item.IsFolder]


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
    from bakuri.domain.formats import SUPPORTED
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

def register_menu(enabled, *, development=False):
    from bakuri.domain.formats import SUPPORTED
    verb = r'\BakuriDevelopment' if development else r'\BakuriPythonTrial'
    for root in menu_roots():
        if not development:
            delete_menu_key(root+r'\BakuriConvert')
        delete_menu_key(root+verb)
    if enabled:
        executable=Path(sys.executable)
        if not getattr(sys,'frozen',False):executable=executable.with_name('pythonw.exe')
        args=[str(executable)] if getattr(sys,'frozen',False) else [str(executable),str(Path(__file__).with_name('app.py').resolve())]
        for ext in sorted(SUPPORTED):
            path=r'Software\Classes\SystemFileAssociations'+chr(92)+ext+r'\shell'+verb
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER,path) as key:
                winreg.SetValueEx(key,'',0,winreg.REG_SZ,'바꾸리 개발판 파일 변환' if development else '바꾸리 파일 변환')
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


def initialize_startup(settings,first_run=True):
    """Enable once by default; preserve explicit choices on subsequent runs."""
    if not settings.contains('startup_enabled'):
        enabled=True if first_run else startup_enabled()
        set_startup(enabled)
        settings.setValue('startup_enabled',enabled)
        settings.sync()
    elif startup_enabled():
        # Refresh an existing registration after portable-directory moves.
        set_startup(True)


def apply_install_options(arguments):
    """Apply the installer's explicit choice, before single-instance forwarding."""
    choice=next((arg.rsplit('=',1)[1] for arg in arguments
                 if arg in ('--desktop-shortcut=0','--desktop-shortcut=1')),None)
    if choice is None or not getattr(sys,'frozen',False):return
    import pythoncom
    from win32com.shell import shell,shellcon
    pythoncom.CoInitialize()
    try:
        # Prefer Velopack's stable root launcher; current also survives updates.
        root=Path(sys.executable).parent.parent
        launcher=next((path for path in (root/'BakuriFileConverter.exe',root/'바꾸리.exe') if path.is_file()),Path(sys.executable))
        if not (root/'Update.exe').is_file() or not launcher.is_file():
            raise RuntimeError('설치된 바꾸리를 찾지 못했습니다.')
        desktop=Path(shell.SHGetSpecialFolderPath(0,shellcon.CSIDL_DESKTOPDIRECTORY,False))
        link=desktop/'바꾸리.lnk'
        # Use the typed shell interface: WScript's late-bound shortcut object
        # cannot reliably expose writable properties in the frozen application.
        shortcut=pythoncom.CoCreateInstance(shell.CLSID_ShellLink,None,
                                           pythoncom.CLSCTX_INPROC_SERVER,shell.IID_IShellLink)
        persist=shortcut.QueryInterface(pythoncom.IID_IPersistFile)
        if choice=='1':
            shortcut.SetPath(str(launcher))
            shortcut.SetWorkingDirectory(str(root))
            shortcut.SetDescription('바꾸리 파일 변환기')
            shortcut.SetIconLocation(str(launcher),0)
            persist.Save(str(link),0)
        elif link.exists():
            persist.Load(str(link))
            target=Path(shortcut.GetPath(0)[0])
            if target.resolve() in {launcher.resolve(),Path(sys.executable).resolve()}:
                link.unlink()
    except Exception as exc:
        ctypes.windll.user32.MessageBoxW(None,friendly_error(exc,'settings'),'바로가기 설정',48)
    finally:
        pythoncom.CoUninitialize()
