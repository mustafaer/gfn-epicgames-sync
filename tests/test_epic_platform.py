"""Regression guard for the platform bug.

`legendary list-games` defaults to the host platform. On macOS that is "Mac",
which returned 261 entries on the reference account against 845 for Windows.
GeForce NOW streams Windows builds, so the Mac default hid most of the library
and made the audit flag 161 owned games as bogus claims.
"""
import epicsync.epiclib as epiclib


def test_platform_is_windows():
    assert epiclib.PLATFORM == "Windows"


def test_fetch_requests_windows_explicitly(monkeypatch, tmp_path):
    captured = {}

    class Result:
        returncode = 0
        stdout = "[]"
        stderr = ""

    def fake_run(args):
        captured["args"] = args
        return Result()

    monkeypatch.setattr(epiclib, "_run", fake_run)
    monkeypatch.setattr(epiclib, "EPIC_LIBRARY", tmp_path / "lib.json")

    epiclib.fetch(force=True)

    assert "--platform" in captured["args"]
    index = captured["args"].index("--platform")
    assert captured["args"][index + 1] == "Windows"
