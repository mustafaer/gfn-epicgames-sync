# Contributing

Thanks for helping out. This project automates an undocumented web UI, so the
most valuable contributions are usually fixes for things NVIDIA changed.

## Development setup

```bash
git clone https://github.com/mustafaer/gfn-epicgames-sync && cd gfn-epicgames-sync
```

```bash
python -m venv .venv && ./.venv/bin/pip install -e ".[dev]"
```

```bash
./.venv/bin/pytest
```

The test suite covers the pure logic — title normalization, matching, store
parsing, library filtering. It does not touch the network or a browser, so it
runs anywhere.

## Project layout

| Module | Responsibility |
|---|---|
| `cli.py` | Argument parsing and command handlers |
| `paths.py` | Per-platform data locations |
| `browser.py` | Launching Chrome, profile locks |
| `epiclib.py` | Reading the Epic library via `legendary` |
| `catalog.py` | NVIDIA's public supported-games list |
| `normalize.py` | Title normalization and the two matchers |
| `match.py` | Library-to-catalog matching for `plan` |
| `plan.py` | Plan and report generation |
| `mark.py` | GFN navigation and the ownership flow |
| `audit.py` | Library audit and reverting claims |
| `ui.py` | Console output with ASCII fallback |

`normalize.py` holds two matchers with deliberately opposite biases. `covers()`
decides which search result to open and is strict, because opening the wrong
game runs the ownership flow against it. `same_game()` backs the audit and is
generous, because a false negative there deletes a legitimate ownership claim.
Do not merge them.

## When the GFN UI changes

1. Capture what the page actually offers:
   ```bash
   epicsync inspect "Some Game"
   ```
2. Update the label constants at the top of `epicsync/mark.py`.
3. Add a case to `tests/` if the change is parseable logic rather than a selector.

Please keep selectors text- or ARIA-based. GFN's CSS classes carry build hashes
and will not survive a release.

## Non-negotiables

Two invariants protect users from asserting ownership they do not have, or from
spending money. Do not weaken them:

- **The safety gate.** `CONTINUE` is pressed only when the confirmation text
  names `Epic Games Store`.
- **The never-click list.** `FORBIDDEN_TEXTS` must keep excluding `BUY` and
  friends from every click path.

Any change touching `mark_one()` or `find_button()` needs a test.

## Style

- `ruff check .` should pass; line length 100.
- Comments should explain *why*, especially where the code works around GFN
  behavior. Record the observed behavior, not just the workaround.
- User-facing strings are English.

## Licensing

Contributions are accepted under the project's license, the
[GNU General Public License v3.0](LICENSE). By opening a pull request you
agree that your work is licensed on those terms.

## Reporting bugs

Include your OS, Python version, the command you ran, and the output of:

```bash
epicsync status
```

Please do not paste the contents of your data directory — it contains your
session.
