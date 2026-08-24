"""Game-title normalization.

Two levels are used when matching an Epic library against the GFN catalog:

``norm()``
    Safe normalization - case, accents, punctuation, trademark symbols.
    An exact match here is treated as high confidence.

``norm_loose()``
    Also strips edition and storefront suffixes, so ``Absolute Drift``
    matches ``Absolute Drift: Zen Edition``. Editions can be genuinely
    different products, so these matches are reported at lower confidence.
"""
import re
import unicodedata

_STORE_SUFFIXES = (
    "the epic games store",
    "epic games store",
    "epic games",
)

_EDITION_TOKENS = (
    "game of the year edition", "game of the year", "goty edition", "goty",
    "definitive edition", "complete edition", "enhanced edition",
    "deluxe edition", "ultimate edition", "special edition", "gold edition",
    "premium edition", "anniversary edition", "legendary edition",
    "director's cut", "directors cut", "the final cut", "final cut",
    "remastered", "remaster", "zen edition", "standard edition",
    "digital edition", "pc edition", "windows edition",
)

_TRAILING_ROMAN = {
    " i": " 1", " ii": " 2", " iii": " 3", " iv": " 4", " v": " 5",
    " vi": " 6", " vii": " 7", " viii": " 8", " ix": " 9", " x": " 10",
}


def _strip_accents(value: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(ch)
    )


def norm(title: str) -> str:
    """Lower-case, de-accent and strip punctuation from a title."""
    if not title:
        return ""
    text = _strip_accents(str(title).lower())
    text = text.replace("&", " and ")
    text = re.sub(r"[™®©]", " ", text)   # (TM) (R) (C)
    text = re.sub(r"[\u2018\u2019\u02bc]", "'", text)   # smart quotes
    text = text.replace("'", "")                        # "wake's" -> "wakes"
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def norm_loose(title: str) -> str:
    """``norm()`` plus removal of edition and storefront suffixes."""
    text = norm(title)
    for suffix in _STORE_SUFFIXES:
        text = text.replace(norm(suffix), " ")
    for token in _EDITION_TOKENS:
        text = text.replace(norm(token), " ")
    text = re.sub(r"\bedition\b", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    for roman, arabic in _TRAILING_ROMAN.items():
        if text.endswith(roman):
            return text[: -len(roman)] + arabic
    return text


# Words that carry no identity on their own; ignored when comparing token sets.
_FILLER = {"the", "a", "an", "of", "and", "pc", "edition", "game"}


def token_list(title: str):
    """Meaningful words of a title, in order."""
    return [w for w in norm_loose(title).split() if w and w not in _FILLER]


def tokens(title: str):
    """Meaningful words of a title, for subset comparison."""
    return set(token_list(title))


def _is_sequel_marker(token: str) -> bool:
    """A bare number or roman numeral distinguishes sequels, not editions."""
    return token.isdigit() or token in {"i", "ii", "iii", "iv", "v",
                                        "vi", "vii", "viii", "ix", "x"}


def covers(label: str, wanted: str) -> bool:
    """True when ``label`` names the same product as ``wanted``, possibly with
    extra words.

    Directional on purpose. Storefronts publish fuller titles than libraries do,
    so a GFN result may add a subtitle:

        wanted "The Textorcist"  ->  label "The Textorcist: The Story of ..."

    The reverse is not safe. A library entry carrying extra words is usually a
    different product, and treating it as a match opens the wrong game:

        wanted "Airborne Kingdom OST"  ->  label "Airborne Kingdom"   (rejected)
        wanted "Asteroids: Recharged"  ->  label "Asteroids"          (rejected)
    """
    if norm(label) == norm(wanted) or norm_loose(label) == norm_loose(wanted):
        return True

    label_tokens, wanted_tokens = tokens(label), tokens(wanted)
    if not label_tokens or not wanted_tokens:
        return False
    if not wanted_tokens <= label_tokens:
        return False
    if any(_is_sequel_marker(token) for token in label_tokens - wanted_tokens):
        return False

    if len(wanted_tokens) >= 2:
        return True
    only = next(iter(wanted_tokens))
    ordered = token_list(label)
    return len(only) >= 5 and bool(ordered) and ordered[0] == only


def same_game(left: str, right: str) -> bool:
    """True when two titles almost certainly refer to the same product.

    Deliberately generous. This backs the ownership audit, where a false
    "you do not own this" would delete a legitimate ownership record, while a
    missed one merely leaves a game that will not launch. Storefront titles
    routinely differ from library titles by a subtitle or a stray word:

        "The Textorcist"                vs "The Textorcist: The Story of ..."
        "Zombie Army 4 Dead War"        vs "Zombie Army 4"
        "Metro Exodus Enhanced Edition" vs "Metro Exodus PC Enhanced Edition"

    Generosity stops at sequels: the extra words may not contain a bare number
    or roman numeral, so "Battlefield" never absorbs "Battlefield 6".
    """
    if norm(left) == norm(right) or norm_loose(left) == norm_loose(right):
        return True

    left_tokens, right_tokens = tokens(left), tokens(right)
    if not left_tokens or not right_tokens:
        return False

    smaller, larger = sorted((left_tokens, right_tokens), key=len)
    if not smaller <= larger:
        return False

    extra = larger - smaller
    if any(_is_sequel_marker(token) for token in extra):
        return False

    if len(smaller) >= 2:
        return True

    # A single word identifies a game when it leads the longer title:
    # "Rustler" -> "Rustler - Grand Theft Horse". The floor only rules out
    # very short words; the sequel guard above does the real work.
    only = next(iter(smaller))
    longer_title = left if larger is left_tokens else right
    ordered = token_list(longer_title)
    return len(only) >= 5 and bool(ordered) and ordered[0] == only
