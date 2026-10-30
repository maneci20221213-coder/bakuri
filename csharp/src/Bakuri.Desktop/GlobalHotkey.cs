using System.Runtime.InteropServices;
using System.Windows;
using System.Windows.Interop;
using Bakuri.Infrastructure;
namespace Bakuri.Desktop;

public sealed class GlobalHotkey : IDisposable {
    const int Id=0xBA01;readonly IntPtr hwnd;readonly HwndSource source;readonly Action action;string? currentKey;
    [DllImport("user32.dll",SetLastError=true)] static extern bool RegisterHotKey(IntPtr window,int id,uint modifiers,uint key);
    [DllImport("user32.dll")] static extern bool UnregisterHotKey(IntPtr window,int id);
    public GlobalHotkey(Window window,Action callback){hwnd=new WindowInteropHelper(window).Handle;source=HwndSource.FromHwnd(hwnd);action=callback;source.AddHook(Message);}
    public void Register(string key) {
        UnregisterHotKey(hwnd,Id);(uint mod,uint vk)=key switch{"F9"=>(0u,0x78u),"F8"=>(0u,0x77u),"Ctrl+Alt+B"=>(3u,0x42u),_=>(3u,0x78u)};
        if(!RegisterHotKey(hwnd,Id,mod|0x4000,vk)) {
            var previous=currentKey;currentKey=null;if(previous!=null)Register(previous);
            throw new IOException("이 단축키를 다른 프로그램에서 사용 중입니다. 다른 키를 선택해 주세요.");
        }
        currentKey=key;
    }
    IntPtr Message(IntPtr handle,int message,IntPtr wParam,IntPtr lParam,ref bool handled){if(message==0x0312&&wParam.ToInt32()==Id){handled=true;action();}return IntPtr.Zero;}
    public void Dispose(){UnregisterHotKey(hwnd,Id);source.RemoveHook(Message);}
}
public static class ExplorerSelection {
    [DllImport("user32.dll")] static extern IntPtr GetForegroundWindow();
    [DllImport("user32.dll",CharSet=CharSet.Unicode)] static extern int GetClassName(IntPtr window,System.Text.StringBuilder name,int max);
    public static async Task<IReadOnlyList<string>> ReadAsync() {
        var hwnd=GetForegroundWindow();var klass=new System.Text.StringBuilder(256);GetClassName(hwnd,klass,256);
        if(!new[]{"CabinetWClass","ExploreWClass","Progman","WorkerW"}.Contains(klass.ToString()))return [];
        var work=new StaRunner().Run<IReadOnlyList<string>>(()=> {
            dynamic shell=Activator.CreateInstance(Type.GetTypeFromProgID("Shell.Application")!)!;
            try {
                var paths=new List<string>();dynamic windows=shell.Windows();
                foreach(dynamic window in windows) {
                    try {if((long)window.HWND!=hwnd.ToInt64())continue;foreach(dynamic item in window.Document.SelectedItems())if(!(bool)item.IsFolder&&File.Exists((string)item.Path))paths.Add((string)item.Path);if(paths.Count>0)break;}catch(COMException){}
                }
                if(paths.Count==0&&klass.ToString() is "Progman" or "WorkerW") {
                    dynamic desktop=windows.FindWindowSW(0,0,8,out int _,1);foreach(dynamic item in desktop.Document.SelectedItems())if(!(bool)item.IsFolder&&File.Exists((string)item.Path))paths.Add((string)item.Path);
                }
                return paths.Distinct(StringComparer.OrdinalIgnoreCase).ToArray();
            }finally{Marshal.FinalReleaseComObject(shell);}
        });
        if(await Task.WhenAny(work,Task.Delay(3000))!=work)throw new IOException("탐색기 응답이 지연됩니다. 다시 시도해 주세요.");
        var result=await work;return GetForegroundWindow()==hwnd?result:[];
    }
}
