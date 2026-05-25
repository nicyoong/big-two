from bot import Move, PassMove
from card import Card
from game import Observation, Play
from lowest_valid_bot import LowestValidBot


def make_observation(
    my_hand: list[Card],
    current_play: Play | None = None,
    must_include_card: Card | None = None,
) -> Observation:
    return Observation(
        my_seat_id="seat-1",
        my_hand=tuple(my_hand),
        seat_order=("seat-1", "seat-2", "seat-3", "seat-4"),
        current_turn_seat_id="seat-1",
        current_play=current_play,
        current_trick_leader=current_play.seat_id if current_play is not None else None,
        passed_seat_ids=frozenset(),
        card_counts_by_seat={"seat-1": len(my_hand), "seat-2": 13, "seat-3": 13, "seat-4": 13},
        is_starting_new_trick=current_play is None,
        must_include_card=must_include_card,
        recent_events=(),
        memory_window=8,
    )


def test_lowest_valid_bot_first_move_with_three_diamonds_must_include_three_diamonds() -> None:
    bot = LowestValidBot()
    observation = make_observation(
        my_hand=[Card.from_text("3D"), Card.from_text("4D"), Card.from_text("5D")],
        must_include_card=Card.from_text("3D"),
    )

    move = bot.choose_move(observation)

    assert move == Move([Card.from_text("3D")])


def test_lowest_valid_bot_plays_weakest_single_that_beats_current_single() -> None:
    bot = LowestValidBot()
    observation = make_observation(
        my_hand=[
            Card.from_text("7C"),
            Card.from_text("7S"),
            Card.from_text("8D"),
            Card.from_text("9D"),
        ],
        current_play=Play(seat_id="seat-2", cards=(Card.from_text("7D"),)),
    )

    move = bot.choose_move(observation)

    assert move == Move([Card.from_text("7C")])


def test_lowest_valid_bot_plays_weakest_pair_that_beats_current_pair() -> None:
    bot = LowestValidBot()
    observation = make_observation(
        my_hand=[
            Card.from_text("8H"),
            Card.from_text("8S"),
            Card.from_text("9D"),
            Card.from_text("9C"),
            Card.from_text("10D"),
            Card.from_text("10C"),
        ],
        current_play=Play(seat_id="seat-2", cards=tuple(Card.from_text(card) for card in ["8D", "8C"])),
    )

    move = bot.choose_move(observation)

    assert move == Move([Card.from_text("8H"), Card.from_text("8S")])


def test_lowest_valid_bot_passes_when_no_response_is_possible() -> None:
    bot = LowestValidBot()
    observation = make_observation(
        my_hand=[Card.from_text("7D"), Card.from_text("7C"), Card.from_text("8D")],
        current_play=Play(seat_id="seat-2", cards=tuple(Card.from_text(card) for card in ["8H", "8S"])),
    )

    move = bot.choose_move(observation)

    assert isinstance(move, PassMove)


def test_lowest_valid_bot_is_deterministic_across_repeated_calls() -> None:
    bot = LowestValidBot()
    observation = make_observation(
        my_hand=[Card.from_text("7C"), Card.from_text("7S"), Card.from_text("8D")],
        current_play=Play(seat_id="seat-2", cards=(Card.from_text("7D"),)),
    )

    moves = [bot.choose_move(observation) for _ in range(5)]

    assert moves == [Move([Card.from_text("7C")])] * 5
