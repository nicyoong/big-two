from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from bot import BotBrain, Move, PassMove, generate_legal_plays
from card import Card, Rank
from combo_preserving_bot import (
    _remove_cards,
    _would_break_pair,
    _would_break_triple,
    estimate_exit_groups,
    evaluate_remaining_hand,
    has_likely_control_card,
    score_move_level_2,
)
from heuristics import (
    BEST_SCORE_THRESHOLD_WORSE_HAND,
    BotPersonality,
    EXPENSIVE_MOVE_THRESHOLD,
    NEAR_WIN_REDUCTION_FACTOR,
    PENALTY_ACE,
    PENALTY_HIGH_FULL_HOUSE,
    PENALTY_HIGH_PAIR,
    PENALTY_HIGH_TRIPLE,
    PENALTY_KING,
    PENALTY_POWER_FIVE,
    PENALTY_TWO,
    STRONG_REMAINING_HAND_THRESHOLD,
    URGENT_REDUCTION_FACTOR,
)
from rules import PlayCategory, classify_play

if TYPE_CHECKING:
    from game import Observation


@dataclass
class ControlCardBot(BotBrain):
    personality: BotPersonality = field(default_factory=BotPersonality.create_random)

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
            score = score_move_level_2(observation, move) + control_card_penalty(move, observation, self.personality)
            scored_moves.append((score, cards))

        best_score, best_cards = min(scored_moves, key=lambda scored_move: (scored_move[0], scored_move[1]))
        best_move = Move(cards=list(best_cards))
        if should_pass(observation, best_move, best_score, self.personality):
            return PassMove()
        return best_move


def is_control_card(card: Card, observation: "Observation") -> bool:
    if card.rank in (Rank.TWO, Rank.ACE):
        return True
    if card.rank == Rank.KING:
        visible_high_cards = [
            played_card
            for event in observation.recent_events
            if _is_played_event(event)
            for played_card in event.cards
            if played_card.rank in (Rank.ACE, Rank.TWO)
        ]
        return len(visible_high_cards) >= 6
    return False


def control_card_penalty(move: Move, observation: "Observation", personality: BotPersonality | None = None) -> int:
    if _move_wins_immediately(move, observation):
        return 0

    p = personality or BotPersonality.create_default()
    penalty = 0
    # 2s are the most precious single-card controls.
    penalty += p.penalty_two * sum(1 for card in move.cards if card.rank == Rank.TWO)
    # Aces are strong controls, but less absolute than 2s.
    penalty += p.penalty_ace * sum(1 for card in move.cards if card.rank == Rank.ACE)
    # Kings are useful late controls in some visible-card states.
    penalty += PENALTY_KING * sum(1 for card in move.cards if card.rank == Rank.KING)
    # High pairs and triples can take important multi-card tricks.
    penalty += _high_group_penalty(move)
    # Very strong five-card hands should not be spent casually.
    penalty += _strong_five_card_penalty(move)

    if is_urgent_situation(observation):
        penalty //= URGENT_REDUCTION_FACTOR
    elif player_is_near_win(observation):
        penalty //= NEAR_WIN_REDUCTION_FACTOR

    if move_takes_control(move, observation) and _remaining_hand_is_strong(move, observation, p):
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


def should_pass(observation: "Observation", best_move: Move, best_score: int, personality: BotPersonality | None = None) -> bool:
    p = personality or BotPersonality.create_default()
    # Never pass if:
    # - bot is starting a new trick
    if observation.is_starting_new_trick:
        return False
    # - best_move wins immediately
    if _move_wins_immediately(best_move, observation):
        return False
    # - current play was made by a dangerous opponent with 1 or 2 cards
    if is_current_leader_dangerous(observation):
        return False
    # - any opponent has 1 card and best_move can block safely
    if move_blocks_dangerous_player(observation, best_move):
        return False
    # - bot has 3 or fewer cards and best_move improves exit path significantly
    if len(observation.my_hand) <= 3 and improves_exit_path(observation, best_move):
        return False

    # Usually pass if:
    # - best move uses a 2 just to beat a high single
    is_single = len(best_move.cards) == 1
    if is_single and any(card.rank == Rank.TWO for card in best_move.cards):
        if observation.current_play and len(observation.current_play.cards) == 1:
            current_card = observation.current_play.cards[0]
            if current_card.rank >= Rank.JACK: # Wasting 2 on J, Q, K, A
                if is_safe_to_pass(observation):
                    return True

    # - best move uses the bot's last obvious control card
    if is_expensive_move(observation, best_move, p) and not has_likely_control_card(_remove_cards(list(observation.my_hand), best_move.cards)):
        if is_safe_to_pass(observation):
            return True

    # - best move breaks a strong combo
    if _would_break_triple(list(observation.my_hand), best_move.cards) and is_safe_to_pass(observation):
        return True

    # - best move leaves a much worse remaining hand
    remaining_hand = _remove_cards(list(observation.my_hand), best_move.cards)
    if evaluate_remaining_hand(observation, remaining_hand) > evaluate_remaining_hand(observation, list(observation.my_hand)) + p.best_score_threshold_worse_hand:
        if is_safe_to_pass(observation):
            return True

    # - current trick is not urgent
    # - current play was not made by a dangerous opponent
    if not is_urgent_situation(observation) and is_expensive_move(observation, best_move, p):
        if is_safe_to_pass(observation):
            return True

    return False


def is_expensive_move(observation: "Observation", move: Move, personality: BotPersonality | None = None) -> bool:
    p = personality or BotPersonality.create_default()
    # Expensive if:
    # - uses rank 2
    if any(card.rank == Rank.TWO for card in move.cards):
        return True
    # - uses high Ace
    from card import Suit
    if any(card.rank == Rank.ACE and card.suit in (Suit.HEARTS, Suit.SPADES) for card in move.cards):
        return True
    # - breaks triple
    if _would_break_triple(list(observation.my_hand), move.cards):
        return True
    # - breaks useful five-card hand
    hand = list(observation.my_hand)
    remaining = _remove_cards(hand, move.cards)
    if len([p for p in generate_legal_plays(hand=hand, current_play=None) if len(p) == 5]) > \
       len([p for p in generate_legal_plays(hand=remaining, current_play=None) if len(p) == 5]):
        return True
    # - uses last likely control card
    if has_likely_control_card(hand) and not has_likely_control_card(remaining):
        return True
    return False


def is_current_leader_dangerous(observation: "Observation") -> bool:
    if observation.current_trick_leader is None:
        return False
    count = observation.card_counts_by_seat.get(observation.current_trick_leader, 13)
    return count <= 2


def move_blocks_dangerous_player(observation: "Observation", move: Move) -> bool:
    # True if:
    # - current leader is dangerous and move beats them
    if is_current_leader_dangerous(observation):
        return True
    # - or opponent has 1 card and move avoids giving an easy single
    if any(seat_id != observation.my_seat_id and count == 1 for seat_id, count in observation.card_counts_by_seat.items()):
        return True
    return False


def improves_exit_path(observation: "Observation", move: Move) -> bool:
    hand = list(observation.my_hand)
    remaining = _remove_cards(hand, move.cards)
    return estimate_exit_groups(remaining) < estimate_exit_groups(hand)


def is_safe_to_pass(observation: "Observation") -> bool:
    # - current leader is not dangerous
    if is_current_leader_dangerous(observation):
        return False
    # - next player is not down to 1 card
    from opponent_aware_bot import next_seat_id
    next_player = next_seat_id(observation, observation.my_seat_id)
    if observation.card_counts_by_seat.get(next_player, 13) == 1:
        return False
    # - bot is not near winning
    if len(observation.my_hand) <= 3:
        return False
    return True


def _move_wins_immediately(move: Move, observation: "Observation") -> bool:
    return len(move.cards) == len(observation.my_hand)


def _high_group_penalty(move: Move) -> int:
    if len(move.cards) not in (2, 3):
        return 0
    play_rank = classify_play(move.cards)
    if play_rank.category == PlayCategory.PAIR and move.cards[0].rank >= Rank.ACE:
        return PENALTY_HIGH_PAIR
    if play_rank.category == PlayCategory.TRIPLE and move.cards[0].rank >= Rank.KING:
        return PENALTY_HIGH_TRIPLE
    return 0


def _strong_five_card_penalty(move: Move) -> int:
    if len(move.cards) != 5:
        return 0
    play_rank = classify_play(move.cards)
    if play_rank.category in (PlayCategory.FOUR_OF_A_KIND, PlayCategory.STRAIGHT_FLUSH):
        return PENALTY_POWER_FIVE
    if play_rank.category == PlayCategory.FULL_HOUSE and max(card.rank for card in move.cards) >= Rank.ACE:
        return PENALTY_HIGH_FULL_HOUSE
    return 0


def _remaining_hand_is_strong(move: Move, observation: "Observation", personality: BotPersonality | None = None) -> bool:
    remaining = list(observation.my_hand)
    for card in move.cards:
        remaining.remove(card)
    # Using evaluate_remaining_hand instead of old evaluate_hand_badness
    return evaluate_remaining_hand(observation, remaining) <= STRONG_REMAINING_HAND_THRESHOLD or any(
        is_control_card(card, observation) for card in remaining
    )


def _beating_current_play_is_too_expensive(move: Move, observation: "Observation", personality: BotPersonality | None = None) -> bool:
    if observation.current_play is None:
        return False
    return control_card_penalty(move, observation, personality) >= EXPENSIVE_MOVE_THRESHOLD


def _is_played_event(event: object) -> bool:
    return hasattr(event, "cards") and hasattr(event, "play_kind")
