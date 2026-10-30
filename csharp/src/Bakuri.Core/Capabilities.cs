namespace Bakuri.Core;

public static class Capabilities {
    public static readonly HashSet<string> Images = new(StringComparer.OrdinalIgnoreCase) { ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".gif", ".webp", ".ico" };
    public static readonly HashSet<string> Sheets = new(StringComparer.OrdinalIgnoreCase) { ".xls", ".xlsx", ".xlsm", ".xlsb", ".xlt", ".xltx", ".xltm", ".csv", ".tsv", ".ods", ".dif", ".slk" };
    public static bool IsImage(string path) => Images.Contains(Path.GetExtension(path));
    public static bool IsHancom(string path) => new[]{".hwp",".hwpx"}.Contains(Path.GetExtension(path),StringComparer.OrdinalIgnoreCase);
    public static bool Supports(string path, OutputFormat format) {
        var ext=Path.GetExtension(path).ToLowerInvariant(); var image=IsImage(path); var sheet=Sheets.Contains(ext);
        bool supported=image || sheet || new[]{".pdf",".doc",".docx",".hwp",".hwpx",".odt",".ppt",".pptx"}.Contains(ext);
        return format switch {
            OutputFormat.Pdf or OutputFormat.Png or OutputFormat.Jpeg => supported,
            OutputFormat.Hwpx => image || new[]{".pdf",".hwp",".hwpx",".odt",".doc",".docx"}.Contains(ext),
            OutputFormat.Docx => IsHancom(path), OutputFormat.Xlsx => sheet,
            OutputFormat.Pptx => image || ext==".pdf", OutputFormat.Compress => image || ext==".pdf", _=>false
        };
    }
    public static bool CanMerge(IEnumerable<string> files, OutputFormat format) {
        var paths=files.ToArray();
        return paths.Length>0 && paths.All(p=>Supports(p,format)) && (format is OutputFormat.Pdf or OutputFormat.Pptx || format==OutputFormat.Hwpx && (paths.All(IsHancom) || paths.All(p=>IsImage(p)||Path.GetExtension(p).Equals(".pdf",StringComparison.OrdinalIgnoreCase))));
    }
    public static string Extension(OutputFormat format)=>format.ToString().ToLowerInvariant();
}
