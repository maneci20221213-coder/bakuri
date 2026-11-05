"""Elapsed-time estimates from reported work, never a simulated percentage."""

import math
import time


class ProgressEstimate:
    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.started = clock()
        self.percent = 1
        self.text = "작업 준비"
        self.remaining = None
        self.sampled_at = self.started

    def update(self, percent, text):
        now = self.clock()
        percent = max(self.percent, min(100, max(1, int(percent))))
        if percent == 100:
            self.remaining = 0
            self.sampled_at = now
        elif percent > self.percent and now - self.started >= 2:
            # Include startup and saving overhead in the measured average.
            self.remaining = (now - self.started) * (100 - percent) / percent
            self.sampled_at = now
        self.percent = percent
        self.text = text

    def label(self, waiting=0):
        elapsed = int(self.clock() - self.started)
        if self.percent == 100:
            timing = "완료"
        elif self.remaining is None:
            timing = "남은 시간 계산 중"
        else:
            # Do not count down to zero while an external converter is still busy.
            seconds = math.ceil(self.remaining - (self.clock() - self.sampled_at))
            if seconds <= 0:
                timing = "예상보다 오래 걸리는 중 · 남은 시간 다시 계산 중"
            else:
                timing = (
                    f"약 {seconds}초 남음"
                    if seconds < 60
                    else f"약 {math.ceil(seconds / 60)}분 남음"
                )
        queued = f" · 대기 {waiting}개" if waiting else ""
        return f"{self.percent}% · {self.text}\n{timing} · 경과 {elapsed}초{queued}"
