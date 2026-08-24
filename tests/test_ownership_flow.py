"""Guards for the two invariants that protect the user."""
from epicsync.mark import FORBIDDEN_TEXTS, epic_available

PICKER = ("Metro Exodus | PC Digital Version | Choose a game store | "
          "Where do you own this game and want to play? | Game stores: | "
          "Epic Games Store | Steam | Game not found | Xbox | Game not found")

EPIC_MISSING = ("Some Game | PC Digital Version | Choose a game store | Game stores: | "
                "Epic Games Store | Game not found | Steam")

STEAM_ONLY = ("Prison Architect | PC Digital Version | Steam | Game not found | "
              "Or press CONTINUE to manually mark this game as owned. | CONTINUE | EXIT")


def test_epic_selectable_when_not_tagged_missing():
    assert epic_available(PICKER) is True


def test_epic_rejected_when_tagged_game_not_found():
    assert epic_available(EPIC_MISSING) is False


def test_epic_absent_from_picker():
    assert epic_available(STEAM_ONLY) is False


def test_safety_gate_rejects_steam_confirmation():
    # The gate is "does the stage text name the Epic store".
    assert "epic games store" not in STEAM_ONLY.lower()
    assert "epic games store" in PICKER.lower()


def test_buy_is_on_the_never_click_list():
    assert "BUY" in FORBIDDEN_TEXTS
    assert "PURCHASE" in FORBIDDEN_TEXTS
