namespace Bakuri.Core;

/// <summary>Same-directory, no-overwrite, two-phase moves. Durable progress stays available after a crash.</summary>
public sealed class RenameTransaction(IFileStore files, IRenameJournal journal) {
    public RenameHistory? History=>journal.Read();
    public IReadOnlyList<RenameMove> Apply(IReadOnlyList<RenameItem> plan,bool isUndo=false) {
        if(!isUndo&&History?.State is "working" or "recovery_needed")throw new InvalidOperationException("미완료 이름 변경 기록이 있습니다. 파일을 이동하지 말고 기록을 확인해 주세요.");
        if(plan.Any(p=>p.Error.Length>0))throw new InvalidOperationException("미리보기의 오류를 먼저 해결해 주세요.");
        if(plan.Any(p=>Names.Validate(Path.GetFileName(p.Target)).Length>0)||plan.Select(p=>p.Target).Distinct(StringComparer.OrdinalIgnoreCase).Count()!=plan.Count)throw new IOException("변경할 이름이 올바르지 않거나 서로 겹칩니다.");
        var sources=plan.Select(p=>p.Source).ToHashSet(StringComparer.OrdinalIgnoreCase);
        foreach(var p in plan) {
            if(files.Inspect(p.Source)!=p.Stamp)throw new IOException("미리보기 이후 원본 파일이 바뀌었습니다. 다시 확인해 주세요.");
            if(!string.Equals(Path.GetDirectoryName(p.Source),Path.GetDirectoryName(p.Target),StringComparison.OrdinalIgnoreCase))throw new IOException("다른 폴더로 이동할 수 없습니다.");
            if(files.Exists(p.Target)&&!sources.Contains(p.Target))throw new IOException("대상 이름을 다른 파일이 사용 중입니다.");
        }
        var moves=plan.Where(p=>p.Changed).Select(p=>new RenameMove(p.Source,p.Target,Path.Combine(Path.GetDirectoryName(p.Source)!,".bakuri-csharp-"+Guid.NewGuid().ToString("N")),p.Source,p.Stamp)).ToList();
        if(moves.Count==0)return moves;
        void Save(string state)=>journal.Write(new(state,moves.ToArray()));
        void Move(int index,string target) {
            var entry=moves[index];if(files.Inspect(entry.Current)!=entry.Stamp)throw new IOException("작업 중 원본 파일이 바뀌었습니다.");
            files.Move(entry.Current,target);moves[index]=entry with{Current=target};Save("working");
        }
        Save("working");
        try {
            for(int i=0;i<moves.Count;i++)Move(i,moves[i].Temporary);
            for(int i=0;i<moves.Count;i++)Move(i,moves[i].Target);
        }catch(Exception error) {
            try {
                for(int i=0;i<moves.Count;i++)if(moves[i].Current!=moves[i].Temporary)Move(i,moves[i].Temporary);
                for(int i=0;i<moves.Count;i++)Move(i,moves[i].Original);
                Save("rolled_back");
            }catch {Save("recovery_needed");throw new IOException("일부 파일을 되돌리지 못했습니다. 이름 변경 기록을 보존했습니다. 파일을 옮기지 말고 기록을 확인해 주세요.",error);}
            throw new IOException("이름을 변경하지 못해 원래 이름으로 되돌렸습니다. 파일이 사용 중인지 확인해 주세요.",error);
        }
        Save(isUndo?"undone":"complete");return moves;
    }
    public IReadOnlyList<RenameMove> Undo() {
        var history=History;if(history?.State!="complete")throw new InvalidOperationException("되돌릴 완료 기록이 없습니다.");
        return Apply(history.Moves.Select(m=>new RenameItem(Guid.NewGuid(),m.Current,m.Original,m.Stamp,"")).ToArray(),true);
    }
}
