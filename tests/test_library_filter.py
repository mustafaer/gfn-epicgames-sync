from epicsync.epiclib import filter_games


def entry(title, categories, **extra):
    return dict(
        {"app_name": title.lower().replace(" ", "-"), "app_title": title,
         "metadata": {"categories": [{"path": c} for c in categories]},
         "asset_infos": {"Windows": {"namespace": "ns"}}},
        **extra,
    )


def test_keeps_real_games():
    raw = [entry("Real Game", ["public", "games", "applications"])]
    assert [g["title"] for g in filter_games(raw)] == ["Real Game"]


def test_drops_unreal_engine_marketplace_assets():
    # 115 of 261 entries on the reference account were asset packs.
    raw = [entry("ArchViz Explorer",
                 ["projects", "asset-format/game-engine", "type/format-item"])]
    assert filter_games(raw) == []


def test_drops_dlc():
    raw = [entry("Some DLC", ["games"], is_dlc=True)]
    assert filter_games(raw) == []


def test_drops_addons_category():
    raw = [entry("An Addon", ["games", "addons"])]
    assert filter_games(raw) == []


def test_sorted_case_insensitively():
    raw = [entry("zeta", ["games"]), entry("Alpha", ["games"])]
    assert [g["title"] for g in filter_games(raw)] == ["Alpha", "zeta"]
