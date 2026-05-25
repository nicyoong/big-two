import pytest

from bot import Move
from card import Card
from game import BigTwoGame, InvalidMoveError, Play


@pytest.mark.parametrize("human_count", [1, 2, 3, 4])
def test_game_can_be_created_with_one_to_four_human_players(human_count: int) -> None:
    game = BigTwoGame.new(human_count=human_count, seed=1)

    assert len(game.seats) == 4
    assert sum(seat.kind == "human" for seat in game.seats) == human_count
    assert sum(seat.kind == "bot" for seat in game.seats) == 4 - human_count
    assert set(game.hands) == {seat.seat_id for seat in game.seats}


@pytest.mark.parametrize("human_count", [1, 2, 3])
def test_each_bot_has_a_distinct_brain_instance(human_count: int) -> None:
    game = BigTwoGame.new(human_count=human_count)
    bot_brains = [seat.bot_brain for seat in game.seats if seat.kind == "bot"]

    assert all(brain is not None for brain in bot_brains)
    assert len({id(brain) for brain in bot_brains}) == len(bot_brains)


def test_bot_observation_includes_own_hand() -> None:
    game = BigTwoGame.new(human_count=1)
    bot_seat = next(seat for seat in game.seats if seat.kind == "bot")

    observation = game.create_observation(bot_seat.seat_id)

    assert observation.my_seat_id == bot_seat.seat_id
    assert observation.my_hand == tuple(game.hands[bot_seat.seat_id])


def test_bot_observation_does_not_include_other_players_hands() -> None:
    game = BigTwoGame.new(human_count=1)
    bot_seat = next(seat for seat in game.seats if seat.kind == "bot")
    other_seat_ids = {seat.seat_id for seat in game.seats if seat.seat_id != bot_seat.seat_id}

    observation = game.create_observation(bot_seat.seat_id)

    assert not hasattr(observation, "hands")
    assert set(observation.card_counts_by_seat) == set(game.hands)
    for other_seat_id in other_seat_ids:
        assert tuple(game.hands[other_seat_id]) != observation.my_hand


def test_public_state_exposes_card_counts_not_private_hands() -> None:
    game = BigTwoGame.new(human_count=2)

    public_state = game.get_public_state()

    assert not hasattr(public_state, "hands")
    assert all(not hasattr(seat, "bot_brain") for seat in public_state.seats)
    assert public_state.card_counts_by_seat == {
        seat.seat_id: len(game.hands[seat.seat_id]) for seat in game.seats
    }


def test_public_history_records_plays_and_passes() -> None:
    game = BigTwoGame.new(human_count=4)
    starting_seat_id = game.current_turn_seat_id

    game.apply_move(starting_seat_id, Move([Card.from_text("3D")]))
    passing_seat_id = game.current_turn_seat_id
    game.pass_turn(passing_seat_id)

    assert [event.event_type for event in game.public_history] == ["play", "pass"]
    assert game.public_history[0].seat_id == starting_seat_id
    assert game.public_history[0].cards == (Card.from_text("3D"),)
    assert game.public_history[1].seat_id == passing_seat_id


def test_rejects_invalid_play_category() -> None:
    game = BigTwoGame.new(human_count=4)
    seat_id = game.current_turn_seat_id
    game.hands[seat_id] = [Card.from_text("3D"), Card.from_text("4D")]

    with pytest.raises(InvalidMoveError, match="pair"):
        game.apply_move(seat_id, Move([Card.from_text("3D"), Card.from_text("4D")]))


def test_rejects_play_that_does_not_beat_current_play() -> None:
    game = BigTwoGame.new(human_count=4)
    seat_id = game.current_turn_seat_id
    game.current_play = Play(seat_id="seat-2", cards=(Card.from_text("7D"),))
    game.current_trick_leader = "seat-2"
    game.hands[seat_id] = [Card.from_text("6S")]

    with pytest.raises(InvalidMoveError, match="does not beat"):
        game.apply_move(seat_id, Move([Card.from_text("6S")]))


def test_allows_five_card_higher_category_to_beat_current_play() -> None:
    game = BigTwoGame.new(human_count=4)
    seat_id = game.current_turn_seat_id
    game.current_play = Play(
        seat_id="seat-2",
        cards=tuple(Card.from_text(label) for label in ["3D", "4C", "5H", "6S", "7D"]),
    )
    game.current_trick_leader = "seat-2"
    game.hands[seat_id] = [Card.from_text(label) for label in ["3S", "5S", "7S", "9S", "JS"]]

    event = game.apply_move(seat_id, Move([Card.from_text(label) for label in ["3S", "5S", "7S", "9S", "JS"]]))

    assert event.event_type == "play"


def test_deal_is_shuffled_before_round_robin_distribution() -> None:
    game = BigTwoGame.new(human_count=4, seed=1)

    assert game.hands["seat-1"] != [Card.from_text(label) for label in [
        "3D",
        "4D",
        "5D",
        "6D",
        "7D",
        "8D",
        "9D",
        "10D",
        "JD",
        "QD",
        "KD",
        "AD",
        "2D",
    ]]


def test_seeded_deals_are_reproducible() -> None:
    first_game = BigTwoGame.new(human_count=4, seed=42)
    second_game = BigTwoGame.new(human_count=4, seed=42)

    assert first_game.hands == second_game.hands
