from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from logic import generate_legal_plays
from card import Card, Rank, Suit
from game import Play
from rules import PlayCategory, classify_play, play_strength


@dataclass(frozen=True)
class HandAnalysis:
    singles: list[Card]
    pairs: list[list[Card]]
    triples: list[list[Card]]
    five_card_plays: list[Play]
    control_cards: list[Card]
    low_singles: list[Card]
    high_cards: list[Card]
    rank_counts: dict[Rank, int]
    suit_counts: dict[Suit, int]


def analyze_hand(hand: list[Card]) -> HandAnalysis:
    sorted_hand = sorted(hand)
    rank_counts = _rank_counts(sorted_hand)
    suit_counts = _suit_counts(sorted_hand)
    singles = [card for card in sorted_hand if rank_counts[card.rank] == 1]

    return HandAnalysis(
        singles=singles,
        pairs=_same_rank_groups(sorted_hand, 2),
        triples=_same_rank_groups(sorted_hand, 3),
        five_card_plays=_five_card_plays(sorted_hand),
        control_cards=_control_cards(sorted_hand),
        low_singles=[card for card in singles if card.rank < Rank.JACK],
        high_cards=[card for card in sorted_hand if card.rank >= Rank.KING],
        rank_counts=rank_counts,
        suit_counts=suit_counts,
    )


def count_pairs(hand: list[Card]) -> int:
    return len(analyze_hand(hand).pairs)


def count_triples(hand: list[Card]) -> int:
    return len(analyze_hand(hand).triples)


def count_five_card_plays(hand: list[Card]) -> int:
    return len(analyze_hand(hand).five_card_plays)


def count_control_cards(hand: list[Card]) -> int:
    return len(analyze_hand(hand).control_cards)


def remove_cards(hand: list[Card], cards: list[Card]) -> list[Card]:
    remaining = list(hand)
    for card in cards:
        remaining.remove(card)
    return sorted(remaining)


def would_break_pair(hand: list[Card], move_cards: list[Card]) -> bool:
    hand_rank_counts = _rank_counts(hand)
    move_rank_counts = _rank_counts(move_cards)
    return any(hand_rank_counts[rank] >= 2 and 0 < move_count < 2 for rank, move_count in move_rank_counts.items())


def would_break_triple(hand: list[Card], move_cards: list[Card]) -> bool:
    hand_rank_counts = _rank_counts(hand)
    move_rank_counts = _rank_counts(move_cards)
    return any(hand_rank_counts[rank] >= 3 and 0 < move_count < 3 for rank, move_count in move_rank_counts.items())


def _rank_counts(hand: list[Card]) -> dict[Rank, int]:
    return dict(Counter(card.rank for card in hand))


def _suit_counts(hand: list[Card]) -> dict[Suit, int]:
    return dict(Counter(card.suit for card in hand))


def _same_rank_groups(hand: list[Card], size: int) -> list[list[Card]]:
    cards_by_rank: dict[Rank, list[Card]] = defaultdict(list)
    for card in hand:
        cards_by_rank[card.rank].append(card)

    groups = []
    for rank in sorted(cards_by_rank):
        cards = sorted(cards_by_rank[rank])
        if len(cards) >= size:
            groups.append(cards[:size])
    return groups


def _five_card_plays(hand: list[Card]) -> list[Play]:
    plays: list[Play] = []
    for cards in generate_legal_plays(hand=hand, current_play=None):
        if len(cards) != 5:
            continue
        play_rank = classify_play(cards)
        if play_rank.category in {
            PlayCategory.STRAIGHT,
            PlayCategory.FLUSH,
            PlayCategory.FULL_HOUSE,
            PlayCategory.FOUR_OF_A_KIND,
            PlayCategory.STRAIGHT_FLUSH,
        }:
            plays.append(Play(seat_id="", cards=cards))
    return sorted(plays, key=lambda play: play_strength(play.cards))


def _control_cards(hand: list[Card]) -> list[Card]:
    return [card for card in sorted(hand) if card.rank in (Rank.KING, Rank.ACE, Rank.TWO)]
