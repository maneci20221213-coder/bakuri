"""CI-only smoke check of the packaged developer edition on native Windows."""
import os,subprocess,sys,time
from pathlib import Path
import win32gui,win32process
exe=Path(sys.argv[1]).resolve();env=dict(os.environ,QT_QPA_PLATFORM='windows')
process=subprocess.Popen([str(exe)],env=env)
try:
 deadline=time.monotonic()+15
 while time.monotonic()<deadline:
  if process.poll() is not None:raise RuntimeError('Developer executable exited before showing its window')
  found=[]
  def visit(hwnd,_):
   if win32process.GetWindowThreadProcessId(hwnd)[1]==process.pid and win32gui.IsWindowVisible(hwnd):
    found.append(win32gui.GetWindowText(hwnd))
  win32gui.EnumWindows(visit,None)
  if any('개발용' in text and '0.15.0' in text for text in found):break
  time.sleep(.2)
 else:raise RuntimeError('Developer window was not found')
 print('Packaged developer window startup verification passed.')
finally:
 process.terminate();process.wait(timeout=10)
