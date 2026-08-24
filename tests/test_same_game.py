"""Ownership matching for the audit.

The audit decides whether a GFN ownership claim is backed by the real Epic
library. A false "not owned" leads to deleting a legitimate claim, so these
cases are deliberately biased toward recognizing a match.
"""
import pytest

from epicsync.normalize import same_game

# Storefront and library titles differ in ways that are not real differences.
SAME = [
    ("Metro Exodus PC Enhanced Edition", "Metro Exodus Enhanced Edition"),
    ("Zombie Army 4", "Zombie Army 4 Dead War"),
    ("The Textorcist: The Story of Ray Bibbia", "The Textorcist"),
    ("The Falconeer Revolution Remaster", "The Falconeer"),
    ("Rustler", "Rustler - Grand Theft Horse"),
    ("Hundred Days", "Hundred Days - Winemaking Simulator"),
    ("Alan Wake", "Alan Wake Remastered"),
    ("ALAN WAKE™", "Alan Wake"),
]

# Genuinely different products that must never be collapsed.
DIFFERENT = [
    ("Torchlight", "Torchlight II"),
    ("Battlefield 6", "Battlefield"),
    ("Metro: 2033 Redux", "Metro Exodus"),
    ("Shadow Tactics - Aiko's Choice", "Shadow Tactics: Blades of the Shogun"),
    ("Realm Royale Reforged", "Breakout: Recharged"),
    ("INSIDE", "Inside"),  # identical after norm, handled by the equality path
]


@pytest.mark.parametrize(("left", "right"), SAME)
def test_recognised_as_same_game(left, right):
    assert same_game(left, right) is True
    assert same_game(right, left) is True, "must be symmetric"


@pytest.mark.parametrize(("left", "right"), DIFFERENT[:-1])
def test_distinct_products_stay_distinct(left, right):
    assert same_game(left, right) is False
    assert same_game(right, left) is False, "must be symmetric"


def test_sequel_numbers_block_a_match():
    # The guard that stops "Battlefield" from absorbing every sequel.
    assert same_game("Battlefield", "Battlefield 6") is False
    assert same_game("Portal", "Portal 2") is False


def test_single_word_must_lead_the_longer_title():
    assert same_game("Rustler", "Rustler - Grand Theft Horse") is True
    assert same_game("Horse", "Rustler - Grand Theft Horse") is False


def test_empty_titles_never_match():
    assert same_game("", "Anything") is False
    assert same_game("Anything", "") is False
