from card import Card, Rank, Suit
from hand_analysis import (
    analyze_hand,
    count_control_cards,
    count_five_card_plays,
    count_pairs,
    count_triples,
    remove_cards,
    would_break_pair,
    would_break_triple,
)


def cards(*labels: str) -> list[Card]:
    return [Card.from_text(label) for label in labels]


def test_detects_pairs() -> None:
    hand = cards("3D", "3C", "4D", "5D")

    analysis = analyze_hand(hand)

    assert analysis.pairs == [cards("3D", "3C")]
    assert count_pairs(hand) == 1
    assert analysis.rank_counts[Rank.THREE] == 2


def test_detects_triples() -> None:
    hand = cards("4D", "4C", "4H", "7D")

    analysis = analyze_hand(hand)

    assert analysis.triples == [cards("4D", "4C", "4H")]
    assert count_triples(hand) == 1


def test_detects_five_card_hands() -> None:
    hand = cards("3D", "4C", "5H", "6S", "7D", "9D")

    analysis = analyze_hand(hand)

    assert count_five_card_plays(hand) >= 1
    assert cards("3D", "4C", "5H", "6S", "7D") in [list(play.cards) for play in analysis.five_card_plays]


def test_detects_twos_as_control_cards() -> None:
    hand = cards("2D", "2S", "AD", "KD", "QD")

    analysis = analyze_hand(hand)

    assert Card.from_text("2D") in analysis.control_cards
    assert Card.from_text("2S") in analysis.control_cards
    assert count_control_cards(hand) == 4


def test_detects_low_orphan_singles() -> None:
    hand = cards("3D", "4D", "4C", "10S", "JH")

    analysis = analyze_hand(hand)

    assert analysis.low_singles == cards("3D", "10S")


def test_remove_cards_works_correctly() -> None:
    hand = cards("3D", "4D", "5D")

    assert remove_cards(hand, cards("4D")) == cards("3D", "5D")


def test_would_break_pair_returns_true_when_playing_one_card_from_pair() -> None:
    hand = cards("8D", "8C", "9D")

    assert would_break_pair(hand, cards("8D"))
    assert not would_break_pair(hand, cards("8D", "8C"))
    assert not would_break_pair(hand, cards("9D"))


def test_would_break_triple_returns_true_when_playing_one_or_two_cards_from_triple() -> None:
    hand = cards("9D", "9C", "9H", "10D")

    assert would_break_triple(hand, cards("9D"))
    assert would_break_triple(hand, cards("9D", "9C"))
    assert not would_break_triple(hand, cards("9D", "9C", "9H"))
    assert not would_break_triple(hand, cards("10D"))


def test_counts_suits() -> None:
    analysis = analyze_hand(cards("3D", "4D", "5C"))

    assert analysis.suit_counts[Suit.DIAMONDS] == 2
    assert analysis.suit_counts[Suit.CLUBS] == 1
