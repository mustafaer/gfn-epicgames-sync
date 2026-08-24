"""Builds the catalog-based match plan and its human-readable report."""
import json

from . import catalog, epiclib, match
from .paths import PLAN, REPORT


def build(force: bool = False):
    catalog_data = catalog.fetch(force=force)
    gfn_epic = catalog.epic_titles(catalog_data)
    epic_games = epiclib.fetch(force=force)

    matches, unmatched = match.build(epic_games, gfn_epic)

    plan = {
        "account": epiclib.account(),
        "epic_library_size": len(epic_games),
        "gfn_epic_catalog_size": len(gfn_epic),
        "matches": matches,
    }
    PLAN.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    REPORT.write_text(_render(plan, unmatched), encoding="utf-8")
    return plan


def auto_targets(plan, include_review: bool = False):
    tiers = {"exact", "strong"} | ({"review"} if include_review else set())
    return [m for m in plan["matches"] if m["tier"] in tiers]


def _render(plan, unmatched) -> str:
    matches = plan["matches"]
    def count(tier):
        return sum(1 for m in matches if m["tier"] == tier)


    lines = [
        "# gfn-epicgames-sync report",
        "",
        f"- Epic account: `{plan['account']}`",
        f"- Epic library: **{plan['epic_library_size']}** games",
        f"- GFN-supported Epic titles: **{plan['gfn_epic_catalog_size']}**",
        f"- Intersection: **{len(matches)}** "
        f"(exact {count('exact')}, strong {count('strong')}, review {count('review')})",
        "",
        "## Candidates to mark",
        "",
        "| # | GFN title | Epic title | Tier | Score | Optimized |",
        "|---|---|---|---|---|---|",
    ]
    for index, m in enumerate(matches, 1):
        same = m["gfn_title"] == m["epic_title"]
        lines.append(
            f"| {index} | {m['gfn_title']} | {'same' if same else m['epic_title']} "
            f"| {m['tier']} | {m['score']} | {'yes' if m['optimized'] else '-'} |"
        )

    lines += [
        "",
        f"## GFN-supported Epic titles you do not own ({len(unmatched)})",
        "",
        "<details><summary>show list</summary>",
        "",
        *[f"- {entry['title']}" for entry in unmatched],
        "",
        "</details>",
        "",
    ]
    return "\n".join(lines)
