from epicsync.catalog import epic_titles

CATALOG = [
    {"id": 1, "title": "Epic Game", "store": "Epic", "status": "AVAILABLE"},
    {"id": 2, "title": "Steam Game", "store": "Steam", "status": "AVAILABLE"},
    {"id": 3, "title": "Retired", "store": "Epic", "status": "REMOVED"},
    {"id": 4, "title": "Default Status", "store": "Epic"},
]


def test_keeps_only_available_epic_entries():
    titles = [e["title"] for e in epic_titles(CATALOG)]
    assert titles == ["Epic Game", "Default Status"]


def test_shape_is_normalised():
    entry = epic_titles(CATALOG)[0]
    assert set(entry) == {"gfn_id", "title", "sort_name", "publisher", "genres", "optimized"}
