"""Preview and reversible, no-overwrite file renaming within each source folder."""
import json,os,re,uuid
from pathlib import Path

RESERVED={p+n for p in ('COM','LPT') for n in '¹²³'}|{'CON','PRN','AUX','NUL','CLOCK$','CONIN$','CONOUT$'}|{f'{p}{n}' for p in ('COM','LPT') for n in range(1,10)}

def identity(path):
    stat=Path(path).stat();return [stat.st_dev,stat.st_ino,stat.st_size,stat.st_mtime_ns]

def key(path):return str(Path(path).absolute()).casefold()

def invalid(name):
    if not name or name in {'.','..'} or name.endswith((' ','.')):return '끝의 공백·마침표 또는 빈 이름은 사용할 수 없습니다.'
    if re.search(r'[<>:"/\\|?*\x00-\x1f]',name):return '파일명에 사용할 수 없는 문자가 있습니다.'
    if name.split('.')[0].upper() in RESERVED:return 'Windows 예약 이름은 사용할 수 없습니다.'
    if len(name.encode('utf-16-le'))//2>255:return '파일명이 너무 깁니다.'
    return ''

def preview(paths,find='',replace='',prefix='',suffix='',base='',start=1,digits=3,**unused):
    rows=[]
    for index,source in enumerate(paths):
        source=Path(source).absolute();stem=(base+f'_{start+index:0{digits}d}') if base else source.stem
        if find:stem=stem.replace(find,replace)
        name=prefix+stem+suffix+source.suffix;target=source.with_name(name) if not re.search(r'[/\\\x00]',name) else source
        error=invalid(name)
        try:
            if source.is_symlink() or not source.is_file():raise ValueError()
            token=identity(source)
        except (OSError,ValueError):token=None;error='원본 파일을 찾을 수 없거나 바로가기 링크입니다.'
        if len(str(source.parent/name))>240:error='전체 경로가 너무 깁니다. 이름을 줄여 주세요.'
        rows.append(dict(source=str(source),target=str(target),name=name,identity=token,error=error,changed=name!=source.name))
    sources={key(r['source']) for r in rows};counts={}
    for row in rows:counts[key(Path(row['source']).parent/row['name'])]=counts.get(key(Path(row['source']).parent/row['name']),0)+1
    folders={}
    for row in rows:
        if row['error']:continue
        target=Path(row['target']);k=key(target)
        if counts.get(key(Path(row['source']).parent/row['name']),0)>1:row['error']='선택한 파일끼리 이름이 겹칩니다.'
        elif row['changed']:
            try:
                if target.parent not in folders:folders[target.parent]={key(p) for p in target.parent.iterdir()}-sources
                if k in folders[target.parent]:row['error']='같은 폴더에 이미 있는 이름입니다.'
            except OSError:row['error']='폴더를 확인할 수 없습니다.'
    return rows

def write_journal(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True);temp=path.with_suffix('.tmp')
    with temp.open('w',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False);f.flush();os.fsync(f.fileno())
    temp.replace(path)

def move(source,target):
    if os.name=='nt':os.rename(source,target) # Windows rename refuses an existing destination.
    else:
        os.link(source,target,follow_symlinks=False)
        try:os.unlink(source)
        except BaseException:
            os.unlink(target);raise

def apply(rows,journal):
    if not rows or any(r['error'] for r in rows):raise ValueError('미리보기의 오류를 먼저 해결해 주세요.')
    changed=[r for r in rows if r['changed']]
    if not changed:return []
    for row in rows:
        if identity(row['source'])!=row['identity']:raise ValueError('미리보기 이후 파일이 바뀌었습니다. 목록을 다시 확인해 주세요.')
        if Path(row['source']).parent!=Path(row['target']).parent:raise ValueError('다른 폴더로 이동할 수 없습니다.')
    sources={key(r['source']) for r in rows}
    for row in changed:
        if Path(row['target']).exists() and key(row['target']) not in sources:raise ValueError('대상 이름이 이미 사용 중입니다.')
    entries=[dict(original=r['source'],target=r['target'],current=r['source'],identity=r['identity'],temporary=str(Path(r['source']).with_name('.bakuri-rename-'+uuid.uuid4().hex))) for r in changed]
    data=dict(state='working',entries=entries);write_journal(journal,data)
    def relocate(entry,target):
        if identity(entry['current'])!=entry['identity']:raise ValueError('작업 중 원본이 변경되었습니다.')
        move(entry['current'],target);entry['current']=target;write_journal(journal,data)
    try:
        for entry in entries:relocate(entry,entry['temporary'])
        for entry in entries:relocate(entry,entry['target'])
    except Exception as exc:
        try:
            for entry in entries:
                if entry['current']!=entry['temporary']:relocate(entry,entry['temporary'])
            for entry in entries:relocate(entry,entry['original'])
            data['state']='rolled_back';write_journal(journal,data)
        except Exception:
            data['state']='recovery_needed';write_journal(journal,data)
            raise RuntimeError('일부 파일을 되돌리지 못했습니다. 이름 변경 기록을 보존했습니다. 파일을 이동하지 말고 기록을 확인해 주세요.') from exc
        raise RuntimeError('이름을 변경하지 못해 원래 이름으로 되돌렸습니다. 파일이 다른 프로그램에서 사용 중인지 확인해 주세요.') from exc
    data['state']='complete';write_journal(journal,data)
    return entries

def undo(journal):
    data=json.loads(Path(journal).read_text(encoding='utf-8'))
    if data.get('state')!='complete':raise ValueError('되돌릴 수 있는 완료 기록이 없습니다.')
    entries=data['entries'];rows=[];sources={key(e['current']) for e in entries}
    for entry in entries:
        if identity(entry['current'])!=entry['identity']:raise ValueError('변경 후 파일이 수정되거나 교체되어 되돌릴 수 없습니다.')
        target=Path(entry['original'])
        if target.exists() and key(target) not in sources:raise ValueError('원래 이름을 다른 파일이 사용 중입니다.')
        rows.append(dict(source=entry['current'],target=entry['original'],name=target.name,identity=entry['identity'],changed=True,error=''))
    result=apply(rows,journal)
    write_journal(journal,dict(state='undone',entries=result));return result
