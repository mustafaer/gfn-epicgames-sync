# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project
adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-08-24

First public release.

### Added

- `sweep` - check every owned Epic game against the live GeForce NOW client
  and mark the ones it carries.
- `audit` / `unmark` - find ownership claims the Epic library cannot back, and
  revert them.
- `plan` / `mark` - faster path based on NVIDIA's public catalog, kept as an
  approximation since that catalog is incomplete.
- `status`, `where`, `inspect`, `login`, `auth` helper commands.
- Resumable progress: every game is recorded as it is processed, so an
  interrupted run continues where it stopped.
- Support for macOS, Linux and Windows, including ASCII output on terminals
  that are not UTF-8.

### Safety

- **Store safety gate** - `CONTINUE` is pressed only when the GFN confirmation
  names the Epic Games Store, so a title whose entry resolves to another store
  is never claimed.
- **Purchase protection** - controls labeled `BUY`, `PURCHASE`, `SUBSCRIBE`
  or `UPGRADE` are excluded from every click path.
- **Reverting requires confirmation** - `unmark` lists every title and waits
  for a typed `yes`.
- **Empty-library refusal** - the audit flags nothing if the Epic library
  comes back empty, rather than treating every claim as bogus.
