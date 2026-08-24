"""Matches an Epic library against GeForce NOW's Epic catalog entries.

Confidence tiers:

``exact``
    Normalized titles are identical - marked automatically.
``strong``
    Loose-normalized titles match, or similarity >= 0.93 - marked automatically.
``review``
    Similarity between 0.85 and 0.93 - reported, marked only with an opt-in.
"""
from difflib import SequenceMatcher

from .normalize import norm, norm_loose

STRONG_RATIO = 0.93
REVIEW_RATIO = 0.85

_TIER_RANK = {"exact": 0, "strong": 1, "review": 2}


def _ratio(left: str, right: str) -> float:
    return SequenceMatcher(None, left, right).ratio()


def build(epic_games, gfn_epic):
    """Return ``(matches, unmatched_gfn_entries)``."""
    by_norm, by_loose = {}, {}
    for entry in gfn_epic:
        by_norm.setdefault(norm(entry["title"]), []).append(entry)
        by_loose.setdefault(norm_loose(entry["title"]), []).append(entry)

    matches, used = [], set()

    for game in epic_games:
        exact_key, loose_key = norm(game["title"]), norm_loose(game["title"])
        hit, tier, score = None, None, 1.0

        if exact_key in by_norm:
            hit, tier = by_norm[exact_key][0], "exact"
        elif loose_key and loose_key in by_loose:
            hit, tier = by_loose[loose_key][0], "strong"
        else:
            best, best_ratio = None, 0.0
            for entry in gfn_epic:
                ratio = max(
                    _ratio(exact_key, norm(entry["title"])),
                    _ratio(loose_key, norm_loose(entry["title"])),
                )
                if ratio > best_ratio:
                    best, best_ratio = entry, ratio
            if best_ratio >= STRONG_RATIO:
                hit, tier, score = best, "strong", best_ratio
            elif best_ratio >= REVIEW_RATIO:
                hit, tier, score = best, "review", best_ratio

        if hit is None:
            continue

        matches.append(
            {
                "epic_title": game["title"],
                "epic_app_name": game["app_name"],
                "gfn_title": hit["title"],
                "gfn_id": hit["gfn_id"],
                "optimized": hit["optimized"],
                "tier": tier,
                "score": round(score, 3),
            }
        )
        used.add(hit["gfn_id"])

    # Several Epic entries can collapse onto one GFN entry; keep the best tier.
    best_by_gfn = {}
    for match in matches:
        current = best_by_gfn.get(match["gfn_id"])
        key = (_TIER_RANK[match["tier"]], -match["score"])
        if current is None or key < (_TIER_RANK[current["tier"]], -current["score"]):
            best_by_gfn[match["gfn_id"]] = match

    deduped = sorted(
        best_by_gfn.values(),
        key=lambda m: (_TIER_RANK[m["tier"]], m["gfn_title"].lower()),
    )
    unmatched = [e for e in gfn_epic if e["gfn_id"] not in used]
    return deduped, unmatched
