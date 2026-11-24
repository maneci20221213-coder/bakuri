"""Cooperative job cancellation and monotonic, measured unit progress."""

import threading
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory


class Cancelled(Exception):
    pass


class JobControl:
    def __init__(
        self, progress=lambda percent, text: None, measurement=lambda done, total, stage: None
    ):
        self.cancelled = threading.Event()
        self.callback = progress
        self.measurement = measurement
        self.percent = 0
        self.outputs = []
        self.rows = []
        self.notes = []
        self._location = None

    def cancel(self):
        self.cancelled.set()

    def check(self):
        if self.cancelled.is_set():
            raise Cancelled("작업이 중지되었습니다.")

    def update(self, percent, text=""):
        self.check()
        self.percent = max(self.percent, min(99, int(percent)))
        self.callback(self.percent, text)

    def measure_units(self, done, total, stage):
        """Report observable work separately from the overall weighted percentage."""
        self.check()
        self.measurement(int(done), int(total), stage)

    def complete(self):
        self.check()
        if self._location is not None:
            self._location.flush(self.check)
        self.percent = 100
        self.callback(100, "완료")

    @contextmanager
    def save_to(self, location, first_folder):
        if location.mode == "source":
            yield
            return
        publisher = _OutputLocation(self, location, Path(first_folder))
        self._location = publisher
        try:
            yield
            publisher.flush(self.check)
        except Exception:
            try:
                # The first result was already generated when a later item failed or stopped.
                publisher.flush(lambda: None)
            except OSError:
                self.notes.append("먼저 끝난 파일의 저장 위치를 확인해 주세요.")
            raise
        finally:
            self._location = None
            publisher.close()

    def publish(self, source, desired):
        """Reserve a fresh name; remove our partial file if interrupted or failed."""
        if self._location is not None:
            return self._location.publish(source, Path(desired))
        return self._publish(source, desired, self.check)

    def _publish(self, source, desired, check):
        output = self._copy(source, desired, check)
        self.outputs.append(str(output))
        return str(output)

    @staticmethod
    def _copy(source, desired, check):
        source = Path(source)
        desired = Path(desired)
        index = 0
        while True:
            check()
            output = (
                desired
                if not index
                else desired.with_name(f"{desired.stem}_{index}{desired.suffix}")
            )
            try:
                handle = output.open("xb")
            except FileExistsError:
                index += 1
                continue
            try:
                with handle, source.open("rb") as original:
                    while True:
                        check()
                        block = original.read(1024 * 1024)
                        if not block:
                            break
                        handle.write(block)
                check()
            except BaseException:
                output.unlink(missing_ok=True)
                raise
            return output


class _OutputLocation:
    def __init__(self, control, location, first_folder):
        self.control = control
        self.location = location
        self.first_folder = first_folder
        self.group = None
        self.staging = None
        self.pending = None
        self.first_result = None

    def publish(self, source, desired):
        check = self.control.check
        check()
        if self.location.mode == "custom":
            folder = Path(self.location.folder)
        elif self.location.mode == "subfolder":
            folder = desired.parent / "바꾸리 변환"
        elif self.staging is None:
            # Save only the first result temporarily. Most conversion engines reuse their output path.
            staging = TemporaryDirectory(prefix="BakuriOutput-")
            try:
                staged = self.control._copy(source, Path(staging.name) / desired.name, check)
            except BaseException:
                staging.cleanup()
                raise
            self.staging = staging
            self.pending = (staged, desired)
            return str(staged)
        else:
            if self.group is None:
                self.group = self._new_group(check)
            self.flush(check)
            folder = self.group
        folder.mkdir(parents=True, exist_ok=True)
        return self.control._publish(source, folder / desired.name, check)

    def _new_group(self, check):
        number = 0
        while True:
            check()
            folder = self.first_folder / ("바꾸리 변환" if not number else f"바꾸리 변환_{number}")
            try:
                folder.mkdir()
            except FileExistsError:
                number += 1
            else:
                return folder

    def flush(self, check):
        if self.pending is None:
            return
        staged, desired = self.pending
        if self.group is not None:
            desired = self.group / desired.name
        output = self.control._publish(staged, desired, check)
        self.first_result = (str(staged), output)
        self.pending = None

    def close(self):
        if self.staging is None:
            return
        for row in self.control.rows:
            if self.first_result and row["output"] == self.first_result[0]:
                row["output"] = self.first_result[1]
            elif self.pending and row["output"] == str(self.pending[0]):
                row.update(
                    output="", after=row["before"], status="실패", detail="저장할 수 없습니다."
                )
        self.staging.cleanup()
        if self.group is not None and not self.control.outputs:
            try:
                self.group.rmdir()
            except OSError:
                pass
