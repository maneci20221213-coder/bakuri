namespace Bakuri.Core;

public enum OutputFormat
{
    Pdf, Png, Jpeg, Hwpx, Docx, Pptx, Xlsx, Compress
}
public enum InsertPosition
{
    Before, After, BeforeMarker, AfterMarker
}
public enum FileOutcome
{
    Saved, Skipped, Failed
}
public sealed record InputFile(Guid Id, string Path);
public sealed record FileStamp(long Length, long ModifiedTicks, string Identity);
public sealed record RenameItem(Guid Id, string Source, string Target, FileStamp Stamp, string Error)
{
    public bool Changed => !string.Equals(Source, Target, StringComparison.Ordinal);
}
public sealed record RenameOptions(string Find = "", string Replace = "", string Base = "", string Text = "",
    InsertPosition Position = InsertPosition.Before, string Marker = "", bool PerFile = false,
    bool Number = false, int Start = 1, int Digits = 1, string Separator = "_",
    InsertPosition NumberPosition = InsertPosition.After, string NumberMarker = "");
public sealed record FileRule(InputFile File, string Extra = "", string? ManualName = null);
public sealed record JobRequest(IReadOnlyList<InputFile> Files, OutputFormat Format, bool Merge = false,
    int Dpi = 150, int RetainPercent = 90, bool ProtectText = false);
public sealed record JobProgress(int Percent, string Stage);
public sealed record FileResult(string Source, string? Output, FileOutcome Outcome, long Before, long After, string Message);
public sealed record JobReport(IReadOnlyList<FileResult> Files, bool Cancelled, TimeSpan Elapsed)
{
    public long SavedBytes => Files.Where(f => f.Outcome == FileOutcome.Saved).Sum(f => Math.Max(0, f.Before - f.After));
    public string Summary => $"저장 {Files.Count(f => f.Outcome == FileOutcome.Saved)}개 · 건너뜀 {Files.Count(f => f.Outcome == FileOutcome.Skipped)}개 · 실패 {Files.Count(f => f.Outcome == FileOutcome.Failed)}개" + (Cancelled ? " · 작업 중지" : "");
}
public interface IFileStore
{
    FileStamp Inspect(string path);
    bool Exists(string path);
    IEnumerable<string> FilesIn(string directory);
    void Move(string source, string target);
}
public interface IConversionService
{
    Task<JobReport> RunAsync(JobRequest request, IProgress<JobProgress> progress, CancellationToken cancellation);
}
public sealed record RenameMove(string Original, string Target, string Temporary, string Current, FileStamp Stamp);
public sealed record RenameHistory(string State, IReadOnlyList<RenameMove> Moves, int SchemaVersion = 1);
public interface IRenameJournal
{
    RenameHistory? Read(); void Write(RenameHistory history);
}
