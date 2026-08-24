from epicsync.normalize import norm, norm_loose


def test_strips_trademark_and_case():
    assert norm("ALAN WAKE™") == "alan wake"
    assert norm("Rocket League®") == "rocket league"


def test_strips_apostrophes_and_punctuation():
    assert norm("Alan Wake's American Nightmare") == "alan wakes american nightmare"
    assert norm("Tom Clancy\u2019s The Division\u2122 2") == "tom clancys the division 2"


def test_ampersand_becomes_word():
    assert norm("Rock & Roll") == "rock and roll"


def test_loose_strips_edition_suffixes():
    assert norm_loose("Absolute Drift: Zen Edition") == "absolute drift"
    assert norm_loose("Alan Wake Remastered") == "alan wake"


def test_loose_strips_final_cut():
    # Regression: this pair was missed and silently dropped a real match.
    assert norm_loose("Disco Elysium - The Final Cut") == norm_loose("Disco Elysium")


def test_loose_keeps_distinct_products_apart():
    # "Redux" is a genuinely different product; it must not be collapsed.
    assert norm_loose("Metro: 2033 Redux") != norm_loose("Metro Exodus")


def test_empty_input():
    assert norm("") == ""
    assert norm_loose("") == ""
