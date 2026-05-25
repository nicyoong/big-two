from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from bot import BotBrain, Move, PassMove, generate_legal_plays
from card import Card, Rank
from combo_preserving_bot import score_move_level_2
from control_card_bot import control_card_penalty, should_pass
from rules import PlayCategory, classify_play

if TYPE_CHECKING:
    from game import Observation


class GamePhase(Enum):
    OPENING = "opening"
    MIDDLE = "middle"
    ENDGAME = "endgame"


@dataclass
class PhaseAwareBot(BotBrain):
    def choose_move(self, observation: "Observation") -> Move | PassMove:
        legal_plays = generate_legal_plays(
            hand=observation.my_hand,
            current_play=observation.current_play,
            must_include=observation.must_include_card,
        )
        if not legal_plays:
            return PassMove()

        scored_moves = []
        for cards in legal_plays:
            move = Move(cards=list(cards))
            remaining_hand = _remove_cards(list(observation.my_hand), move.cards)
            score = (
                score_move_level_2(observation, move)
                + _phase_control_penalty(observation, move)
                + phase_adjustment(observation, move, remaining_hand)
            )
            scored_moves.append((score, cards))

        best_score, best_cards = min(scored_moves, key=lambda scored_move: (scored_move[0], scored_move[1]))
        best_move = Move(cards=list(best_cards))
        if _phase_should_pass(observation, best_move, best_score):
            return PassMove()
        return best_move


def get_game_phase(my_card_count: int) -> GamePhase:
    if my_card_count >= 9:
        return GamePhase.OPENING
    if my_card_count >= 4:
        return GamePhase.MIDDLE
    return GamePhase.ENDGAME


def phase_adjustment(observation: "Observation", move: Move, remaining_hand: list[Card]) -> int:
    phase = get_game_phase(len(observation.my_hand))
    if phase == GamePhase.OPENING:
        return _opening_adjustment(observation, move)
    if phase == GamePhase.MIDDLE:
        return _middle_adjustment(move, remaining_hand)
    return _endgame_adjustment(move, remaining_hand)


def _opening_adjustment(observation: "Observation", move: Move) -> int:
    score = 0
    # Opening: weak five-card hands are good leads because they shed cards without spending controls.
    if observation.is_starting_new_trick and len(move.cards) == 5 and _is_weak_five_card_play(move):
        score -= 25
    # Opening: preserve 2s and Aces aggressively for later control.
    score += 40 * sum(1 for card in move.cards if card.rank == Rank.TWO)
    score += 20 * sum(1 for card in move.cards if card.rank == Rank.ACE)
    # Opening: avoid damaging useful pairs/triples/five-card structures early.
    score += 30 if _would_break_pair(list(observation.my_hand), move.cards) else 0
    score += 45 if _would_break_triple(list(observation.my_hand), move.cards) else 0
    # Opening: get rid of awkward low orphan singles when possible.
    score -= 10 * len(_low_orphan_cards_in_move(list(observation.my_hand), move.cards))
    return score


def _middle_adjustment(move: Move, remaining_hand: list[Card]) -> int:
    # Middle: prioritize clean shape and avoid being left with scattered low singles.
    low_orphans = _low_orphan_cards(remaining_hand)
    score = sum(12 + 3 * int(Rank.JACK - card.rank) for card in low_orphans)
    # Middle: five-card moves are welcome when they leave fewer awkward singles.
    if len(move.cards) == 5 and len(low_orphans) <= 1:
        score -= 20
    # Middle: keep at least one control card if possible.
    if not any(card.rank in (Rank.ACE, Rank.TWO) for card in remaining_hand):
        score += 18
    return score


def _endgame_adjustment(move: Move, remaining_hand: list[Card]) -> int:
    score = 0
    # Endgame: shedding cards matters twice as much.
    score -= 20 * len(move.cards)
    # Endgame: leaving one strong out is good, leaving one weak out is risky.
    if len(remaining_hand) == 1:
        score += -35 if remaining_hand[0].rank >= Rank.ACE else 45
    # Endgame: avoid giving opponents a single-card chance when someone is nearly out.
    if len(move.cards) == 1:
        score += 30
    return score


def _phase_control_penalty(observation: "Observation", move: Move) -> int:
    penalty = control_card_penalty(move, observation)
    phase = get_game_phase(len(observation.my_hand))
    if phase == GamePhase.OPENING:
        return penalty
    if phase == GamePhase.MIDDLE:
        return penalty
    # Endgame: control cards are meant to be spent to finish.
    return penalty // 5


def _phase_should_pass(observation: "Observation", move: Move, score: int) -> bool:
    if get_game_phase(len(observation.my_hand)) == GamePhase.ENDGAME:
        return False
    return should_pass(observation, move, score)


def _is_weak_five_card_play(move: Move) -> bool:
    if len(move.cards) != 5:
        return False
    play_rank = classify_play(move.cards)
    return play_rank.category in (PlayCategory.STRAIGHT, PlayCategory.FLUSH)


def _low_orphan_cards(hand: list[Card]) -> list[Card]:
    rank_counts = _rank_counts(hand)
    return [card for card in hand if rank_counts[card.rank] == 1 and card.rank < Rank.JACK]


def _low_orphan_cards_in_move(hand: list[Card], move_cards: list[Card]) -> list[Card]:
    low_orphans = set(_low_orphan_cards(hand))
    return [card for card in move_cards if card in low_orphans]


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


def _remove_cards(hand: list[Card], cards: list[Card]) -> list[Card]:
    remaining = list(hand)
    for card in cards:
        remaining.remove(card)
    return sorted(remaining)
