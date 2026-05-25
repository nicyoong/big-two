from bot import Move
from card import Card
from game import Observation, Play
from phase_aware_bot import GamePhase, PhaseAwareBot, get_game_phase


def cards(*labels: str) -> list[Card]:
    return [Card.from_text(label) for label in labels]


def make_observation(
    my_hand: list[Card],
    current_play: Play | None = None,
    card_counts_by_seat: dict[str, int] | None = None,
) -> Observation:
    return Observation(
        my_seat_id="seat-1",
        my_hand=tuple(my_hand),
        seat_order=("seat-1", "seat-2", "seat-3", "seat-4"),
        current_turn_seat_id="seat-1",
        current_play=current_play,
        current_trick_leader=current_play.seat_id if current_play is not None else None,
        passed_seat_ids=frozenset(),
        card_counts_by_seat=card_counts_by_seat
        or {"seat-1": len(my_hand), "seat-2": 8, "seat-3": 8, "seat-4": 8},
        is_starting_new_trick=current_play is None,
        must_include_card=None,
        recent_events=(),
        memory_window=8,
    )


def test_get_game_phase() -> None:
    assert get_game_phase(13) == GamePhase.OPENING
    assert get_game_phase(9) == GamePhase.OPENING
    assert get_game_phase(8) == GamePhase.MIDDLE
    assert get_game_phase(4) == GamePhase.MIDDLE
    assert get_game_phase(3) == GamePhase.ENDGAME
    assert get_game_phase(1) == GamePhase.ENDGAME


def test_opening_bot_prefers_weak_five_card_hand_over_low_single_when_starting() -> None:
    bot = PhaseAwareBot()
    observation = make_observation(
        my_hand=cards("3D", "4C", "5H", "6S", "7D", "9D", "JD", "QD", "KD"),
    )

    move = bot.choose_move(observation)

    assert move == Move(cards("3D", "4C", "5H", "6S", "7D"))


def test_opening_bot_avoids_using_two() -> None:
    bot = PhaseAwareBot()
    observation = make_observation(
        my_hand=cards("8D", "2D", "3C", "4C", "5C", "6C", "9D", "10D", "JD"),
        current_play=Play(seat_id="seat-2", cards=(Card.from_text("7D"),)),
    )

    move = bot.choose_move(observation)

    assert move == Move(cards("8D"))


def test_endgame_bot_uses_two_if_it_helps_go_out() -> None:
    bot = PhaseAwareBot()
    observation = make_observation(
        my_hand=cards("2D"),
        current_play=Play(seat_id="seat-2", cards=(Card.from_text("AH"),)),
    )

    move = bot.choose_move(observation)

    assert move == Move(cards("2D"))


def test_endgame_bot_prefers_move_that_leaves_one_high_card_over_one_low_card() -> None:
    bot = PhaseAwareBot()
    observation = make_observation(
        my_hand=cards("3D", "AD", "AH"),
        current_play=Play(seat_id="seat-2", cards=tuple(cards("KD", "KC"))),
    )

    move = bot.choose_move(observation)

    assert move == Move(cards("AD", "AH"))


def test_middle_bot_avoids_move_that_leaves_many_low_singles() -> None:
    bot = PhaseAwareBot()
    observation = make_observation(
        my_hand=cards("3D", "4C", "5H", "6S", "7D", "8C"),
    )

    move = bot.choose_move(observation)

    assert move == Move(cards("3D", "4C", "5H", "6S", "7D"))
