"""CI-only: the installed executable must offer again after 'Later' and reopening."""

import os
from pathlib import Path
import subprocess
import sys
import time
import winreg
import xml.etree.ElementTree as ET
import win32con
import win32gui
from PIL import ImageGrab
from version import VERSION


def visible_windows():
    found = []

    def visit(hwnd, _):
        try:
            title = win32gui.GetWindowText(hwnd)
            if win32gui.IsWindowVisible(hwnd) and "바꾸리" in title:
                found.append((hwnd, title))
        except win32gui.error:
            pass

    win32gui.EnumWindows(visit, None)
    return found


def wait_prompt(label, folder):
    deadline = time.monotonic() + 75
    while time.monotonic() < deadline:
        visible = visible_windows()
        prompt = next((hwnd for hwnd, title in visible if title == "바꾸리 업데이트"), None)
        if prompt:
            ImageGrab.grab().save(folder / (label + ".png"))
            return prompt
        time.sleep(0.25)
    raise RuntimeError(f"Installed update prompt missing at {label}")


def verify(root):
    root = Path(root).resolve()
    manifest = root / "current/sq.version"
    original = manifest.read_bytes()
    folder = Path("UpdateVerification")
    folder.mkdir(exist_ok=True)
    child = None
    key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Bakuri\FileConverter")
    try:
        try:
            saved, saved_type = winreg.QueryValueEx(key, "update_skipped_version")
        except FileNotFoundError:
            saved, saved_type = None, None
        try:
            winreg.DeleteValue(key, "update_skipped_version")
        except FileNotFoundError:
            pass
        # Lower only this isolated installation's SDK metadata; its actual EXE stays intact.
        # That lets the real public release be newer without publishing a fake release.
        tree = ET.parse(manifest)
        node = next(n for n in tree.iter() if n.tag.rsplit("}", 1)[-1] == "version")
        node.text = "0.0.1"
        tree.write(manifest, encoding="utf-8", xml_declaration=True)
        exe = root / "current/BakuriFileConverter.exe"
        env = dict(os.environ, QT_QPA_PLATFORM="windows", BAKURI_DISABLE_SHELL_INTEGRATION="1")
        child = subprocess.Popen([str(exe)], env=env)
        prompt = wait_prompt("initial-update", folder)
        win32gui.PostMessage(prompt, win32con.WM_CLOSE, 0, 0)
        time.sleep(0.75)
        main = next(hwnd for hwnd, title in visible_windows() if "파일 변환기" in title)
        win32gui.PostMessage(main, win32con.WM_CLOSE, 0, 0)
        time.sleep(0.75)
        reopen = subprocess.Popen([str(exe)], env=env)
        reopen.wait(timeout=20)
        prompt = wait_prompt("reopened-update", folder)
        win32gui.PostMessage(prompt, win32con.WM_CLOSE, 0, 0)
        print(f"Installed {VERSION} frontend offered twice after reopening within five minutes.")
    finally:
        if child is not None and child.poll() is None:
            subprocess.run(["taskkill", "/PID", str(child.pid), "/T", "/F"], capture_output=True)
        manifest.write_bytes(original)
        if saved is not None:
            winreg.SetValueEx(key, "update_skipped_version", 0, saved_type, saved)
        else:
            try:
                winreg.DeleteValue(key, "update_skipped_version")
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)


if __name__ == "__main__":
    verify(Path(sys.argv[1]))
