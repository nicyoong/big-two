from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from bot import BotBrain, Move, PassMove, generate_legal_plays
from card import Card, Rank
from combo_preserving_bot import evaluate_hand_badness, score_move_level_2
from rules import PlayCategory, classify_play

if TYPE_CHECKING:
    from game import Observation


@dataclass
class ControlCardBot(BotBrain):
    def choose_move(self, observation: "Observation") -> Move | PassMove:
        legal_plays = generate_legal_plays(
            hand=observation.my_hand,
            current_play=observation.current_play,
            must_include=observation.must_include_card,
        )
        if not legal_plays:
            return PassMove()

        scored_moves = [
            (
                score_move_level_2(observation, Move(cards=list(cards)))
                + control_card_penalty(Move(cards=list(cards)), observation),
                cards,
            )
            for cards in legal_plays
        ]
        _, best_cards = min(scored_moves, key=lambda scored_move: (scored_move[0], scored_move[1]))
        best_move = Move(cards=list(best_cards))
        if should_pass(observation, best_move):
            return PassMove()
        return best_move


def is_control_card(card: Card, observation: "Observation") -> bool:
    if card.rank in (Rank.TWO, Rank.ACE):
        return True
    if card.rank == Rank.KING:
        visible_high_cards = [card for card in observation.played_cards if card.rank in (Rank.ACE, Rank.TWO)]
        return len(visible_high_cards) >= 6
    return False


def control_card_penalty(move: Move, observation: "Observation") -> int:
    if _move_wins_immediately(move, observation):
        return 0

    penalty = 0
    # 2s are the most precious single-card controls.
    penalty += 80 * sum(1 for card in move.cards if card.rank == Rank.TWO)
    # Aces are strong controls, but less absolute than 2s.
    penalty += 35 * sum(1 for card in move.cards if card.rank == Rank.ACE)
    # Kings are useful late controls in some visible-card states.
    penalty += 15 * sum(1 for card in move.cards if card.rank == Rank.KING)
    # High pairs and triples can take important multi-card tricks.
    penalty += _high_group_penalty(move)
    # Very strong five-card hands should not be spent casually.
    penalty += _strong_five_card_penalty(move)

    if is_urgent_situation(observation):
        penalty //= 4
    elif player_is_near_win(observation):
        penalty //= 2

    if move_takes_control(move, observation) and _remaining_hand_is_strong(move, observation):
        penalty //= 2

    return penalty


def is_urgent_situation(observation: "Observation") -> bool:
    return player_is_near_win(observation) or any(
        seat_id != observation.my_seat_id and count == 1
        for seat_id, count in observation.card_counts_by_seat.items()
    )


def player_is_near_win(observation: "Observation") -> bool:
    return len(observation.my_hand) <= 3


def move_takes_control(move: Move, observation: "Observation") -> bool:
    return bool(move.cards) and (
        observation.is_starting_new_trick or observation.current_play is not None
    )


def should_pass(observation: "Observation", best_move: Move) -> bool:
    if observation.is_starting_new_trick:
        return False
    if _move_wins_immediately(best_move, observation):
        return False
    if any(
        seat_id != observation.my_seat_id and count == 1
        for seat_id, count in observation.card_counts_by_seat.items()
    ):
        return False

    penalty = control_card_penalty(best_move, observation)
    if penalty >= 60 and not player_is_near_win(observation):
        return True
    if _beating_current_play_is_too_expensive(best_move, observation):
        return True
    return False


def _move_wins_immediately(move: Move, observation: "Observation") -> bool:
    return len(move.cards) == len(observation.my_hand)


def _high_group_penalty(move: Move) -> int:
    if len(move.cards) not in (2, 3):
        return 0
    play_rank = classify_play(move.cards)
    if play_rank.category == PlayCategory.PAIR and move.cards[0].rank >= Rank.ACE:
        return 30
    if play_rank.category == PlayCategory.TRIPLE and move.cards[0].rank >= Rank.KING:
        return 45
    return 0


def _strong_five_card_penalty(move: Move) -> int:
    if len(move.cards) != 5:
        return 0
    play_rank = classify_play(move.cards)
    if play_rank.category in (PlayCategory.FOUR_OF_A_KIND, PlayCategory.STRAIGHT_FLUSH):
        return 50
    if play_rank.category == PlayCategory.FULL_HOUSE and max(card.rank for card in move.cards) >= Rank.ACE:
        return 25
    return 0


def _remaining_hand_is_strong(move: Move, observation: "Observation") -> bool:
    remaining = list(observation.my_hand)
    for card in move.cards:
        remaining.remove(card)
    return evaluate_hand_badness(remaining) <= 25 or any(
        is_control_card(card, observation) for card in remaining
    )


def _beating_current_play_is_too_expensive(move: Move, observation: "Observation") -> bool:
    if observation.current_play is None:
        return False
    return control_card_penalty(move, observation) >= 80
