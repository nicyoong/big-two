from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from random_legal_play import RandomLegalPlay
from game import BigTwoGame, PlayerSeat
from lowest_valid_play import LowestValidPlay
from combo_preservation import ComboPreservation


GAME_COUNT = 1000
MAX_TURNS_PER_GAME = 1000
LOWEST_VALID_SEAT_ID = "seat-1"


@dataclass(frozen=True)
class GameResult:
    winner: str
    turns: int
    test_starting_cards: int
    random_starting_cards: tuple[int, int, int]


def test_combo_preservation_against_three_random_legal_plays_monte_carlo() -> None:
    results = [run_game(game_number) for game_number in range(GAME_COUNT)]
    winners = Counter(result.winner for result in results)
    lowest_valid_wins = winners[LOWEST_VALID_SEAT_ID]
    random_wins = GAME_COUNT - lowest_valid_wins
    turn_counts = [result.turns for result in results]

    print("")
    print("Monte Carlo: ComboPreservation vs 3 RandomLegalPlay")
    print(f"Games: {GAME_COUNT}")
    print(f"ComboPreservation wins: {lowest_valid_wins} ({lowest_valid_wins / GAME_COUNT:.1%})")
    print(f"RandomLegalPlay wins: {random_wins} ({random_wins / GAME_COUNT:.1%})")
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
            name="ComboPreservation",
            kind="logic",
            strategy=ComboPreservation(),
        ),
        PlayerSeat(
            seat_id="seat-2",
            name="RandomLegalPlay 1",
            kind="logic",
            strategy=RandomLegalPlay(seed=20_000 + game_number),
        ),
        PlayerSeat(
            seat_id="seat-3",
            name="RandomLegalPlay 2",
            kind="logic",
            strategy=RandomLegalPlay(seed=30_000 + game_number),
        ),
        PlayerSeat(
            seat_id="seat-4",
            name="RandomLegalPlay 3",
            kind="logic",
            strategy=RandomLegalPlay(seed=40_000 + game_number),
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
        if seat.strategy is None:
            raise AssertionError(f"{seat.seat_id} has no strategy")

        observation = game.create_observation(seat.seat_id)
        move = seat.strategy.choose_move(observation)
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
