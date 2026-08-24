"""Cross-platform browser launch for the GeForce NOW web client.

Two facts drive this module:

* The GFN client is an Angular app that never finishes bootstrapping in
  headless Chromium - it stalls on the NVIDIA splash screen. Every command
  therefore runs headed.
* GFN degrades the experience for browsers it does not recognize, so a real
  Chrome/Edge install is preferred over Playwright's bundled Chromium.
"""
import os
import sys

from playwright.sync_api import Error as PlaywrightError

from .paths import PROFILE

# A stable desktop Chrome UA. Without it GFN shows a
# "not using a recommended browser" warning.
CHROME_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
)

# Tried in order; falls back to the bundled Chromium.
CHANNELS = ("chrome", "chrome-beta", "msedge")

_LOCK_HINTS = ("existing browser session", "already in use", "ProcessSingleton")


class ProfileLocked(RuntimeError):
    """Raised when another epicsync process still owns the browser profile."""


def _process_alive(pid: int) -> bool:
    """Whether ``pid`` is running. Never signals the process.

    ``os.kill(pid, 0)`` is a harmless existence probe on POSIX only. On Windows
    ``os.kill`` routes every signal to TerminateProcess, so calling it there
    would kill the very process we are asking about.
    """
    if sys.platform == "win32":
        import ctypes

        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True             # cannot tell - assume alive
            return code.value == STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True                     # exists, owned by someone else
    except OSError:
        return True                     # cannot tell - assume alive
    return True


def _clear_stale_lock() -> bool:
    """Remove a SingletonLock left behind by a browser that is gone.

    Chrome writes ``SingletonLock`` as a symlink to ``<host>-<pid>``. A crashed
    or killed run leaves it pointing at a dead process, and every later command
    then refuses to start. Only a provably dead owner is cleared.

    Windows Chrome does not use this scheme, so nothing is found there and the
    function is a no-op.
    """
    lock = PROFILE / "SingletonLock"
    try:
        target = os.readlink(lock)
    except (OSError, ValueError, NotImplementedError):
        return False

    _, _, pid_text = target.rpartition("-")
    if not pid_text.isdigit() or _process_alive(int(pid_text)):
        return False

    for name in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        try:
            (PROFILE / name).unlink()
        except OSError:
            pass
    return True


def _is_lock_error(exc: Exception) -> bool:
    text = str(exc)
    return any(h in text for h in _LOCK_HINTS)


def launch(pw, headless: bool = False):
    """Open the persistent browser context used by every command."""
    opts = {
        "user_data_dir": str(PROFILE),
        "headless": headless,
        "viewport": {"width": 1440, "height": 900},
        "user_agent": CHROME_UA,
        "args": ["--disable-blink-features=AutomationControlled"],
    }

    last = None
    for channel in CHANNELS:
        try:
            return pw.chromium.launch_persistent_context(channel=channel, **opts)
        except Exception as exc:
            if _is_lock_error(exc):
                if _clear_stale_lock():
                    return launch(pw, headless=headless)   # owner was dead
                raise ProfileLocked(
                    "The browser profile is in use by another process.\n"
                    "Close any running epicsync window, then try again."
                ) from None
            last = exc

    try:
        return pw.chromium.launch_persistent_context(**opts)
    except Exception as exc:
        if _is_lock_error(exc):
            raise ProfileLocked(
                "The browser profile is locked. Close the other epicsync window."
            ) from None
        raise RuntimeError(
            "Could not start a browser.\n"
            "Install Google Chrome, or run: python -m playwright install chromium\n"
            f"Last error: {last or exc}"
        ) from None


__all__ = ["CHROME_UA", "PlaywrightError", "ProfileLocked", "launch"]
