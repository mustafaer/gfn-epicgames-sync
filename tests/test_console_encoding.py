"""Console output on terminals that cannot encode symbols.

Windows `cmd.exe` commonly runs on a legacy code page. Output must degrade to
ASCII rather than raising UnicodeEncodeError mid-run.
"""
import importlib

import epicsync.ui as ui


def _reload_with_encoding(monkeypatch, encoding):
    class FakeStdout:
        def __init__(self, enc):
            self.encoding = enc

    monkeypatch.setattr("sys.stdout", FakeStdout(encoding))
    return importlib.reload(ui)


def test_utf8_terminal_keeps_symbols(monkeypatch):
    module = _reload_with_encoding(monkeypatch, "utf-8")
    assert module.sym("ok") == "✓"


def test_legacy_codepage_falls_back_to_ascii(monkeypatch):
    module = _reload_with_encoding(monkeypatch, "cp1252")
    assert module.sym("ok") == "[ok]"
    assert module.sym("warn") == "[!]"


def test_unknown_encoding_falls_back(monkeypatch):
    module = _reload_with_encoding(monkeypatch, "not-a-real-encoding")
    assert module.sym("fail") == "[fail]"


def test_say_rewrites_symbols_for_legacy_terminals(monkeypatch, capsys):
    module = _reload_with_encoding(monkeypatch, "cp1252")
    monkeypatch.undo()
    module.say("✓ done", "→", "next")
    assert "[ok] done" in capsys.readouterr().out


def test_every_symbol_has_an_ascii_form():
    for rich, plain in ui._SYMBOLS.values():
        assert plain.isascii(), f"{rich} has no ASCII fallback"
