"""One synthetic PNG-to-merged-PDF case against the unchanged Python 0.15.0 source."""
import ctypes,json,shutil,sys,time,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
import fitz
from engine import convert
root=Path(sys.argv[1]).resolve();output=root/('python-output-'+uuid.uuid4().hex);output.mkdir()
paths=[]
for source in sorted(root.glob('sample_*.png')):
 target=output/source.name;shutil.copyfile(source,target);paths.append(str(target))
start=time.perf_counter();results=convert(paths,'pdf',merge=True);elapsed=(time.perf_counter()-start)*1000
class Memory(ctypes.Structure):
 _fields_=[('cb',ctypes.c_ulong),('page_faults',ctypes.c_ulong)]+[(n,ctypes.c_size_t) for n in ['peak_working_set','working_set','quota_peak_paged','quota_paged','quota_peak_nonpaged','quota_nonpaged','pagefile','peak_pagefile']]
memory=Memory();memory.cb=ctypes.sizeof(memory)
ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.windll.kernel32.GetCurrentProcess(),ctypes.byref(memory),memory.cb)
data=dict(Engine='Python / PyMuPDF '+fitz.VersionBind,Files=len(paths),ElapsedMs=elapsed,OutputBytes=sum(Path(p).stat().st_size for p in results),PeakWorkingSetBytes=memory.peak_working_set)
(root/'python-benchmark.json').write_text(json.dumps(data,indent=2),encoding='utf-8');print(json.dumps(data))
