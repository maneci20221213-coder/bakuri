using System.Text;
using System.Text.RegularExpressions;
namespace Bakuri.Core;

public static class Names {
    static readonly HashSet<string> Reserved = new(new[]{"CON","PRN","AUX","NUL","CLOCK$","CONIN$","CONOUT$"}.Concat(new[]{"COM","LPT"}.SelectMany(p=>Enumerable.Range(1,9).Select(n=>p+n))).Concat(new[]{"COM¹","COM²","COM³","LPT¹","LPT²","LPT³"}),StringComparer.OrdinalIgnoreCase);
    public static string Validate(string name) {
        if (string.IsNullOrWhiteSpace(name)||name.EndsWith(' ')||name.EndsWith('.')) return "빈 이름이나 끝의 공백·마침표는 사용할 수 없습니다.";
        if (Regex.IsMatch(name,"[<>:\"/\\\\|?*\\x00-\\x1f]")) return "파일명에 사용할 수 없는 문자가 있습니다.";
        if(Reserved.Contains(name.Split('.')[0]))return "Windows 예약 이름은 사용할 수 없습니다.";
        return name.Length>255 ? "파일명이 너무 깁니다." : "";
    }
    public static string Insert(string stem,string value,InsertPosition position,string marker="",string separator="") {
        if(value.Length==0)return stem;
        int index=position switch {InsertPosition.Before=>0,InsertPosition.After=>stem.Length,_=>stem.IndexOf(marker,StringComparison.Ordinal)};
        if(position is InsertPosition.BeforeMarker or InsertPosition.AfterMarker) {
            if(marker.Length==0)throw new ArgumentException("삽입 기준 문자를 입력해 주세요.");
            if(index<0)throw new ArgumentException("삽입 기준 문자가 이름에 없습니다.");
            if(position==InsertPosition.AfterMarker)index+=marker.Length;
        }
        string left=stem[..index],right=stem[index..];
        return left+(left.Length>0&&separator.Length>0&&!left.EndsWith(separator,StringComparison.Ordinal)?separator:"")+value+(right.Length>0&&separator.Length>0&&!right.StartsWith(separator,StringComparison.Ordinal)?separator:"")+right;
    }
    public static string[] Lines(string text) {
        var normalized=text.Replace("\r\n","\n").Replace('\r','\n');
        if(normalized.EndsWith('\n'))normalized=normalized[..^1];
        var lines=normalized.Split('\n');
        if(lines.Any(l=>l.Contains('\t')))throw new ArgumentException("엑셀에서는 한 열만 복사해 주세요.");
        return lines;
    }
    public static string[] FillDown(string text,int count) {
        var lines=Lines(text);
        if(count<=0||lines.Length>count||lines.All(string.IsNullOrWhiteSpace))throw new ArgumentException("체크한 파일 수와 붙여넣을 문구를 확인해 주세요.");
        string previous="";return Enumerable.Range(0,count).Select(i=>{var value=i<lines.Length?lines[i]:"";if(!string.IsNullOrWhiteSpace(value))previous=value;return previous;}).ToArray();
    }
    public static string Merged(IReadOnlyList<string> paths,string extension) {
        if(paths.Count==1)return Path.ChangeExtension(paths[0],extension);
        var names=paths.Select(p=>Path.GetFileNameWithoutExtension(p).Normalize(NormalizationForm.FormC)).ToArray();
        string shared="";
        // Bounded filenames (255 UTF-16 units) keep this readable search small.
        for(int length=names.Min(n=>n.Length);length>=2&&shared.Length==0;length--)
            for(int i=0;i+length<=names[0].Length;i++) {
                var part=names[0].Substring(i,length).Trim(' ','_','-','.',',','(',')','[',']','{','}','·');
                if(part.Count(char.IsLetterOrDigit)>=2&&names.All(n=>n.Contains(part,StringComparison.Ordinal))){shared=part;break;}
            }
        var stem=shared.Length>0?shared+"_통합본":names[0]+" 등 통합본";
        if(stem.Length>190)stem=stem[..190].TrimEnd(' ','.');
        return Path.Combine(Path.GetDirectoryName(paths[0])!,stem+"."+extension);
    }
}

public sealed class RenamePlanner(IFileStore files) {
    public IReadOnlyList<RenameItem> Preview(IReadOnlyList<FileRule> rules,RenameOptions options) {
        var result=new List<RenameItem>();
        for(int i=0;i<rules.Count;i++) {
            var rule=rules[i];var source=Path.GetFullPath(rule.File.Path);string target=source,error="";FileStamp stamp=new(0,0,"");
            try {
                stamp=files.Inspect(source);string stem=options.Base.Length>0?options.Base:Path.GetFileNameWithoutExtension(source);
                if(options.Find.Length>0)stem=stem.Replace(options.Find,options.Replace,StringComparison.Ordinal);
                stem=Names.Insert(stem,options.PerFile?rule.Extra:"",options.Position,options.Marker);
                if(options.Number)stem=Names.Insert(stem,(checked(options.Start+i)).ToString("D"+Math.Clamp(options.Digits,1,8)),options.NumberPosition,options.NumberMarker,options.Separator);
                stem=Names.Insert(stem,options.PerFile?"":options.Text,options.Position,options.Marker);
                var ext=Path.GetExtension(source);var name=stem+ext;
                if(!string.IsNullOrEmpty(rule.ManualName))name=rule.ManualName.EndsWith(ext,StringComparison.OrdinalIgnoreCase)?rule.ManualName:rule.ManualName+ext;
                error=Names.Validate(name);if(error.Length==0)target=Path.Combine(Path.GetDirectoryName(source)!,name);
                if(target.Length>240)error="전체 경로가 너무 깁니다. 이름을 줄여 주세요.";
            } catch(Exception e) when(e is IOException or UnauthorizedAccessException or ArgumentException or OverflowException) {error=e is ArgumentException?e.Message:"원본 파일 또는 이름 설정을 확인해 주세요.";}
            result.Add(new(rule.File.Id,source,target,stamp,error));
        }
        var sources=result.Select(r=>r.Source).ToHashSet(StringComparer.OrdinalIgnoreCase);
        var counts=result.GroupBy(r=>r.Target,StringComparer.OrdinalIgnoreCase).ToDictionary(g=>g.Key,g=>g.Count(),StringComparer.OrdinalIgnoreCase);
        var occupied=result.Select(r=>Path.GetDirectoryName(r.Source)!).Distinct(StringComparer.OrdinalIgnoreCase).ToDictionary(d=>d,d=>files.FilesIn(d).Where(p=>!sources.Contains(p)).ToHashSet(StringComparer.OrdinalIgnoreCase),StringComparer.OrdinalIgnoreCase);
        return result.Select(r=>r.Error.Length>0?r:r with{Error=counts[r.Target]>1?"선택한 파일끼리 이름이 겹칩니다.":occupied[Path.GetDirectoryName(r.Source)!].Contains(r.Target)?"같은 폴더에 이미 있는 이름입니다.":""}).ToArray();
    }
}
