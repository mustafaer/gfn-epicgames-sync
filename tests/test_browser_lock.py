"""Stale browser-profile locks.

Chrome leaves a SingletonLock symlink pointing at its own pid. A killed run
leaves it behind, and without cleanup every later command refuses to start.
Only a provably dead owner may be cleared.
"""
import os
import sys

import pytest

import epicsync.browser as browser

# Chrome's SingletonLock is a POSIX symlink. Windows Chrome uses a different
# scheme entirely, and creating symlinks there needs elevation or Developer
# Mode - so the whole module is POSIX-only.
pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="SingletonLock symlinks are POSIX-only; cleanup is a no-op on Windows",
)


@pytest.fixture()
def profile(tmp_path, monkeypatch):
    monkeypatch.setattr(browser, "PROFILE", tmp_path)
    return tmp_path


def _write_lock(profile, pid):
    link = profile / "SingletonLock"
    os.symlink(f"somehost-{pid}", link)
    (profile / "SingletonCookie").write_text("x")
    return link


def test_no_lock_is_not_an_error(profile):
    assert browser._clear_stale_lock() is False


def test_dead_owner_is_cleared(profile):
    # Pick a pid that cannot exist.
    _write_lock(profile, 999999)
    assert browser._clear_stale_lock() is True
    # lexists, not exists: these are symlinks to targets that never existed.
    assert not os.path.lexists(profile / "SingletonLock")
    assert not os.path.lexists(profile / "SingletonCookie")


def test_live_owner_is_left_alone(profile):
    _write_lock(profile, os.getpid())
    assert browser._clear_stale_lock() is False
    assert os.path.lexists(profile / "SingletonLock")


def test_unparseable_lock_is_left_alone(profile):
    os.symlink("no-pid-here", profile / "SingletonLock")
    assert browser._clear_stale_lock() is False
    assert os.path.lexists(profile / "SingletonLock")


def test_lock_errors_are_recognised():
    assert browser._is_lock_error(Exception("Opening in existing browser session")) is True
    assert browser._is_lock_error(Exception("something else")) is False
