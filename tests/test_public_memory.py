from card import Card
from game import (
    BigTwoGame,
    Observation,
    PassedEvent,
    PlayedEvent,
    PublicEvent,
    recent_events_by_seat,
    recent_passes_by_seat,
    recent_plays_by_seat,
    recently_passed_on_kind,
    recently_passed_on_size,
)


def make_observation(recent_events: tuple[PublicEvent, ...]) -> Observation:
    return Observation(
        my_seat_id="seat-1",
        my_hand=(Card.from_text("3D"),),
        seat_order=("seat-1", "seat-2", "seat-3", "seat-4"),
        current_turn_seat_id="seat-1",
        current_play=None,
        current_trick_leader=None,
        passed_seat_ids=frozenset(),
        card_counts_by_seat={"seat-1": 1, "seat-2": 13, "seat-3": 13, "seat-4": 13},
        is_starting_new_trick=True,
        must_include_card=None,
        recent_events=recent_events,
        memory_window=8,
    )


def played_event(turn_number: int, seat_id: str, labels: list[str], play_kind: str) -> PlayedEvent:
    return PlayedEvent(
        turn_number=turn_number,
        trick_number=1,
        seat_id=seat_id,
        cards=tuple(Card.from_text(label) for label in labels),
        play_kind=play_kind,
    )


def passed_event(turn_number: int, seat_id: str) -> PassedEvent:
    return PassedEvent(turn_number=turn_number, trick_number=1, seat_id=seat_id)


def test_observation_only_includes_last_n_events() -> None:
    game = BigTwoGame.new(human_count=4, seed=1)
    game.public_history = [
        played_event(turn_number=index, seat_id=f"seat-{index % 4 + 1}", labels=["3D"], play_kind="single")
        for index in range(1, 11)
    ]

    observation = game.create_observation(game.current_turn_seat_id, memory_window=3)

    assert observation.memory_window == 3
    assert [event.turn_number for event in observation.recent_events] == [8, 9, 10]


def test_observation_does_not_include_all_historical_played_cards() -> None:
    game = BigTwoGame.new(human_count=4, seed=1)
    game.public_history = [
        played_event(turn_number=1, seat_id="seat-1", labels=["3D"], play_kind="single"),
        played_event(turn_number=2, seat_id="seat-2", labels=["4D"], play_kind="single"),
        played_event(turn_number=3, seat_id="seat-3", labels=["5D"], play_kind="single"),
    ]

    observation = game.create_observation(game.current_turn_seat_id, memory_window=1)

    assert not hasattr(observation, "played_cards")
    assert not hasattr(observation, "public_history")
    assert len(observation.recent_events) == 1
    assert observation.recent_events[0] == game.public_history[-1]


def test_observation_does_not_include_opponents_hands() -> None:
    game = BigTwoGame.new(human_count=1, seed=1)
    bot_seat = next(seat for seat in game.seats if seat.kind == "logic")

    observation = game.create_observation(bot_seat.seat_id)

    assert not hasattr(observation, "hands")
    assert observation.my_hand == tuple(game.hands[bot_seat.seat_id])


def test_recent_pass_helper_works() -> None:
    observation = make_observation(
        (
            played_event(1, "seat-1", ["3D"], "single"),
            passed_event(2, "seat-2"),
            passed_event(3, "seat-3"),
        )
    )

    assert recent_passes_by_seat(observation, "seat-2") == [passed_event(2, "seat-2")]


def test_recent_play_helper_works() -> None:
    event = played_event(1, "seat-2", ["3D", "3C"], "pair")
    observation = make_observation((event, passed_event(2, "seat-3")))

    assert recent_plays_by_seat(observation, "seat-2") == [event]
    assert recent_events_by_seat(observation, "seat-3") == [passed_event(2, "seat-3")]


def test_recently_passed_on_kind_works() -> None:
    observation = make_observation(
        (
            played_event(1, "seat-1", ["3D", "3C"], "pair"),
            passed_event(2, "seat-2"),
        )
    )

    assert recently_passed_on_kind(observation, "seat-2", "pair")
    assert not recently_passed_on_kind(observation, "seat-2", "single")


def test_recently_passed_on_size_works() -> None:
    observation = make_observation(
        (
            played_event(1, "seat-1", ["3D", "3C", "3H"], "triple"),
            passed_event(2, "seat-2"),
        )
    )

    assert recently_passed_on_size(observation, "seat-2", 3)
    assert not recently_passed_on_size(observation, "seat-2", 2)
