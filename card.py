from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum


class CardError(ValueError):
    """Base exception for card-related validation errors."""


class InvalidCardError(CardError):
    """Raised when card text or components do not describe a valid card."""


class Rank(IntEnum):
    THREE = 0
    FOUR = 1
    FIVE = 2
    SIX = 3
    SEVEN = 4
    EIGHT = 5
    NINE = 6
    TEN = 7
    JACK = 8
    QUEEN = 9
    KING = 10
    ACE = 11
    TWO = 12

    @property
    def label(self) -> str:
        return _RANK_LABELS[self]

    @classmethod
    def from_label(cls, label: str) -> "Rank":
        try:
            return _RANK_BY_LABEL[label.upper()]
        except KeyError as exc:
            raise InvalidCardError(f"Invalid card rank: {label!r}") from exc


class Suit(IntEnum):
    DIAMONDS = 0
    CLUBS = 1
    HEARTS = 2
    SPADES = 3

    @property
    def label(self) -> str:
        return _SUIT_LABELS[self]

    @classmethod
    def from_label(cls, label: str) -> "Suit":
        try:
            return _SUIT_BY_LABEL[label.upper()]
        except KeyError as exc:
            raise InvalidCardError(f"Invalid card suit: {label!r}") from exc


@dataclass(frozen=True, order=True)
class Card:
    rank: Rank
    suit: Suit

    def __post_init__(self) -> None:
        if not isinstance(self.rank, Rank):
            raise InvalidCardError(f"Card rank must be a Rank, got {self.rank!r}")
        if not isinstance(self.suit, Suit):
            raise InvalidCardError(f"Card suit must be a Suit, got {self.suit!r}")

    @property
    def sort_key(self) -> tuple[int, int]:
        return (int(self.rank), int(self.suit))

    @classmethod
    def from_text(cls, text: str) -> "Card":
        if not isinstance(text, str):
            raise InvalidCardError(f"Card text must be a string, got {type(text).__name__}")

        normalized = text.strip().upper()
        if len(normalized) < 2:
            raise InvalidCardError(f"Invalid card text: {text!r}")

        rank_text = normalized[:-1]
        suit_text = normalized[-1]
        return cls(Rank.from_label(rank_text), Suit.from_label(suit_text))

    def __str__(self) -> str:
        return f"{self.rank.label}{self.suit.label}"

    def __repr__(self) -> str:
        return f"Card.from_text({str(self)!r})"


def create_standard_deck() -> tuple[Card, ...]:
    return tuple(Card(rank, suit) for rank in Rank for suit in Suit)


_RANK_LABELS: dict[Rank, str] = {
    Rank.THREE: "3",
    Rank.FOUR: "4",
    Rank.FIVE: "5",
    Rank.SIX: "6",
    Rank.SEVEN: "7",
    Rank.EIGHT: "8",
    Rank.NINE: "9",
    Rank.TEN: "10",
    Rank.JACK: "J",
    Rank.QUEEN: "Q",
    Rank.KING: "K",
    Rank.ACE: "A",
    Rank.TWO: "2",
}

_RANK_BY_LABEL: dict[str, Rank] = {
    **{label: rank for rank, label in _RANK_LABELS.items()},
    "T": Rank.TEN,
}

_SUIT_LABELS: dict[Suit, str] = {
    Suit.DIAMONDS: "D",
    Suit.CLUBS: "C",
    Suit.HEARTS: "H",
    Suit.SPADES: "S",
}

_SUIT_BY_LABEL: dict[str, Suit] = {label: suit for suit, label in _SUIT_LABELS.items()}
