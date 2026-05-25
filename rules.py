from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import IntEnum

from card import Card, Rank


class InvalidPlayError(ValueError):
    """Raised when cards do not form a valid Big Two play."""


class PlayCategory(IntEnum):
    SINGLE = 0
    PAIR = 1
    TRIPLE = 2
    STRAIGHT = 3
    FLUSH = 4
    FULL_HOUSE = 5
    FOUR_OF_A_KIND = 6
    STRAIGHT_FLUSH = 7


@dataclass(frozen=True)
class PlayRank:
    category: PlayCategory
    card_count: int
    tiebreaker: tuple[int, ...]


def classify_play(cards: tuple[Card, ...] | list[Card]) -> PlayRank:
    normalized = tuple(sorted(cards))
    if len(normalized) not in (1, 2, 3, 5):
        raise InvalidPlayError("A play must contain 1, 2, 3, or 5 cards")
    if len(set(normalized)) != len(normalized):
        raise InvalidPlayError("A play cannot contain duplicate cards")

    card_count = len(normalized)
    rank_counts = Counter(card.rank for card in normalized)

    if card_count == 1:
        return PlayRank(PlayCategory.SINGLE, card_count, _cards_tiebreaker(normalized))

    if card_count == 2:
        if len(rank_counts) != 1:
            raise InvalidPlayError("Two-card plays must be a pair")
        return PlayRank(PlayCategory.PAIR, card_count, _cards_tiebreaker(normalized))

    if card_count == 3:
        if len(rank_counts) != 1:
            raise InvalidPlayError("Three-card plays must be a triple")
        return PlayRank(PlayCategory.TRIPLE, card_count, _cards_tiebreaker(normalized))

    return _classify_five_card_play(normalized, rank_counts)


def can_beat(candidate: tuple[Card, ...] | list[Card], current: tuple[Card, ...] | list[Card]) -> bool:
    candidate_rank = classify_play(candidate)
    current_rank = classify_play(current)

    if candidate_rank.card_count != current_rank.card_count:
        return False

    if candidate_rank.card_count == 5 and candidate_rank.category != current_rank.category:
        return candidate_rank.category > current_rank.category

    if candidate_rank.category != current_rank.category:
        return False

    return candidate_rank.tiebreaker > current_rank.tiebreaker


def play_strength(cards: tuple[Card, ...] | list[Card]) -> tuple[int, tuple[int, ...]]:
    play_rank = classify_play(cards)
    return (int(play_rank.category), play_rank.tiebreaker)


def _classify_five_card_play(
    cards: tuple[Card, ...],
    rank_counts: Counter[Rank],
) -> PlayRank:
    is_flush = len({card.suit for card in cards}) == 1
    is_straight = _is_straight(cards)
    counts = sorted(rank_counts.values(), reverse=True)

    if is_straight and is_flush:
        return PlayRank(PlayCategory.STRAIGHT_FLUSH, 5, _straight_tiebreaker(cards))
    if counts == [4, 1]:
        four_rank = _rank_with_count(rank_counts, 4)
        kicker = next(card for card in cards if card.rank != four_rank)
        return PlayRank(
            PlayCategory.FOUR_OF_A_KIND,
            5,
            (int(four_rank), _card_value(kicker)),
        )
    if counts == [3, 2]:
        return PlayRank(PlayCategory.FULL_HOUSE, 5, (int(_rank_with_count(rank_counts, 3)),))
    if is_flush:
        return PlayRank(PlayCategory.FLUSH, 5, _cards_tiebreaker(cards))
    if is_straight:
        return PlayRank(PlayCategory.STRAIGHT, 5, _straight_tiebreaker(cards))

    raise InvalidPlayError("Five-card plays must be straight, flush, full house, four-of-a-kind, or straight flush")


def _is_straight(cards: tuple[Card, ...]) -> bool:
    ranks = sorted({card.rank for card in cards})
    if len(ranks) != 5:
        return False
    if Rank.TWO in ranks:
        return False

    rank_values = [int(rank) for rank in ranks]
    return rank_values == list(range(rank_values[0], rank_values[0] + 5))


def _straight_tiebreaker(cards: tuple[Card, ...]) -> tuple[int, int]:
    high_card = max(cards)
    return (int(high_card.rank), int(high_card.suit))


def _cards_tiebreaker(cards: tuple[Card, ...]) -> tuple[int, ...]:
    values: list[int] = []
    for card in sorted(cards, reverse=True):
        values.append(int(card.rank))
        values.append(int(card.suit))
    return tuple(values)


def _card_value(card: Card) -> int:
    return int(card.rank) * 4 + int(card.suit)


def _rank_with_count(rank_counts: Counter[Rank], count: int) -> Rank:
    for rank, rank_count in rank_counts.items():
        if rank_count == count:
            return rank
    raise InvalidPlayError(f"No rank appears {count} times")
