from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from bot import BotBrain, Move, PassMove, generate_legal_plays
from card import Card, Rank
from rules import play_strength

if TYPE_CHECKING:
    from game import Observation


@dataclass
class ComboPreservingBot(BotBrain):
    def choose_move(self, observation: "Observation") -> Move | PassMove:
        legal_plays = generate_legal_plays(
            hand=observation.my_hand,
            current_play=observation.current_play,
            must_include=observation.must_include_card,
        )
        if not legal_plays:
            return PassMove()

        scored_moves = [
            (score_move_level_2(observation, Move(cards=list(cards))), cards)
            for cards in legal_plays
        ]
        _, best_cards = min(scored_moves, key=lambda scored_move: (scored_move[0], scored_move[1]))
        return Move(cards=list(best_cards))


def score_move_level_2(observation: "Observation", move: Move) -> int:
    hand = list(observation.my_hand)
    move_cards = list(move.cards)
    remaining_hand = _remove_cards(hand, move_cards)

    # Ending the hand is always the best available action.
    if not remaining_hand:
        return -1_000_000

    score = 0
    # Prefer moves that shed more cards.
    score -= 20 * len(move_cards)
    # Prefer weaker legal moves, especially when responding to a play.
    score += _normalized_move_strength(move_cards)
    # Avoid spending control cards unless the hand shape justifies it.
    score += 25 if any(card.rank == Rank.TWO for card in move_cards) else 0
    # Aces are strong late-game cards and should not be wasted cheaply.
    score += 10 if any(card.rank == Rank.ACE for card in move_cards) else 0
    # Kings are also useful high cards, but less valuable than Aces or 2s.
    score += 5 if any(card.rank == Rank.KING for card in move_cards) else 0
    # Avoid breaking a pair to play one of its cards as a weaker structure.
    score += 20 if _would_break_pair(hand, move_cards) else 0
    # Avoid breaking triples even more heavily than pairs.
    score += 30 if _would_break_triple(hand, move_cards) else 0
    # Account for how awkward the remaining hand looks after this move.
    score += evaluate_hand_badness(remaining_hand)
    return score


def evaluate_hand_badness(hand: list[Card]) -> int:
    rank_counts = _rank_counts(hand)
    orphan_singles = [card for card in hand if rank_counts[card.rank] == 1]
    pairs = sum(1 for count in rank_counts.values() if count >= 2)
    triples = sum(1 for count in rank_counts.values() if count >= 3)
    five_card_plays = sum(1 for cards in generate_legal_plays(hand=hand, current_play=None) if len(cards) == 5)
    control_cards = [card for card in hand if card.rank in (Rank.KING, Rank.ACE, Rank.TWO)]

    score = 0
    # More remaining cards means more work left to finish the hand.
    score += 10 * len(hand)
    # Orphan singles are harder to shed than cards grouped into combos.
    score += 8 * len(orphan_singles)
    # Low orphan singles are especially awkward because they rarely regain control.
    score += 10 * sum(1 for card in orphan_singles if card.rank < Rank.JACK)
    # Pairs preserve compact two-card plays.
    score -= 6 * pairs
    # Triples preserve compact three-card plays.
    score -= 8 * triples
    # Five-card plays are valuable ways to shed many cards at once.
    score -= 12 * five_card_plays
    # Control cards improve the chance of winning later tricks.
    score -= 5 * len(control_cards)
    return score


def _normalized_move_strength(cards: list[Card]) -> int:
    category_strength, tiebreaker = play_strength(cards)
    return category_strength * 10 + sum(tiebreaker)


def _remove_cards(hand: list[Card], cards: list[Card]) -> list[Card]:
    remaining = list(hand)
    for card in cards:
        remaining.remove(card)
    return sorted(remaining)


def _would_break_pair(hand: list[Card], move_cards: list[Card]) -> bool:
    hand_rank_counts = _rank_counts(hand)
    move_rank_counts = _rank_counts(move_cards)
    return any(hand_rank_counts[rank] >= 2 and 0 < move_count < 2 for rank, move_count in move_rank_counts.items())


def _would_break_triple(hand: list[Card], move_cards: list[Card]) -> bool:
    hand_rank_counts = _rank_counts(hand)
    move_rank_counts = _rank_counts(move_cards)
    return any(hand_rank_counts[rank] >= 3 and 0 < move_count < 3 for rank, move_count in move_rank_counts.items())


def _rank_counts(cards: list[Card]) -> dict[Rank, int]:
    return {rank: sum(1 for card in cards if card.rank == rank) for rank in Rank}
