"""Cross-platform behavior.

CI runs the suite on macOS, Linux and Windows, but each job only exercises its
own branch. These tests simulate the other two so a regression on any platform
fails everywhere.
"""
import os
import sys
from pathlib import Path

import pytest

import epicsync.browser as browser
import epicsync.epiclib as epiclib
import epicsync.paths as paths


# --------------------------------------------------------------------------- #
# data directory
# --------------------------------------------------------------------------- #
def test_macos_uses_application_support(monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    monkeypatch.delenv("EPICSYNC_DATA_DIR", raising=False)
    assert paths._default_data_dir() == Path.home() / "Library/Application Support" / paths.APP


def test_windows_prefers_localappdata(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("EPICSYNC_DATA_DIR", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", r"C:\Users\x\AppData\Local")
    assert paths._default_data_dir() == Path(r"C:\Users\x\AppData\Local") / paths.APP


def test_windows_falls_back_to_appdata(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.delenv("EPICSYNC_DATA_DIR", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setenv("APPDATA", r"C:\Users\x\AppData\Roaming")
    assert paths._default_data_dir() == Path(r"C:\Users\x\AppData\Roaming") / paths.APP


def test_linux_honours_xdg(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("EPICSYNC_DATA_DIR", raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", "/custom/share")
    assert paths._default_data_dir() == Path("/custom/share") / paths.APP


def test_linux_default_without_xdg(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.delenv("EPICSYNC_DATA_DIR", raising=False)
    monkeypatch.delenv("XDG_DATA_HOME", raising=False)
    assert paths._default_data_dir() == Path.home() / ".local/share" / paths.APP


@pytest.mark.parametrize("platform", ["darwin", "linux", "win32"])
def test_env_override_wins_everywhere(monkeypatch, tmp_path, platform):
    monkeypatch.setattr(sys, "platform", platform)
    monkeypatch.setenv("EPICSYNC_DATA_DIR", str(tmp_path))
    assert paths._default_data_dir() == tmp_path


# --------------------------------------------------------------------------- #
# legendary discovery
# --------------------------------------------------------------------------- #
def test_finds_legendary_in_windows_scripts_layout(monkeypatch, tmp_path):
    scripts = tmp_path / "Scripts"
    scripts.mkdir()
    (scripts / "python.exe").write_text("")
    exe = scripts / "legendary.exe"
    exe.write_text("")
    monkeypatch.setattr(sys, "executable", str(scripts / "python.exe"))
    assert epiclib.executable() == str(exe)


def test_finds_legendary_next_to_a_posix_interpreter(monkeypatch, tmp_path):
    (tmp_path / "python").write_text("")
    exe = tmp_path / "legendary"
    exe.write_text("")
    monkeypatch.setattr(sys, "executable", str(tmp_path / "python"))
    assert epiclib.executable() == str(exe)


def test_falls_back_to_path(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "executable", str(tmp_path / "python"))
    monkeypatch.setattr(epiclib.shutil, "which", lambda name: "/usr/bin/legendary")
    assert epiclib.executable() == "/usr/bin/legendary"


def test_missing_legendary_explains_the_fix(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "executable", str(tmp_path / "python"))
    monkeypatch.setattr(epiclib.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="pip install legendary-gl"):
        epiclib.executable()


# --------------------------------------------------------------------------- #
# process probing
# --------------------------------------------------------------------------- #
def test_never_signals_a_process_on_windows(monkeypatch):
    # os.kill on Windows routes every signal to TerminateProcess, so probing
    # liveness with it would kill the process being asked about.
    def explode(*_args, **_kwargs):
        raise AssertionError("os.kill must not be used on Windows")

    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(os, "kill", explode)

    class FakeKernel:
        def OpenProcess(self, *_):
            return 0        # "no such process"

    import ctypes

    monkeypatch.setattr(ctypes, "windll",
                        type("W", (), {"kernel32": FakeKernel()})(), raising=False)
    assert browser._process_alive(4242) is False


def test_live_process_detected_on_posix(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    assert browser._process_alive(os.getpid()) is True


def test_dead_process_detected_on_posix(monkeypatch):
    # Spawn and reap a real process so the pid is provably gone. A hard-coded
    # high pid is not safe: Linux allows pids well above a million.
    import subprocess

    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()

    monkeypatch.setattr(sys, "platform", "linux")
    assert browser._process_alive(child.pid) is False
