using System.Runtime.InteropServices;
using System.Text.Json;
using Bakuri.Core;
namespace Bakuri.Infrastructure;

public static class TrialPaths {
    public static string Root=>Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"BakuriCSharpTrial");
}
public sealed class FileStore : IFileStore {
    [StructLayout(LayoutKind.Sequential)] struct HandleInfo {public uint Attributes; public System.Runtime.InteropServices.ComTypes.FILETIME Creation,Access,Write; public uint Volume,SizeHigh,SizeLow,Links,IndexHigh,IndexLow;}
    [DllImport("kernel32.dll",SetLastError=true)] static extern bool GetFileInformationByHandle(Microsoft.Win32.SafeHandles.SafeFileHandle handle,out HandleInfo info);
    public FileStamp Inspect(string path) {
        var info=new FileInfo(path);if(!info.Exists||info.Attributes.HasFlag(FileAttributes.ReparsePoint))throw new IOException("원본 파일을 찾을 수 없거나 바로가기 링크입니다.");
        using var handle=File.OpenHandle(path,FileMode.Open,FileAccess.Read,FileShare.ReadWrite|FileShare.Delete);
        if(!GetFileInformationByHandle(handle,out var native))throw new IOException("원본 파일 정보를 읽지 못했습니다.");
        return new(info.Length,info.LastWriteTimeUtc.Ticks,$"{native.Volume:x}:{native.IndexHigh:x}:{native.IndexLow:x}");
    }
    public bool Exists(string path)=>File.Exists(path)||Directory.Exists(path);
    public IEnumerable<string> FilesIn(string directory)=>Directory.EnumerateFileSystemEntries(directory);
    public void Move(string source,string target)=>File.Move(source,target,false);
}
public sealed class JsonRenameJournal(string path) : IRenameJournal {
    public RenameHistory? Read() {
        if(!File.Exists(path))return null;var history=JsonSerializer.Deserialize<RenameHistory>(File.ReadAllText(path));
        if(history==null||history.SchemaVersion!=1)throw new IOException("지원하지 않는 이름 변경 기록입니다. 기록을 보존하고 확인해 주세요.");return history;
    }
    public void Write(RenameHistory history)=>AtomicJson.Write(path,history);
}
public static class AtomicJson {
    public static void Write<T>(string path,T value) {
        Directory.CreateDirectory(Path.GetDirectoryName(path)!);var temp=path+"."+Guid.NewGuid().ToString("N")+".tmp";
        try {using(var stream=new FileStream(temp,FileMode.CreateNew,FileAccess.Write,FileShare.None,4096,FileOptions.WriteThrough)){JsonSerializer.Serialize(stream,value);stream.Flush(true);}File.Move(temp,path,true);}
        finally {if(File.Exists(temp))File.Delete(temp);}
    }
}
public sealed record TrialSettings(string Hotkey="Ctrl+Alt+F9",bool Notify=true,int Dpi=150,int RetainPercent=90) {
    public static string SettingsPath=>Path.Combine(TrialPaths.Root,"settings.json");
    public static TrialSettings Load(){try{return JsonSerializer.Deserialize<TrialSettings>(File.ReadAllText(SettingsPath))??new();}catch(Exception e) when(e is IOException or JsonException){return new();}}
    public void Save()=>AtomicJson.Write(SettingsPath,this);
}
public sealed class WorkDirectory : IDisposable {
    public string Path {get;}=System.IO.Path.Combine(System.IO.Path.GetTempPath(),"BakuriCSharp-"+Guid.NewGuid().ToString("N"));
    public WorkDirectory()=>Directory.CreateDirectory(Path);
    public string File(string extension)=>System.IO.Path.Combine(Path,Guid.NewGuid().ToString("N")+"."+extension.TrimStart('.'));
    public void Dispose(){try{Directory.Delete(Path,true);}catch(IOException){}catch(UnauthorizedAccessException){}}
}
public static class OutputPublisher {
    public static string Publish(string staged,string preferred,CancellationToken cancellation) {
        cancellation.ThrowIfCancellationRequested();var directory=Path.GetDirectoryName(preferred)!;
        var pending=Path.Combine(directory,".bakuri-output-"+Guid.NewGuid().ToString("N"));
        try {
            using(var input=File.OpenRead(staged))using(var output=new FileStream(pending,FileMode.CreateNew,FileAccess.Write,FileShare.None,81920,FileOptions.WriteThrough)) {
                var buffer=new byte[81920];int read;while((read=input.Read(buffer))>0){cancellation.ThrowIfCancellationRequested();output.Write(buffer,0,read);}output.Flush(true);
            }
            for(int index=0;index<10000;index++) {
                cancellation.ThrowIfCancellationRequested();var target=index==0?preferred:Path.Combine(directory,$"{Path.GetFileNameWithoutExtension(preferred)} ({index}){Path.GetExtension(preferred)}");
                try {File.Move(pending,target,false);return target;}catch(IOException) when(File.Exists(target)||Directory.Exists(target)){}
            }
            throw new IOException("같은 이름의 파일이 너무 많습니다. 다른 이름을 사용해 주세요.");
        }finally{if(File.Exists(pending))File.Delete(pending);}
    }
}
