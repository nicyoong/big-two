"""Centralized scoring constants for tactical, phase, and opponent-aware strategies."""

from dataclasses import dataclass
import random

@dataclass(frozen=True)
class BotPersonality:
    penalty_two: int
    penalty_ace: int
    best_score_threshold_worse_hand: int
    endgame_card_shed_bonus: int
    endgame_control_reduction_factor: int

    @classmethod
    def create_random(cls, seed: int | None = None) -> "BotPersonality":
        rng = random.Random(seed)
        return cls(
            penalty_two=rng.randint(30, 70),           # Mean ~50
            penalty_ace=rng.randint(10, 30),           # Mean ~20
            best_score_threshold_worse_hand=rng.randint(50, 150), # Mean ~100
            endgame_card_shed_bonus=rng.randint(-70, -30),        # Mean ~-50
            endgame_control_reduction_factor=rng.randint(1, 3),   # Mean ~2
        )

    @classmethod
    def create_default(cls) -> "BotPersonality":
        return cls(
            penalty_two=50,
            penalty_ace=20,
            best_score_threshold_worse_hand=100,
            endgame_card_shed_bonus=-50,
            endgame_control_reduction_factor=2,
        )

# --- Tactical Heuristics (control_card_bot.py) ---
PENALTY_TWO = 50
PENALTY_ACE = 20
PENALTY_KING = 15
PENALTY_HIGH_PAIR = 30
PENALTY_HIGH_TRIPLE = 45
PENALTY_POWER_FIVE = 50
PENALTY_HIGH_FULL_HOUSE = 25
URGENT_REDUCTION_FACTOR = 4
NEAR_WIN_REDUCTION_FACTOR = 2
STRONG_REMAINING_HAND_THRESHOLD = 25
EXPENSIVE_MOVE_THRESHOLD = 80
BEST_SCORE_THRESHOLD_WORSE_HAND = 100

# --- Phase Heuristics (phase_aware_bot.py) ---
PHASE_THRESHOLD_OPENING = 9
PHASE_THRESHOLD_MIDDLE = 4
OPENING_WEAK_FIVE_BONUS = -25
OPENING_PENALTY_TWO = 40
OPENING_PENALTY_ACE = 20
OPENING_BREAK_PAIR_PENALTY = 30
OPENING_BREAK_TRIPLE_PENALTY = 45
OPENING_LOW_ORPHAN_BONUS = -10
MIDDLE_LOW_ORPHAN_BASE_PENALTY = 12
MIDDLE_LOW_ORPHAN_RANK_PENALTY = 3
MIDDLE_FIVE_CARD_BONUS = -20
MIDDLE_NO_CONTROL_PENALTY = 18
ENDGAME_CARD_SHED_BONUS = -50
ENDGAME_STRONG_OUT_BONUS = -35
ENDGAME_WEAK_OUT_PENALTY = 45
ENDGAME_SINGLE_PENALTY = 30
ENDGAME_CONTROL_REDUCTION_FACTOR = 2

# --- Opponent Heuristics (opponent_aware_bot.py) ---
DANGER_LEVEL_1_CARD = 100
DANGER_LEVEL_2_CARDS = 60
DANGER_LEVEL_3_4_CARDS = 30
OPPONENT_1_CARD_START_LOW_SINGLE_PENALTY = 80
OPPONENT_1_CARD_START_MULTI_CARD_BONUS = -25
NEXT_PLAYER_1_CARD_LOW_SINGLE_PENALTY = 100
OPPONENT_2_CARDS_START_WEAK_PAIR_PENALTY = 35
OPPONENT_1_CARD_SINGLE_RANK_PENALTY_MULT = 2
DANGEROUS_OPPONENT_PASSED_SIZE_BONUS = -15
DANGEROUS_OPPONENT_PASSED_KIND_BONUS = -10
