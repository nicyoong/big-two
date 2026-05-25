from bot import Move, PassMove
from card import Card
from control_card_bot import ControlCardBot
from game import Observation, Play


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


def test_bot_passes_instead_of_playing_two_over_ace_in_non_urgent_situation() -> None:
    bot = ControlCardBot()
    observation = make_observation(
        my_hand=cards("2D", "4D", "5D", "6D"),
        current_play=Play(seat_id="seat-2", cards=(Card.from_text("AH"),)),
    )

    move = bot.choose_move(observation)

    assert isinstance(move, PassMove)


def test_bot_plays_two_over_ace_if_opponent_has_one_card() -> None:
    bot = ControlCardBot()
    observation = make_observation(
        my_hand=cards("2D", "4D", "5D", "6D"),
        current_play=Play(seat_id="seat-2", cards=(Card.from_text("AH"),)),
        card_counts_by_seat={"seat-1": 4, "seat-2": 1, "seat-3": 8, "seat-4": 8},
    )

    move = bot.choose_move(observation)

    assert move == Move(cards("2D"))


def test_bot_uses_two_if_it_wins_immediately() -> None:
    bot = ControlCardBot()
    observation = make_observation(
        my_hand=cards("2D"),
        current_play=Play(seat_id="seat-2", cards=(Card.from_text("AH"),)),
    )

    move = bot.choose_move(observation)

    assert move == Move(cards("2D"))


def test_bot_preserves_two_when_lower_legal_move_can_beat_current_play() -> None:
    bot = ControlCardBot()
    observation = make_observation(
        my_hand=cards("8D", "2D"),
        current_play=Play(seat_id="seat-2", cards=(Card.from_text("7D"),)),
    )

    move = bot.choose_move(observation)

    assert move == Move(cards("8D"))


def test_bot_does_not_pass_when_starting_new_trick() -> None:
    bot = ControlCardBot()
    observation = make_observation(my_hand=cards("2D", "4D", "5D"))

    move = bot.choose_move(observation)

    assert not isinstance(move, PassMove)
