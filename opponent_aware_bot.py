from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from bot import BotBrain, Move, PassMove, generate_legal_plays
from card import Card, Rank
from combo_preserving_bot import score_move_level_2
from control_card_bot import control_card_penalty
from game import recently_passed_on_kind, recently_passed_on_size
from phase_aware_bot import phase_adjustment
from rules import PlayCategory, classify_play

if TYPE_CHECKING:
    from game import Observation


@dataclass
class OpponentAwareBot(BotBrain):
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
                + control_card_penalty(move, observation)
                + phase_adjustment(observation, move, remaining_hand)
                + opponent_adjustment(observation, move, remaining_hand)
            )
            scored_moves.append((score, cards))

        _, best_cards = min(scored_moves, key=lambda scored_move: (scored_move[0], scored_move[1]))
        return Move(cards=list(best_cards))


def opponent_danger(observation: "Observation", seat_id: str) -> int:
    if seat_id == observation.my_seat_id:
        return 0
    card_count = observation.card_counts_by_seat.get(seat_id)
    if card_count == 1:
        return 100
    if card_count == 2:
        return 60
    if card_count in (3, 4):
        return 30
    return 0


def any_opponent_has_one_card(observation: "Observation") -> bool:
    return any(
        seat_id != observation.my_seat_id and count == 1
        for seat_id, count in observation.card_counts_by_seat.items()
    )


def dangerous_opponents(observation: "Observation") -> list[str]:
    return [
        seat_id
        for seat_id in observation.seat_order
        if opponent_danger(observation, seat_id) > 0
    ]


def next_seat_id(observation: "Observation", seat_id: str) -> str:
    seat_order = observation.seat_order
    index = seat_order.index(seat_id)
    return seat_order[(index + 1) % len(seat_order)]


def next_player_is_dangerous(observation: "Observation") -> bool:
    # prompt says "if the next player has 1 card, be extra careful" 
    # and "next_player_is_dangerous(observation) -> bool" 
    # I'll implement it as "has 1 card" based on the strategic behavior rule.
    return observation.card_counts_by_seat.get(next_seat_id(observation, observation.my_seat_id)) == 1


def opponent_adjustment(observation: "Observation", move: Move, remaining_hand: list[Card]) -> int:
    score = 0
    play_rank = classify_play(move.cards)
    is_single = len(move.cards) == 1
    is_low_single = is_single and move.cards[0].rank < Rank.JACK
    is_multi_card = len(move.cards) in (2, 3, 5)

    # - If any opponent has 1 card, avoid starting a trick with a low single.
    # - If any opponent has 1 card, prefer pair/triple/five-card plays when starting.
    if observation.is_starting_new_trick and any_opponent_has_one_card(observation):
        if is_low_single:
            score += 80
        if is_multi_card:
            score -= 25

    # - If the next player has 1 card, be extra careful with singles.
    if next_player_is_dangerous(observation) and is_low_single:
        score += 100

    # - If an opponent has 2 cards, be cautious about starting weak pairs.
    if any(_opponent_card_count(observation, seat_id) == 2 for seat_id in observation.seat_order):
        if observation.is_starting_new_trick and _is_weak_pair(move):
            score += 35

    # - If forced to play a single while an opponent has 1 card, prefer higher singles.
    if any_opponent_has_one_card(observation) and is_single:
        # Penalize lower singles more than higher ones.
        # Rank.TWO is highest, Rank.THREE is lowest.
        score += int(Rank.TWO - move.cards[0].rank) * 2

    # - If a dangerous opponent recently passed on a play size or kind, slightly prefer that kind when starting.
    for seat_id in dangerous_opponents(observation):
        if recently_passed_on_size(observation, seat_id, len(move.cards)):
            score -= 15
        if recently_passed_on_kind(observation, seat_id, play_rank.category.name.lower()):
            score -= 10

    return score


def _is_weak_pair(move: Move) -> bool:
    if len(move.cards) != 2:
        return False
    play_rank = classify_play(move.cards)
    return play_rank.category == PlayCategory.PAIR and move.cards[0].rank < Rank.JACK


def _opponent_card_count(observation: "Observation", seat_id: str) -> int | None:
    if seat_id == observation.my_seat_id:
        return None
    return observation.card_counts_by_seat.get(seat_id)


def _remove_cards(hand: list[Card], cards: list[Card]) -> list[Card]:
    remaining = list(hand)
    for card in cards:
        remaining.remove(card)
    return sorted(remaining)
