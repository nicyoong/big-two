from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from bot import BotBrain, Move, PassMove, generate_legal_plays
from card import Card, Rank
from combo_preserving_bot import _remove_cards, _would_break_pair, _would_break_triple, score_move_level_2
from control_card_bot import control_card_penalty, should_pass
from heuristics import (
    ENDGAME_CARD_SHED_BONUS,
    ENDGAME_CONTROL_REDUCTION_FACTOR,
    ENDGAME_SINGLE_PENALTY,
    ENDGAME_STRONG_OUT_BONUS,
    ENDGAME_WEAK_OUT_PENALTY,
    MIDDLE_FIVE_CARD_BONUS,
    MIDDLE_LOW_ORPHAN_BASE_PENALTY,
    MIDDLE_LOW_ORPHAN_RANK_PENALTY,
    MIDDLE_NO_CONTROL_PENALTY,
    OPENING_BREAK_PAIR_PENALTY,
    OPENING_BREAK_TRIPLE_PENALTY,
    OPENING_LOW_ORPHAN_BONUS,
    OPENING_PENALTY_ACE,
    OPENING_PENALTY_TWO,
    OPENING_WEAK_FIVE_BONUS,
    PHASE_THRESHOLD_MIDDLE,
    PHASE_THRESHOLD_OPENING,
)
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
    if my_card_count >= PHASE_THRESHOLD_OPENING:
        return GamePhase.OPENING
    if my_card_count >= PHASE_THRESHOLD_MIDDLE:
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
        score += OPENING_WEAK_FIVE_BONUS
    # Opening: preserve 2s and Aces aggressively for later control.
    score += OPENING_PENALTY_TWO * sum(1 for card in move.cards if card.rank == Rank.TWO)
    score += OPENING_PENALTY_ACE * sum(1 for card in move.cards if card.rank == Rank.ACE)
    # Opening: avoid damaging useful pairs/triples/five-card structures early.
    score += OPENING_BREAK_PAIR_PENALTY if _would_break_pair(list(observation.my_hand), move.cards) else 0
    score += OPENING_BREAK_TRIPLE_PENALTY if _would_break_triple(list(observation.my_hand), move.cards) else 0
    # Opening: get rid of awkward low orphan singles when possible.
    score += OPENING_LOW_ORPHAN_BONUS * len(_low_orphan_cards_in_move(list(observation.my_hand), move.cards))
    return score


def _middle_adjustment(move: Move, remaining_hand: list[Card]) -> int:
    # Middle: prioritize clean shape and avoid being left with scattered low singles.
    low_orphans = _low_orphan_cards(remaining_hand)
    score = sum(MIDDLE_LOW_ORPHAN_BASE_PENALTY + MIDDLE_LOW_ORPHAN_RANK_PENALTY * int(Rank.JACK - card.rank) for card in low_orphans)
    # Middle: five-card moves are welcome when they leave fewer awkward singles.
    if len(move.cards) == 5 and len(low_orphans) <= 1:
        score += MIDDLE_FIVE_CARD_BONUS
    # Middle: keep at least one control card if possible.
    if not any(card.rank in (Rank.ACE, Rank.TWO) for card in remaining_hand):
        score += MIDDLE_NO_CONTROL_PENALTY
    return score


def _endgame_adjustment(move: Move, remaining_hand: list[Card]) -> int:
    score = 0
    # Endgame: shedding cards matters twice as much.
    score += ENDGAME_CARD_SHED_BONUS * len(move.cards)
    # Endgame: leaving one strong out is good, leaving one weak out is risky.
    if len(remaining_hand) == 1:
        score += ENDGAME_STRONG_OUT_BONUS if remaining_hand[0].rank >= Rank.ACE else ENDGAME_WEAK_OUT_PENALTY
    # Endgame: avoid giving opponents a single-card chance when someone is nearly out.
    if len(move.cards) == 1:
        score += ENDGAME_SINGLE_PENALTY
    return score


def _phase_control_penalty(observation: "Observation", move: Move) -> int:
    penalty = control_card_penalty(move, observation)
    phase = get_game_phase(len(observation.my_hand))
    if phase == GamePhase.OPENING:
        return penalty
    if phase == GamePhase.MIDDLE:
        return penalty
    # Endgame: control cards are meant to be spent to finish.
    return penalty // ENDGAME_CONTROL_REDUCTION_FACTOR


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


def _rank_counts(cards: list[Card]) -> dict[Rank, int]:
    return {rank: sum(1 for card in cards if card.rank == rank) for rank in Rank}
