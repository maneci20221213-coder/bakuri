using System.Collections.ObjectModel;
using System.ComponentModel;
using System.Runtime.CompilerServices;
using System.Windows.Threading;
using Bakuri.Core;
using Bakuri.Infrastructure;
namespace Bakuri.Desktop;

public class Observable : INotifyPropertyChanged
{
    public event PropertyChangedEventHandler? PropertyChanged;
    protected void Notify([CallerMemberName] string? property = null) => PropertyChanged?.Invoke(this, new(property));
}
public sealed class FileRow(string path) : Observable
{
    public Guid Id { get; } = Guid.NewGuid();
    public string FullPath { get; private set; } = path;
    public string Name => Path.GetFileName(FullPath);
    readonly long bytes = new FileInfo(path).Length;
    public string Size => $"{bytes / 1024d:N1} KB";
    bool selected = true; string next = "", extra = "", state = "";
    public string? ManualName
    {
        get; private set;
    }
    public bool Selected
    {
        get => selected; set
        {
            if (selected != value)
            {
                selected = value;
                Notify();
            }
        }
    }
    public string Extra
    {
        get => extra; set
        {
            if (extra != value)
            {
                extra = value;
                Notify();
            }
        }
    }
    public string NextName
    {
        get => next; set
        {
            ManualName = string.IsNullOrEmpty(value) ? null : value;
            next = value;
            Notify();
        }
    }
    public string State
    {
        get => state; set
        {
            state = value;
            Notify();
        }
    }
    public InputFile Input => new(Id, FullPath);
    public void Preview(string value, string message)
    {
        next = value;
        Notify(nameof(NextName));
        State = message;
    }
    public void Renamed(string path)
    {
        FullPath = path;
        ManualName = null;
        Notify(nameof(Name));
        Notify(nameof(FullPath));
    }
}
public sealed class FormatChoice(OutputFormat value) : Observable
{
    public OutputFormat Value { get; } = value;
    public string Label => Value == OutputFormat.Compress ? "용량 축소" : Value.ToString().ToUpperInvariant();
    bool enabled = true; public bool Enabled
    {
        get => enabled; set
        {
            enabled = value;
            Notify();
        }
    }
}
public sealed class MainViewModel : Observable
{
    public ObservableCollection<FileRow> Files { get; } = [];
    public ObservableCollection<FormatChoice> Formats { get; } = new(Enum.GetValues<OutputFormat>().Select(f => new FormatChoice(f)));
    readonly Dictionary<string, FileRow> index = new(StringComparer.OrdinalIgnoreCase);
    readonly RenamePlanner planner; readonly RenameTransaction renamer; readonly IConversionService conversion;
    readonly DispatcherTimer previewTimer = new() { Interval = TimeSpan.FromMilliseconds(140) };
    bool refreshing, busy; string status = "원본 폴더에 새 파일로 저장 · C# 시험판"; int progress; CancellationTokenSource? cancellation;
    public RenameOptions Options { get; private set; } = new();
    public IReadOnlyList<RenameItem> Plan { get; private set; } = [];
    public JobReport? LastReport
    {
        get; private set;
    }
    public event Action<string>? Completed;
    public event Action? CapabilitiesChanged;
    public bool Busy
    {
        get => busy; private set
        {
            busy = value;
            if (value)
                previewTimer.Stop();
            Notify();
            Notify(nameof(CanEdit));
        }
    }
    public bool CanEdit => !Busy;
    public string Status
    {
        get => status; set
        {
            status = value;
            Notify();
        }
    }
    public int Progress
    {
        get => progress; set
        {
            progress = value;
            Notify();
        }
    }
    public MainViewModel(IConversionService service, IFileStore store, IRenameJournal journal)
    {
        conversion = service;
        planner = new(store);
        renamer = new(store, journal);
        previewTimer.Tick += (_, _) => { previewTimer.Stop(); Refresh(); };
    }
    public void Add(IEnumerable<string> paths)
    {
        if (Busy)
            return;
        foreach (var raw in paths)
        {
            var path = Path.GetFullPath(raw);
            if (!File.Exists(path) || index.ContainsKey(path) || File.GetAttributes(path).HasFlag(FileAttributes.ReparsePoint))
                continue;
            var row = new FileRow(path);
            row.PropertyChanged += (_, e) => { if (!refreshing && e.PropertyName is nameof(FileRow.Selected) or nameof(FileRow.Extra) or nameof(FileRow.NextName)) QueuePreview(); };
            index[path] = row;
            Files.Add(row);
        }
        Refresh();
    }
    public void RemoveChecked()
    {
        if (Busy)
            return;
        foreach (var row in Files.Where(f => f.Selected).ToArray())
        {
            Files.Remove(row);
            index.Remove(row.FullPath);
        }
        Refresh();
    }
    public void Clear()
    {
        Files.Clear();
        index.Clear();
        QueuePreview();
    }
    public void Sort()
    {
        var sorted = Files.OrderBy(f => f.Name, StringComparer.CurrentCultureIgnoreCase).ToArray();
        Files.Clear();
        foreach (var row in sorted)
            Files.Add(row);
        QueuePreview();
    }
    public void Configure(RenameOptions options)
    {
        Options = options;
        QueuePreview();
    }
    public void QueuePreview()
    {
        previewTimer.Stop();
        previewTimer.Start();
    }
    public void Refresh()
    {
        if (refreshing)
            return;
        refreshing = true;
        try
        {
            var selected = Files.Where(f => f.Selected).ToArray();
            foreach (var format in Formats)
                format.Enabled = selected.Length == 0 || selected.All(f => Capabilities.Supports(f.FullPath, format.Value));
            Plan = planner.Preview(selected.Select(f => new FileRule(f.Input, f.Extra, f.ManualName)).ToArray(), Options);
            var byId = Plan.ToDictionary(p => p.Id);
            foreach (var row in Files)
            if (byId.TryGetValue(row.Id, out var plan))
                row.Preview(Path.GetFileName(plan.Target), plan.Error.Length > 0 ? plan.Error : plan.Changed ? "변경 가능" : "변경 없음");
            else
                row.Preview("", "선택 안 됨");
        }
        catch (Exception error) { Status = ConversionService.Friendly(error); Plan = []; }
        finally { refreshing = false; CapabilitiesChanged?.Invoke(); }
    }
    public async Task Convert(OutputFormat format, bool merge, TrialSettings settings, bool protect)
    {
        if (Busy)
            return;
        var files = Files.Where(f => f.Selected).Select(f => f.Input).ToArray();
        if (files.Length == 0)
        {
            Status = "파일을 먼저 추가하고 체크해 주세요.";
            return;
        }
        Busy = true;
        cancellation = new();
        Progress = 0;
        try
        {
            var request = new JobRequest(files, format, merge, settings.Dpi, settings.RetainPercent, protect);
            LastReport = await conversion.RunAsync(request, new Progress<JobProgress>(p => { Progress = p.Percent; Status = p.Stage; }), cancellation.Token);
            Status = LastReport.Summary + (format == OutputFormat.Compress ? $" · {LastReport.SavedBytes / 1048576d:N2} MB 절감" : "");
            Completed?.Invoke(Status);
        }
        catch (OperationCanceledException) { Status = "작업을 중지했습니다."; Completed?.Invoke(Status); }
        catch (Exception error) { ConversionService.Log(error); Status = ConversionService.Friendly(error); Completed?.Invoke(Status); }
        finally { Busy = false; Progress = 0; cancellation.Dispose(); cancellation = null; }
    }
    public async Task Rename(bool undo)
    {
        if (Busy)
            return;
        Refresh();
        var plan = Plan.ToArray();
        Busy = true;
        try
        {
            var moved = await Task.Run(() => undo ? renamer.Undo() : renamer.Apply(plan));
            var mapping = moved.ToDictionary(m => m.Original, m => m.Current, StringComparer.OrdinalIgnoreCase);
            foreach (var row in Files)
            if (mapping.TryGetValue(row.FullPath, out var path))
                row.Renamed(path);
            index.Clear();
            foreach (var row in Files)
                index[row.FullPath] = row;
            Status = $"{moved.Count}개 " + (undo ? "원래 이름으로 복원했습니다." : "이름을 변경했습니다.");
            Completed?.Invoke(Status);
        }
        catch (Exception error) { ConversionService.Log(error); Status = error.Message; }
        finally { Busy = false; Refresh(); }
    }
    public void Stop()
    {
        cancellation?.Cancel();
        Status = "중지 요청 중 · 현재 처리 단계가 끝나면 멈춥니다.";
    }
}
