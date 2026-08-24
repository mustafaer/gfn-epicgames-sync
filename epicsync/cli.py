"""Command-line interface."""
import argparse
import json
import sys

from . import __version__, epiclib, mark
from . import audit as audit_mod
from . import plan as plan_mod
from .paths import AUDIT, DATA, PLAN, REPORT, STATE, ensure_data_dir
from .ui import say, sym


def _load_plan():
    if not PLAN.exists():
        sys.exit("No plan yet. Run: epicsync plan")
    return json.loads(PLAN.read_text(encoding="utf-8"))


def _require_epic():
    if not epiclib.is_authenticated():
        sys.exit("Epic account not linked. Run: epicsync auth")


# --------------------------------------------------------------------------- #
def cmd_auth(args):
    if epiclib.is_authenticated():
        say(sym("ok"), f"Epic account linked: {epiclib.account()}")
        return
    say("Sign in to Epic through legendary; epicsync never sees your password.")
    say("Run this and paste the code it asks for:\n")
    say("    legendary auth\n")


def cmd_plan(args):
    _require_epic()
    plan = plan_mod.build(force=args.refresh)
    matches = plan["matches"]
    def tier(name):
        return sum(1 for m in matches if m["tier"] == name)

    say(f"Epic library        : {plan['epic_library_size']}")
    say(f"GFN-supported Epic  : {plan['gfn_epic_catalog_size']}")
    say(f"Intersection        : {len(matches)}  "
        f"(exact {tier('exact')}, strong {tier('strong')}, review {tier('review')})")
    say(f"\nReport: {REPORT}\nPlan  : {PLAN}")


def cmd_login(args):
    mark.login()


def cmd_mark(args):
    plan = _load_plan()
    targets = plan_mod.auto_targets(plan, include_review=args.include_review)
    if args.limit:
        targets = targets[: args.limit]
    if not targets:
        sys.exit("Nothing to mark.")
    say(f"Processing {len(targets)} games{' (DRY-RUN)' if args.dry_run else ''}\n")
    mark.run(targets, dry_run=args.dry_run, delay=args.delay)


def cmd_sweep(args):
    """Skip the public catalog and test every owned game against the live UI."""
    _require_epic()
    library = epiclib.fetch()
    targets = [
        {"gfn_id": "epic:" + (g["app_name"] or g["title"]), "gfn_title": g["title"]}
        for g in library
    ]
    if args.limit:
        targets = targets[: args.limit]
    say(f"Checking {len(targets)} Epic games against the live GFN client"
        f"{' (DRY-RUN)' if args.dry_run else ''}")
    say("Titles GFN does not carry are discarded quickly; progress is saved.\n")
    mark.run(targets, dry_run=args.dry_run, delay=args.delay)


def cmd_audit(args):
    _require_epic()
    rows = audit_mod.run_audit(refresh_ids=args.refresh)
    flagged = audit_mod.suspects(rows)
    epic_rows = [r for r in rows if r["epic"]]
    say(f"\nScanned {len(rows)} | Epic-claimed {len(epic_rows)} | "
        f"Suspect {len(flagged)}")
    for row in flagged:
        say(f"   {sym('warn')}  {row['title']}")
    say(f"\nDetails: {AUDIT}")
    if flagged:
        say("Revert them with: epicsync unmark --dry-run")


def cmd_unmark(args):
    if not AUDIT.exists():
        sys.exit("Run an audit first: epicsync audit")
    flagged = audit_mod.suspects()
    if args.title:
        flagged = [r for r in flagged if args.title.lower() in r["title"].lower()]
    if not flagged:
        sys.exit("Nothing to revert.")
    say(f"{len(flagged)} game(s){' (DRY-RUN)' if args.dry_run else ''}:")
    for row in flagged:
        say("   ", row["title"])
    say("")
    audit_mod.unmark(flagged, dry_run=args.dry_run, delay=args.delay,
                     assume_yes=args.yes)


def cmd_status(args):
    if not STATE.exists():
        sys.exit("Nothing recorded yet.")
    state = json.loads(STATE.read_text(encoding="utf-8"))

    marked, playable, steam, blocked, absent, errors = {}, {}, {}, {}, {}, {}
    for entry in state["done"].values():
        how, title = str(entry["how"]), entry["title"]
        if how == "marked":
            marked[title] = True
        elif how.startswith("already"):
            playable[title] = True
            if entry.get("epic") is False:
                steam[title] = entry.get("store", "?")
        elif "not-on-gfn" in how:
            absent[title] = True
        elif how.startswith("skip:"):
            blocked[title] = how[len("skip:"):]

    for entry in state["failed"].values():
        message = (entry.get("error") or "").lower()
        if "not found" in message and "search" in message:
            absent[entry["title"]] = True       # historical mislabel
        else:
            errors[entry["title"]] = (entry.get("error") or "")[:70]

    for bucket in (playable, blocked, absent, errors):
        for title in list(bucket):
            if title in marked:
                del bucket[title]

    say(f"{sym('ok')} Marked as owned on Epic ({len(marked)}):")
    for title in sorted(marked):
        say("   ", title)
    say(f"\n{sym('dot')} Already playable: {len(playable)}"
        f"  - {len(steam)} of them come from another store:")
    for title in sorted(steam):
        say(f"   {sym('warn')} {title}")
    say(f"\n{sym('skip')} Could not mark ({len(blocked)}):")
    for title in sorted(blocked):
        reason = (
            "GFN does not offer Epic for this title"
            if "epic-unavailable" in blocked[title]
            else "confirmation named a different store - safety gate"
        )
        say(f"   {title} - {reason}")
    say(f"\n{sym('dot')} Not carried by GFN: {len(absent)}")
    say(f"{sym('fail')} Errors: {len(errors)}")
    for title, message in errors.items():
        say(f"   {title}: {message}")


def cmd_inspect(args):
    mark.inspect(args.title)


def cmd_where(args):
    from .paths import EPIC_LIBRARY, GFN_CATALOG, LIBRARY_IDS, PROFILE

    say(f"Data directory: {DATA}\n")
    entries = (
        (EPIC_LIBRARY, "Epic library snapshot"),
        (GFN_CATALOG, "cached NVIDIA catalog"),
        (PLAN, "catalog match plan"),
        (REPORT, "readable plan report"),
        (STATE, "resumable progress"),
        (LIBRARY_IDS, "GFN library game ids"),
        (AUDIT, "ownership snapshot"),
        (PROFILE, "browser session (private)"),
    )
    width = max(len(path.name) for path, _ in entries)
    for path, description in entries:
        mark = "present" if path.exists() else "-"
        say(f"  {path.name:<{width}}  {mark:<7}  {description}")


# --------------------------------------------------------------------------- #
def build_parser():
    parser = argparse.ArgumentParser(
        prog="epicsync",
        description="Bulk-mark your Epic Games library as owned on GeForce NOW.",
    )
    parser.add_argument("--version", action="version", version=f"gfn-epicgames-sync {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("auth", help="show Epic sign-in status").set_defaults(func=cmd_auth)
    sub.add_parser("login", help="sign in to the GFN web client").set_defaults(func=cmd_login)
    sub.add_parser("status", help="summarize saved progress").set_defaults(func=cmd_status)
    sub.add_parser("where", help="print the data directory").set_defaults(func=cmd_where)

    p = sub.add_parser("plan", help="match your library against the public catalog")
    p.add_argument("--refresh", action="store_true", help="ignore cached data")
    p.set_defaults(func=cmd_plan)

    m = sub.add_parser("mark", help="mark planned games as owned")
    m.add_argument("--dry-run", action="store_true")
    m.add_argument("--include-review", action="store_true", help="include low-confidence matches")
    m.add_argument("--limit", type=int)
    m.add_argument("--delay", type=float, default=0.4)
    m.set_defaults(func=cmd_mark)

    s = sub.add_parser(
        "sweep", help="check every owned game against the live client (recommended)"
    )
    s.add_argument("--dry-run", action="store_true")
    s.add_argument("--limit", type=int)
    s.add_argument("--delay", type=float, default=0.4)
    s.set_defaults(func=cmd_sweep)

    a = sub.add_parser("audit", help="find ownership claims your Epic library cannot back")
    a.add_argument("--refresh", action="store_true", help="re-collect the game id list")
    a.set_defaults(func=cmd_audit)

    u = sub.add_parser("unmark", help="revert incorrect Epic ownership claims")
    u.add_argument("--dry-run", action="store_true")
    u.add_argument("--title", help="only titles containing this text")
    u.add_argument("--delay", type=float, default=0.5)
    u.add_argument("--yes", action="store_true", help="skip the confirmation prompt")
    u.set_defaults(func=cmd_unmark)

    i = sub.add_parser("inspect", help="dump a game page's controls (UI calibration)")
    i.add_argument("title")
    i.set_defaults(func=cmd_inspect)

    return parser


def main(argv=None):
    args = build_parser().parse_args(argv)
    ensure_data_dir()
    try:
        args.func(args)
    except KeyboardInterrupt:
        say("\nInterrupted. Progress is saved; run the same command to resume.")
        return 130
    except RuntimeError as error:
        say(f"{sym('fail')} {error}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
