"""Choosing the right search result.

Opening the wrong game runs the ownership flow against it, so this matcher is
directional and strict - the opposite bias to the audit's `same_game`.
"""
import pytest

from epicsync.mark import pick_label
from epicsync.normalize import covers

LABELS = [
    "Airborne Kingdom",
    "Asteroids",
    "Borderlands 3",
    "Metro Exodus",
    "The Textorcist: The Story of Ray Bibbia",
    "Baldur's Gate: Enhanced Edition",
    "Torchlight II",
]


def test_exact_title_wins():
    assert pick_label(LABELS, "Borderlands 3") == "Borderlands 3"


def test_storefront_may_add_a_subtitle():
    assert pick_label(LABELS, "The Textorcist") == "The Textorcist: The Story of Ray Bibbia"


@pytest.mark.parametrize("wanted", [
    "Airborne Kingdom OST",                        # soundtrack, not the game
    "Airborne Kingdom Community Test Environment",  # test build, not the game
    "Asteroids: Recharged",                         # a different, newer game
])
def test_library_extras_never_open_the_base_game(wanted):
    assert pick_label(LABELS, wanted) is None


def test_sequel_is_not_opened_for_the_original():
    assert pick_label(LABELS, "Torchlight") is None


def test_no_labels_means_no_match():
    assert pick_label([], "Anything") is None


def test_covers_is_directional():
    # The storefront may be more verbose than the library, never the reverse.
    assert covers("The Textorcist: The Story of Ray Bibbia", "The Textorcist") is True
    assert covers("Airborne Kingdom", "Airborne Kingdom OST") is False
