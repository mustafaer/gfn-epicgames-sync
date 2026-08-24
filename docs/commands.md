# Command reference

Every command is a subcommand of `epicsync`. Run `epicsync <command> --help`
for the same information at the terminal.

Commands that drive the browser (`login`, `sweep`, `mark`, `audit`, `unmark`,
`inspect`) open a real Chrome window — the GeForce NOW client does not work
headless.

---

## `epicsync auth`

Reports whether `legendary` is signed in to Epic, and prints the sign-in
command if it is not. epicsync never handles your Epic password; `legendary`
performs Epic's official OAuth flow.

No options.

---

## `epicsync login`

Opens the GeForce NOW web client so you can sign in with your NVIDIA account.
Sign-in is detected automatically and the session is stored in the data
directory, so this is normally needed only once.

Cookie and terms banners are **not** clicked by epicsync — accept them
yourself.

No options. Times out after 15 minutes.

---

## `epicsync sweep`

**The recommended way to mark your library.** Checks every game in your Epic
library against the live GFN client and marks the ones GFN carries.

This bypasses NVIDIA's public catalog, which is incomplete and can be stale.

| Option | Default | Purpose |
|---|---|---|
| `--dry-run` | off | Walk the whole flow up to the Epic confirmation, then back out without confirming. |
| `--limit N` | all | Process only the first N games. Useful for a quick check. |
| `--delay S` | `0.4` | Seconds to pause between games. Raise it if the client struggles. |

Progress is written after every game. Interrupt at any time and re-run to
resume; completed games are skipped instantly.

---

## `epicsync plan`

Matches your Epic library against NVIDIA's public supported-games list and
writes `plan.json` plus a readable `report.md`. Faster than `sweep`, but only
an approximation — the public list misses titles GFN actually carries.

| Option | Default | Purpose |
|---|---|---|
| `--refresh` | off | Ignore cached copies and re-download the catalog and re-read the library. |

---

## `epicsync mark`

Marks the games found by `plan`. Prefer `sweep` unless you specifically want
the catalog-based shortlist.

| Option | Default | Purpose |
|---|---|---|
| `--dry-run` | off | Reach the Epic confirmation without confirming. |
| `--include-review` | off | Also process low-confidence matches (`review` tier). Inspect `report.md` first. |
| `--limit N` | all | Process only the first N matches. |
| `--delay S` | `0.4` | Seconds between games. |

Match tiers are `exact` (identical after normalization), `strong` (identical
once edition suffixes are stripped, or ≥0.93 similarity) and `review`
(0.85–0.93). Only `exact` and `strong` are processed by default.

---

## `epicsync audit`

Walks GFN's own "My Library", records which storefront GFN attributes to each
game, and flags anything claimed on Epic that your Epic library cannot back.
Those claims will fail to launch, because the cloud machine signs in to Epic
and cannot find the game.

| Option | Default | Purpose |
|---|---|---|
| `--refresh` | off | Re-collect the list of library game ids instead of reusing the cached one. |

Results are written to `audit.json`. Expect roughly three seconds per game.

---

## `epicsync unmark`

Reverts the claims `audit` flagged, via the game menu's *Unmark as owned*.

| Option | Default | Purpose |
|---|---|---|
| `--dry-run` | off | Show what would be reverted, change nothing. |
| `--title TEXT` | all | Only titles containing TEXT (case-insensitive). |
| `--yes` | off | Skip the typed confirmation. Intended for scripts. |
| `--delay S` | `0.5` | Seconds between games. |

Reverting is destructive — a claim removed by mistake has to be re-made by
hand. Every title is listed and a typed `yes` is required unless `--yes` is
given. Title matching is heuristic, so **review the list before agreeing**.

---

## `epicsync status`

Summarizes saved progress: what was marked on Epic, what is already playable
(and from which store), what could not be marked and why, what GFN does not
carry, and any real errors.

No options.

---

## `epicsync where`

Prints the data directory and which of its files exist.

No options.

---

## `epicsync inspect "<title>"`

Opens one game and dumps its URL, attributed store and every button label.
This is the calibration tool: when NVIDIA changes the UI, run it to see the
current labels, then update the constants in `epicsync/mark.py`.

Takes the game title as a positional argument.

---

## Exit codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | A recoverable error, printed as a message (not signed in, no browser, profile locked) |
| `2` | Bad command line (argparse) |
| `130` | Interrupted with Ctrl-C; progress is saved |

## Environment

| Variable | Purpose |
|---|---|
| `EPICSYNC_DATA_DIR` | Override the data directory entirely. |

## Files in the data directory

| File | Contents |
|---|---|
| `epic-library.json` | Your Epic games, filtered to real titles |
| `gfn-catalog.json` | Cached copy of NVIDIA's public supported-games list |
| `plan.json` / `report.md` | Output of `plan` |
| `mark-state.json` | Resumable progress for `sweep` and `mark` |
| `library-ids.json` | GFN "My Library" game ids, collected by `audit` |
| `audit.json` | Per-game ownership snapshot from `audit` |
| `browser-profile/` | Your signed-in browser session — treat as private |
