import pytest

from card import Card, InvalidCardError, Rank, Suit, create_standard_deck


def test_rank_order_matches_big_two_rules() -> None:
    assert [rank.label for rank in Rank] == [
        "3",
        "4",
        "5",
        "6",
        "7",
        "8",
        "9",
        "10",
        "J",
        "Q",
        "K",
        "A",
        "2",
    ]
    assert Rank.THREE < Rank.FOUR < Rank.ACE < Rank.TWO


def test_suit_order_matches_big_two_rules() -> None:
    assert [suit.label for suit in Suit] == ["D", "C", "H", "S"]
    assert Suit.DIAMONDS < Suit.CLUBS < Suit.HEARTS < Suit.SPADES


def test_card_order_compares_rank_then_suit() -> None:
    assert Card.from_text("3D") < Card.from_text("3C")
    assert Card.from_text("3S") < Card.from_text("4D")
    assert Card.from_text("AS") < Card.from_text("2D")


def test_card_from_text_parses_case_and_whitespace() -> None:
    assert Card.from_text(" 10s ") == Card(Rank.TEN, Suit.SPADES)
    assert Card.from_text("td") == Card(Rank.TEN, Suit.DIAMONDS)
    assert Card.from_text("Qh") == Card(Rank.QUEEN, Suit.HEARTS)


def test_card_string_uses_canonical_labels() -> None:
    assert str(Card(Rank.TEN, Suit.SPADES)) == "10S"
    assert repr(Card(Rank.THREE, Suit.DIAMONDS)) == "Card.from_text('3D')"


@pytest.mark.parametrize("text", ["", "3", "1D", "11S", "3X", "ZZ", "10"])
def test_card_from_text_rejects_invalid_text(text: str) -> None:
    with pytest.raises(InvalidCardError):
        Card.from_text(text)


def test_card_from_text_rejects_non_string() -> None:
    with pytest.raises(InvalidCardError):
        Card.from_text(3)  # type: ignore[arg-type]


def test_card_rejects_non_enum_components() -> None:
    with pytest.raises(InvalidCardError):
        Card("3", Suit.DIAMONDS)  # type: ignore[arg-type]

    with pytest.raises(InvalidCardError):
        Card(Rank.THREE, "D")  # type: ignore[arg-type]


def test_create_standard_deck_returns_all_52_unique_cards_in_big_two_order() -> None:
    deck = create_standard_deck()

    assert len(deck) == 52
    assert len(set(deck)) == 52
    assert deck[0] == Card.from_text("3D")
    assert deck[-1] == Card.from_text("2S")
    assert deck == tuple(sorted(deck))
