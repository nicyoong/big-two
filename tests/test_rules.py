import pytest

from card import Card
from rules import InvalidPlayError, PlayCategory, can_beat, classify_play


def cards(*labels: str) -> tuple[Card, ...]:
    return tuple(Card.from_text(label) for label in labels)


def test_classifies_basic_play_categories() -> None:
    assert classify_play(cards("3D")).category == PlayCategory.SINGLE
    assert classify_play(cards("4D", "4S")).category == PlayCategory.PAIR
    assert classify_play(cards("5D", "5C", "5S")).category == PlayCategory.TRIPLE


def test_classifies_five_card_categories() -> None:
    assert classify_play(cards("3D", "4C", "5H", "6S", "7D")).category == PlayCategory.STRAIGHT
    assert classify_play(cards("3D", "5D", "7D", "9D", "JD")).category == PlayCategory.FLUSH
    assert classify_play(cards("6D", "6C", "6H", "9D", "9S")).category == PlayCategory.FULL_HOUSE
    assert classify_play(cards("8D", "8C", "8H", "8S", "3D")).category == PlayCategory.FOUR_OF_A_KIND
    assert classify_play(cards("9S", "10S", "JS", "QS", "KS")).category == PlayCategory.STRAIGHT_FLUSH


@pytest.mark.parametrize(
    "labels",
    [
        ("3D", "4D"),
        ("3D", "3C", "4D"),
        ("3D", "4C", "5H", "6S", "2D"),
        ("AD", "2C", "3H", "4S", "5D"),
        ("3D", "4C", "6H", "8S", "10D"),
    ],
)
def test_rejects_invalid_play_categories(labels: tuple[str, ...]) -> None:
    with pytest.raises(InvalidPlayError):
        classify_play(cards(*labels))


def test_compares_single_pair_and_triple_plays() -> None:
    assert can_beat(cards("4D"), cards("3S"))
    assert can_beat(cards("6D", "6C"), cards("5H", "5S"))
    assert can_beat(cards("7D", "7C", "7H"), cards("6D", "6C", "6H"))
    assert not can_beat(cards("5D", "5C"), cards("5H", "5S"))


def test_five_card_category_order_can_beat_higher_tiebreakers() -> None:
    straight = cards("3D", "4C", "5H", "6S", "7D")
    flush = cards("3D", "5D", "7D", "9D", "JD")
    full_house = cards("6D", "6C", "6H", "9D", "9S")
    four_kind = cards("8D", "8C", "8H", "8S", "3D")
    straight_flush = cards("9S", "10S", "JS", "QS", "KS")

    assert can_beat(flush, straight)
    assert can_beat(full_house, flush)
    assert can_beat(four_kind, full_house)
    assert can_beat(straight_flush, four_kind)


def test_five_card_same_category_uses_tiebreakers() -> None:
    assert can_beat(cards("4D", "5C", "6H", "7S", "8D"), cards("3D", "4C", "5H", "6S", "7D"))
    assert can_beat(cards("3S", "5S", "7S", "9S", "QS"), cards("3D", "5D", "7D", "9D", "JD"))
    assert can_beat(cards("7D", "7C", "7H", "4D", "4S"), cards("6D", "6C", "6H", "9D", "9S"))
