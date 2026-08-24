# Troubleshooting

## `Not signed in to GFN`

The stored browser session expired. Run:

```bash
epicsync login
```

Sign in in the window that opens. epicsync detects success automatically and
closes the window. Accept any cookie or terms banner yourself — the tool never
clicks consent controls.

## `The browser profile is in use by another process`

Another epicsync window is still open, or a previous run left Chrome running.
Close the window and try again - a lock whose owner is gone is detected and
cleared automatically on macOS and Linux.

If a browser really is still running, end it yourself.

macOS and Linux:

```bash
pkill -f "gfn-epicgames-sync/browser-profile"
```

Windows (PowerShell):

```powershell
Get-CimInstance Win32_Process -Filter "Name='chrome.exe'" | Where-Object { $_.CommandLine -like '*browser-profile*' } | ForEach-Object { Stop-Process -Id $_.ProcessId }
```

Chrome on Windows does not use the symlink lock that the automatic cleanup
looks for, so stale locks there always need this manual step.

## `Could not start a browser`

No Chrome or Edge was found. Either install Google Chrome, or use Playwright's
bundled browser:

```bash
python -m playwright install chromium
```

## `Epic account not linked`

epicsync reads your library through `legendary`, which needs its own sign-in:

```bash
legendary auth
```

The command opens a browser, and you paste the code it shows back into your own
terminal. epicsync never sees the code or your password.

## `Your Epic library came back empty`

The audit refuses to flag anything when the library returns nothing, because it
would otherwise treat every ownership claim as bogus. Check what `legendary`
reports:

```bash
legendary list-games --platform Windows --json
```

If that is empty, re-authenticate with `legendary auth`. Note the explicit
platform: `legendary` defaults to the *host* platform, which on macOS lists
only games with a Mac build and hides most of the library. epicsync always
asks for Windows, because that is what GeForce NOW streams.

## `legendary list-games failed`

The message includes `legendary`'s own error. Most often the session expired:

```bash
legendary auth
```

A stale metadata cache can also cause it:

```bash
legendary list-games --platform Windows --force-refresh
```

## `ownership dialog did not open`

`MARK AS OWNED` was clicked but the dialog never appeared, usually a slow or
stalled client. Re-run the command — completed games are skipped, so it picks
up where it stopped. If it happens for every game, the dialog element was
probably renamed; check with `epicsync inspect` and update `DIALOG` and `STAGE`
in `epicsync/mark.py`.

## `legendary was not found`

```bash
pip install legendary-gl
```

If it is installed but not on `PATH`, epicsync also looks in the current
interpreter's `bin`/`Scripts` directory.

## `no 'MARK AS OWNED' control`

Usually normal: the game is already playable, so GFN renders `PLAY` instead.
`epicsync status` will show it under *already playable*.

If it happens for a game that is clearly unowned, the UI labels may have
changed. Check what the page actually offers:

```bash
epicsync inspect "Metro Exodus"
```

Then update the label constants near the top of `epicsync/mark.py`:

- `OWN_BUTTON_TEXTS` — the marking control
- `ALREADY_OWNED_TEXTS` — the "you already have this" state
- `FORBIDDEN_TEXTS` — never-click list, keep `BUY` in it
- `EPIC` / `NOT_FOUND` — store picker strings

Selectors are text- and ARIA-based on purpose. GFN's CSS class names contain
build hashes (`ng-tns-c523391267-24`) and change between releases.

## Everything reports "not on GFN"

The search never ran. Confirm the client loads and you are signed in:

```bash
epicsync inspect "Fortnite"
```

If that fails too, the search box selector or the Enter-to-search behavior
changed. See `_search()` in `epicsync/mark.py`.

## A run stopped halfway

Progress is written after every game. Re-run the same command and it resumes;
completed games are skipped instantly.

To start over, delete the state file (find the directory with
`epicsync where`):

```bash
rm "$(epicsync where | head -1 | cut -d' ' -f3-)/mark-state.json"
```

## Output shows `[ok]` / `[!]` instead of symbols

Expected on terminals that are not UTF-8, typically `cmd.exe`. Use Windows
Terminal or PowerShell for the richer output. Behavior is unaffected.

## Linux: the window never appears

A graphical session is required - the GFN client never bootstraps in a headless
browser. Under SSH or on a headless host:

```bash
xvfb-run -a epicsync sweep
```

If Chrome itself is missing, install a channel Playwright recognizes
(`google-chrome-stable` or `microsoft-edge-stable`), or fall back to the
bundled browser:

```bash
python -m playwright install chromium
```

Some minimal containers also lack Chrome's shared libraries:

```bash
python -m playwright install-deps chromium
```

## A game will not launch after being marked

The claim is probably wrong — GFN does not verify ownership. Find and revert it:

```bash
epicsync audit
```

```bash
epicsync unmark --dry-run
```
