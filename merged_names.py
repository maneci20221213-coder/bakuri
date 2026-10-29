from pathlib import Path
import unicodedata

def merged_path(files,extension):
    files=[Path(p) for p in files]
    if len(files)==1:return files[0].with_suffix('.'+extension)
    names=[unicodedata.normalize('NFC',p.stem) for p in files]
    low,high=1,min(map(len,names));common=set()
    while low<=high:
        length=(low+high)//2
        candidates={names[0][i:i+length] for i in range(len(names[0])-length+1)}
        for name in names[1:]:
            candidates.intersection_update(name[i:i+length] for i in range(len(name)-length+1))
            if not candidates:break
        if candidates:common=candidates;low=length+1
        else:high=length-1
    trim=' _-.,()[]{}·'
    candidates=[n.strip(trim) for n in common]
    candidates=[n for n in candidates if sum(c.isalnum() for c in n)>=2]
    if candidates:
        shared=min(candidates,key=lambda n:(-len(n),names[0].find(n),n))
        stem=shared[:180].rstrip(trim)+'_통합본'
    else:stem=names[0][:180].rstrip(' .')+' 등 통합본'
    return files[0].with_name(stem+'.'+extension)
