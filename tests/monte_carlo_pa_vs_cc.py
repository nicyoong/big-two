from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import time

from random_legal_bot import RandomLegalBot
from game import BigTwoGame, PlayerSeat
from control_card_bot import ControlCardBot
from combo_preserving_bot import ComboPreservingBot


GAME_COUNT = 1000
MAX_TURNS_PER_GAME = 1000
LOWEST_VALID_SEAT_ID = "seat-1"


@dataclass(frozen=True)
class GameResult:
    winner: str
    turns: int
    test_starting_cards: int
    random_starting_cards: tuple[int, int, int]


def test_control_card_bot_against_three_combo_preserving_bots_monte_carlo() -> None:
    results: list[GameResult] = []
    started_at = time.monotonic()
    next_progress_at = started_at + 10
    for game_number in range(GAME_COUNT):
        results.append(run_game(game_number))
        now = time.monotonic()
        if now >= next_progress_at:
            completed = game_number + 1
            elapsed = now - started_at
            print(f"Completed {completed}/{GAME_COUNT} games after {elapsed:.1f}s", flush=True)
            next_progress_at = now + 10
    winners = Counter(result.winner for result in results)
    lowest_valid_wins = winners[LOWEST_VALID_SEAT_ID]
    random_wins = GAME_COUNT - lowest_valid_wins
    turn_counts = [result.turns for result in results]

    print("")
    print("Monte Carlo: PhaseAwareBot vs 3 ControlCardBot")
    print(f"Games: {GAME_COUNT}")
    print(f"PhaseAwareBot wins: {lowest_valid_wins} ({lowest_valid_wins / GAME_COUNT:.1%})")
    print(f"ControlCardBot wins: {random_wins} ({random_wins / GAME_COUNT:.1%})")
    print("Wins by seat:")
    for seat_id in ("seat-1", "seat-2", "seat-3", "seat-4"):
        print(f"  {seat_id}: {winners[seat_id]}")
    print("Turn counts:")
    print(f"  min: {min(turn_counts)}")
    print(f"  max: {max(turn_counts)}")
    print(f"  avg: {sum(turn_counts) / len(turn_counts):.2f}")

    assert sum(winners.values()) == GAME_COUNT


def run_game(game_number: int) -> GameResult:
    game = BigTwoGame.new(human_count=4, seed=10_000 + game_number)
    game.seats = [
        PlayerSeat(
            seat_id="seat-1",
            name="ControlCardBot",
            kind="bot",
            bot_brain=ControlCardBot(),
        ),
        PlayerSeat(
            seat_id="seat-2",
            name="ComboPreservingBot 1",
            kind="bot",
            bot_brain=ComboPreservingBot(),
        ),
        PlayerSeat(
            seat_id="seat-3",
            name="ComboPreservingBot 2",
            kind="bot",
            bot_brain=ComboPreservingBot(),
        ),
        PlayerSeat(
            seat_id="seat-4",
            name="ComboPreservingBot 3",
            kind="bot",
            bot_brain=ComboPreservingBot(),
        ),
    ]

    starting_counts = {
        seat.seat_id: len(game.hands[seat.seat_id])
        for seat in game.seats
    }

    turns = 0
    while game.winner is None:
        turns += 1
        if turns > MAX_TURNS_PER_GAME:
            raise AssertionError(f"Game {game_number} exceeded {MAX_TURNS_PER_GAME} turns")

        seat = next(seat for seat in game.seats if seat.seat_id == game.current_turn_seat_id)
        if seat.bot_brain is None:
            raise AssertionError(f"{seat.seat_id} has no bot brain")

        observation = game.create_observation(seat.seat_id)
        move = seat.bot_brain.choose_move(observation)
        game.apply_move(seat.seat_id, move)

    return GameResult(
        winner=game.winner,
        turns=turns,
        test_starting_cards=starting_counts["seat-1"],
        random_starting_cards=(
            starting_counts["seat-2"],
            starting_counts["seat-3"],
            starting_counts["seat-4"],
        ),
    )
