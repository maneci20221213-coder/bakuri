"""Cooperative job cancellation and monotonic, measured unit progress."""
import threading
from pathlib import Path

class Cancelled(Exception):
    pass

class JobControl:
    def __init__(self,progress=lambda percent,text:None):
        self.cancelled=threading.Event();self.callback=progress;self.percent=0
        self.outputs=[];self.rows=[]
    def cancel(self):self.cancelled.set()
    def check(self):
        if self.cancelled.is_set():raise Cancelled('작업이 중지되었습니다.')
    def update(self,percent,text=''):
        self.check();self.percent=max(self.percent,min(99,int(percent)))
        self.callback(self.percent,text)
    def complete(self):
        self.check();self.percent=100;self.callback(100,'완료')
    def publish(self,source,desired):
        """Reserve a fresh name; remove our partial file if interrupted or failed."""
        source=Path(source);desired=Path(desired);index=0
        while True:
            self.check()
            output=desired if not index else desired.with_name(f'{desired.stem}_{index}{desired.suffix}')
            try:handle=output.open('xb')
            except FileExistsError:index+=1;continue
            try:
                with handle,source.open('rb') as original:
                    while True:
                        self.check();block=original.read(1024*1024)
                        if not block:break
                        handle.write(block)
                self.check()
            except BaseException:
                output.unlink(missing_ok=True);raise
            self.outputs.append(str(output));return str(output)
