"""Elapsed-time estimates from reported work, never a simulated percentage."""

from collections import deque
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
        self.work = None
        self.samples = deque(maxlen=30)

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

    def measure(self, done, total, stage):
        now = self.clock()
        if self.work is None or self.work[2] != stage or done < self.work[0]:
            self.samples.clear()
        if not self.samples or done != self.samples[-1][1]:
            self.samples.append((now, done))
        self.work = (done, total, stage)

    def work_remaining(self):
        done, total, _ = self.work
        if total <= 0:
            return "진행량 확인 중 · 남은 시간 계산 대기"
        if done >= total:
            return "현재 단계 완료 · 다음 단계 준비 중"
        if len(self.samples) < 3 or self.clock() - self.samples[-1][0] > 5:
            return "현재 단계 처리 중 · 남은 시간 계산 중"
        started, count = self.samples[0]
        last, done_count = self.samples[-1]
        duration, completed = last - started, done_count - count
        if duration < 1 or completed <= 0:
            return "처리 속도 측정 중"
        seconds = max(1, math.ceil((total - done) * duration / completed))
        remaining = f"약 {seconds}초" if seconds < 60 else f"약 {math.ceil(seconds / 60)}분"
        return f"이 단계 {remaining} 남음 · 이후 단계 별도 계산"

    def label(self, waiting=0):
        elapsed = int(self.clock() - self.started)
        if self.percent == 100:
            timing = "완료"
        elif self.work is not None:
            timing = self.work_remaining()
        elif self.remaining is None:
            timing = "남은 시간 계산 중"
        else:
            # Do not count down to zero while an external converter is still busy.
            seconds = math.ceil(self.remaining - (self.clock() - self.sampled_at))
            if seconds <= 0 or self.clock() - self.sampled_at > 5:
                timing = "예상보다 오래 걸리는 중 · 남은 시간 다시 계산 중"
            else:
                timing = (
                    f"약 {seconds}초 남음"
                    if seconds < 60
                    else f"약 {math.ceil(seconds / 60)}분 남음"
                )
        queued = f" · 대기 {waiting}개" if waiting else ""
        return f"{self.percent}% · {self.text}\n{timing} · 경과 {elapsed}초{queued}"
