"""Safety guards around reverting ownership claims.

Reverting is destructive, so the audit refuses to produce candidates it cannot
justify. These tests pin the refusals in place.
"""

import pytest

import epicsync.audit as audit

ROWS = [
    {"game_id": "1", "title": "Owned Game", "store": "Epic Games Store Owned",
     "epic": True, "in_epic_library": False},
    {"game_id": "2", "title": "Bogus Claim", "store": "Epic Games Store Owned",
     "epic": True, "in_epic_library": True},
    {"game_id": "3", "title": "Steam Game", "store": "Steam Owned",
     "epic": False, "in_epic_library": False},
]


def test_refuses_to_flag_when_library_is_empty(monkeypatch):
    # An empty library would otherwise turn every claim into a deletion target.
    monkeypatch.setattr(audit.epiclib, "fetch", lambda *a, **k: [])
    with pytest.raises(RuntimeError, match="empty"):
        audit.suspects(ROWS)


def test_ignores_the_stored_flag_and_recomputes(monkeypatch):
    # Row 2 is stored as in_epic_library=True but the library says otherwise;
    # row 1 is stored False yet is owned. Both must be re-evaluated.
    monkeypatch.setattr(audit.epiclib, "fetch",
                        lambda *a, **k: [{"title": "Owned Game"}])
    flagged = [row["title"] for row in audit.suspects(ROWS)]
    assert flagged == ["Bogus Claim"]


def test_non_epic_rows_are_never_flagged(monkeypatch):
    monkeypatch.setattr(audit.epiclib, "fetch", lambda *a, **k: [{"title": "Nothing"}])
    flagged = [row["title"] for row in audit.suspects(ROWS)]
    assert "Steam Game" not in flagged


def test_loose_title_differences_do_not_flag(monkeypatch):
    rows = [{"game_id": "9", "title": "Rustler", "store": "Epic Games Store Owned",
             "epic": True, "in_epic_library": False}]
    monkeypatch.setattr(audit.epiclib, "fetch",
                        lambda *a, **k: [{"title": "Rustler - Grand Theft Horse"}])
    assert audit.suspects(rows) == []


def test_unmark_aborts_without_confirmation(monkeypatch, capsys):
    monkeypatch.setattr("builtins.input", lambda *a: "no")
    reverted, failed = audit.unmark([{"game_id": "1", "title": "X"}])
    assert (reverted, failed) == (0, 0)
    assert "Aborted" in capsys.readouterr().out


def test_unmark_aborts_on_non_interactive_stdin(monkeypatch, capsys):
    def raise_eof(*_args):
        raise EOFError

    monkeypatch.setattr("builtins.input", raise_eof)
    reverted, failed = audit.unmark([{"game_id": "1", "title": "X"}])
    assert (reverted, failed) == (0, 0)
    assert "Aborted" in capsys.readouterr().out
