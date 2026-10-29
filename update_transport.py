"""HTTPS downloads using Windows Internet settings; never disables TLS checks."""
import ctypes,sys,time
from urllib.parse import urlparse,urljoin
from urllib.request import Request,urlopen

def validate_url(url):
    parsed=urlparse(url)
    host=(parsed.hostname or '').lower()
    if parsed.scheme!='https' or parsed.username or parsed.password or parsed.port not in (None,443):
        raise ValueError('Update downloads require HTTPS without credentials')
    if host!='github.com' and host!='githubusercontent.com' and not host.endswith('.githubusercontent.com'):
        raise ValueError('Unexpected update download host')
    return url

def download_to(url,path,limit,timeout=30):
    validate_url(url)
    try:
        if sys.platform=='win32':_windows_download(url,path,limit,timeout)
        else:
            with urlopen(Request(url,headers={'User-Agent':'Bakuri-Updater','Accept-Encoding':'identity'}),timeout=timeout) as response:
                validate_url(response.geturl())
                with open(path,'wb') as output:
                    size=0;deadline=time.monotonic()+600
                    while True:
                        chunk=response.read(131072)
                        if not chunk:break
                        size+=len(chunk)
                        if size>limit or time.monotonic()>deadline:raise OSError('Update download exceeded its limit')
                        output.write(chunk)
    except Exception:
        from pathlib import Path
        Path(path).unlink(missing_ok=True)
        raise

def _windows_download(url,path,limit,timeout):
    from ctypes import wintypes as w
    api=ctypes.WinDLL('wininet',use_last_error=True)
    api.InternetOpenW.argtypes=[w.LPCWSTR,w.DWORD,w.LPCWSTR,w.LPCWSTR,w.DWORD];api.InternetOpenW.restype=w.HANDLE
    api.InternetOpenUrlW.argtypes=[w.HANDLE,w.LPCWSTR,w.LPCWSTR,w.DWORD,w.DWORD,ctypes.c_size_t];api.InternetOpenUrlW.restype=w.HANDLE
    api.InternetSetOptionW.argtypes=[w.HANDLE,w.DWORD,w.LPVOID,w.DWORD];api.InternetSetOptionW.restype=w.BOOL
    api.HttpQueryInfoW.argtypes=[w.HANDLE,w.DWORD,w.LPVOID,ctypes.POINTER(w.DWORD),ctypes.POINTER(w.DWORD)];api.HttpQueryInfoW.restype=w.BOOL
    api.InternetReadFile.argtypes=[w.HANDLE,w.LPVOID,w.DWORD,ctypes.POINTER(w.DWORD)];api.InternetReadFile.restype=w.BOOL
    api.InternetCloseHandle.argtypes=[w.HANDLE];api.InternetCloseHandle.restype=w.BOOL
    # PRECONFIG uses the user's Windows Internet/proxy configuration.
    session=api.InternetOpenW('Bakuri-Updater',0,None,None,0)
    if not session:raise ctypes.WinError(ctypes.get_last_error())
    try:
        milliseconds=w.DWORD(timeout*1000)
        for option in (2,5,6):
            if not api.InternetSetOptionW(session,option,ctypes.byref(milliseconds),ctypes.sizeof(milliseconds)):
                raise ctypes.WinError(ctypes.get_last_error())
        for redirect in range(6):
            validate_url(url)
            # RELOAD | NO_CACHE_WRITE | NO_AUTO_REDIRECT | NO_UI | NO_COOKIES.
            request=api.InternetOpenUrlW(session,url,None,0,0x84280200,0)
            if not request:raise ctypes.WinError(ctypes.get_last_error())
            try:
                status=w.DWORD();length=w.DWORD(ctypes.sizeof(status))
                if not api.HttpQueryInfoW(request,19|0x20000000,ctypes.byref(status),ctypes.byref(length),None):
                    raise ctypes.WinError(ctypes.get_last_error())
                if status.value in (301,302,303,307,308):
                    location=ctypes.create_unicode_buffer(8192);length=w.DWORD(ctypes.sizeof(location))
                    if not api.HttpQueryInfoW(request,33,location,ctypes.byref(length),None):
                        raise ctypes.WinError(ctypes.get_last_error())
                    url=urljoin(url,location.value);continue
                if status.value!=200:raise OSError('Update HTTP status '+str(status.value))
                buffer=ctypes.create_string_buffer(131072);read=w.DWORD();size=0;deadline=time.monotonic()+600
                with open(path,'wb') as output:
                    while True:
                        if not api.InternetReadFile(request,buffer,len(buffer),ctypes.byref(read)):
                            raise ctypes.WinError(ctypes.get_last_error())
                        if not read.value:break
                        size+=read.value
                        if size>limit or time.monotonic()>deadline:raise OSError('Update download exceeded its limit')
                        output.write(buffer.raw[:read.value])
                return
            finally:api.InternetCloseHandle(request)
        raise OSError('Too many update redirects')
    finally:api.InternetCloseHandle(session)
