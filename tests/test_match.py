from epicsync.match import build


def gfn(title, gfn_id, optimized=False):
    return {"title": title, "gfn_id": gfn_id, "optimized": optimized}


def epic(title, app_name="a"):
    return {"title": title, "app_name": app_name}


CATALOG = [
    gfn("Alan Wake", 1),
    gfn("Alan Wake's American Nightmare", 2),
    gfn("Absolute Drift: Zen Edition", 3),
    gfn("Rocket League®", 4),
    gfn("Torchlight", 5),
    gfn("Torchlight II", 6),
    gfn("Disco Elysium", 7),
]


def test_exact_match_survives_symbols_and_case():
    matches, _ = build([epic("ALAN WAKE™")], CATALOG)
    assert len(matches) == 1
    assert matches[0]["gfn_title"] == "Alan Wake"
    assert matches[0]["tier"] == "exact"


def test_edition_difference_is_strong_not_exact():
    matches, _ = build([epic("Absolute Drift")], CATALOG)
    assert matches[0]["gfn_title"] == "Absolute Drift: Zen Edition"
    assert matches[0]["tier"] == "strong"


def test_final_cut_matches_base_title():
    matches, _ = build([epic("Disco Elysium - The Final Cut")], CATALOG)
    assert matches[0]["gfn_title"] == "Disco Elysium"


def test_sequel_does_not_match_original():
    # Owning Torchlight II must never mark Torchlight.
    matches, _ = build([epic("Torchlight II")], CATALOG)
    assert [m["gfn_id"] for m in matches] == [6]


def test_unrelated_title_is_not_matched():
    matches, _ = build([epic("Some Game That Does Not Exist 9000")], CATALOG)
    assert matches == []


def test_one_gfn_entry_is_not_returned_twice():
    matches, _ = build([epic("Alan Wake", "a1"), epic("ALAN WAKE™", "a2")], CATALOG)
    assert len(matches) == 1


def test_unmatched_catalog_entries_are_reported():
    matches, unmatched = build([epic("Alan Wake")], CATALOG)
    assert len(matches) == 1
    assert len(unmatched) == len(CATALOG) - 1
