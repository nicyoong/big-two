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
    score += evaluate_remaining_hand(observation, remaining_hand)
    return score


def evaluate_hand_badness(hand: list[Card]) -> int:
    """Backward compatibility wrapper for evaluate_remaining_hand."""
    # Since this version doesn't take observation, we pass a dummy or None if handled.
    # Actually evaluate_remaining_hand uses observation.my_seat_id and card_counts_by_seat
    # only for some checks. I should make evaluate_remaining_hand handle observation=None.
    return evaluate_remaining_hand(None, hand) # type: ignore


def evaluate_remaining_hand(observation: "Observation" | None, hand: list[Card]) -> int:
    if not hand:
        return -2_000_000 # Extremely good

    rank_counts = _rank_counts(hand)
    orphan_singles_list = [card for card in hand if rank_counts[card.rank] == 1]
    orphan_singles = len(orphan_singles_list)
    low_orphan_singles = sum(1 for card in orphan_singles_list if card.rank < Rank.JACK)
    
    pairs = sum(1 for count in rank_counts.values() if count >= 2)
    triples = sum(1 for count in rank_counts.values() if count >= 3)
    
    # Count five-card plays but cap for bonus
    five_card_plays_list = [cards for cards in generate_legal_plays(hand=hand, current_play=None) if len(cards) == 5]
    five_card_count = len(five_card_plays_list)
    capped_five_card_groups = min(five_card_count, 2)
    
    control_cards_count = sum(1 for card in hand if card.rank in (Rank.KING, Rank.ACE, Rank.TWO))
    exit_groups = estimate_exit_groups(hand)
    
    badness = (
        len(hand) * 5
        + exit_groups * 18
        + orphan_singles * 8
        + low_orphan_singles * 12
        - pairs * 5
        - triples * 8
        - capped_five_card_groups * 10
        - control_cards_count * 4
    )
    
    if is_clean_exit_group(hand):
        badness -= 50
        
    if not has_likely_control_card(hand):
        badness += 20

    # Differentiate between high and low single exit groups
    if len(hand) == 1:
        # Penalize lower single rank. Rank.TWO is 12, Rank.THREE is 0.
        badness += int(Rank.TWO - hand[0].rank) * 2

    return badness


def estimate_exit_groups(hand: list[Card]) -> int:
    """Greedy deterministic estimation of future turns needed to empty the hand."""
    temp_hand = sorted(hand)
    groups = 0
    
    while temp_hand:
        groups += 1
        # 1. Best 5-card play (highest strength)
        five_card_plays = [cards for cards in generate_legal_plays(hand=temp_hand, current_play=None) if len(cards) == 5]
        if five_card_plays:
            best_five = max(five_card_plays, key=play_strength)
            temp_hand = _remove_cards(temp_hand, list(best_five))
            continue
            
        # 2. Triples (highest)
        rank_counts = _rank_counts(temp_hand)
        triples = [rank for rank, count in rank_counts.items() if count >= 3]
        if triples:
            best_rank = max(triples)
            cards_to_remove = [c for c in temp_hand if c.rank == best_rank][:3]
            temp_hand = _remove_cards(temp_hand, cards_to_remove)
            continue
            
        # 3. Pairs (highest)
        pairs = [rank for rank, count in rank_counts.items() if count >= 2]
        if pairs:
            best_rank = max(pairs)
            cards_to_remove = [c for c in temp_hand if c.rank == best_rank][:2]
            temp_hand = _remove_cards(temp_hand, cards_to_remove)
            continue
            
        # 4. Single (highest)
        best_card = max(temp_hand)
        temp_hand = _remove_cards(temp_hand, [best_card])
        
    return groups


def is_clean_exit_group(hand: list[Card]) -> bool:
    if len(hand) == 1:
        return True
    if len(hand) == 2:
        return _rank_counts(hand).get(hand[0].rank, 0) == 2
    if len(hand) == 3:
        return _rank_counts(hand).get(hand[0].rank, 0) == 3
    if len(hand) == 5:
        try:
            from rules import classify_play
            classify_play(hand)
            return True
        except Exception:
            return False
    return False


def has_likely_control_card(hand: list[Card]) -> bool:
    if not hand:
        return True
    # Any 2
    if any(card.rank == Rank.TWO for card in hand):
        return True
    # Ace of Spades or Hearts
    from card import Suit
    if any(card.rank == Rank.ACE and card.suit in (Suit.HEARTS, Suit.SPADES) for card in hand):
        return True
    # High pair (JJ or higher)
    rank_counts = _rank_counts(hand)
    if any(count >= 2 and rank >= Rank.JACK for rank, count in rank_counts.items()):
        return True
    # High triple
    if any(count >= 3 and rank >= Rank.TEN for rank, count in rank_counts.items()):
        return True
    # Strong five-card hand (Flush or better)
    from rules import classify_play, PlayCategory
    five_card_plays = [cards for cards in generate_legal_plays(hand=hand, current_play=None) if len(cards) == 5]
    for play in five_card_plays:
        if classify_play(play).category >= PlayCategory.FLUSH:
            return True
            
    return False


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
