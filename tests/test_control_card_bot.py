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


def test_bot_does_not_pass_if_current_leader_is_dangerous() -> None:
    bot = ControlCardBot()
    # Leader has 2 cards, we can beat them with 2D. We SHOULD NOT pass.
    observation = make_observation(
        my_hand=cards("2D", "4D", "5D"),
        current_play=Play(seat_id="seat-2", cards=(Card.from_text("AH"),)),
        card_counts_by_seat={"seat-1": 3, "seat-2": 2, "seat-3": 8, "seat-4": 8},
    )

    move = bot.choose_move(observation)
    assert move == Move(cards("2D"))


def test_bot_does_not_pass_if_any_opponent_has_one_card_blocking() -> None:
    bot = ControlCardBot()
    # Seat 3 has 1 card. We should take control to block them.
    observation = make_observation(
        my_hand=cards("2D", "4D", "5D"),
        current_play=Play(seat_id="seat-2", cards=(Card.from_text("AH"),)),
        card_counts_by_seat={"seat-1": 3, "seat-2": 5, "seat-3": 1, "seat-4": 8},
    )

    move = bot.choose_move(observation)
    assert move == Move(cards("2D"))


def test_bot_may_pass_if_move_breaks_triple_and_situation_is_safe() -> None:
    bot = ControlCardBot()
    # We have a triple of 8s. To beat 7H, we'd have to use one 8, breaking the triple.
    # Situation is safe (all opponents have many cards).
    observation = make_observation(
        my_hand=cards("8D", "8C", "8H", "JD"),
        current_play=Play(seat_id="seat-2", cards=(Card.from_text("7H"),)),
        card_counts_by_seat={"seat-1": 4, "seat-2": 8, "seat-3": 8, "seat-4": 8},
    )

    move = bot.choose_move(observation)
    # It should prefer to pass rather than break the triple of 8s (if JD doesn't beat 7H)
    # Wait, JD beats 7H. Let's make it so only 8 beats 7H.
    # 7H is Rank 4. 8 is Rank 5. 
    # Let's use current_play = 9H (Rank 6). 
    # Then only JD (Rank 8) or 8s (Rank 5) - wait, 8s don't beat 9H.
    
    observation = make_observation(
        my_hand=cards("8D", "8C", "8H", "4D"),
        current_play=Play(seat_id="seat-2", cards=(Card.from_text("7H"),)), # Rank 4
        card_counts_by_seat={"seat-1": 4, "seat-2": 8, "seat-3": 8, "seat-4": 8},
    )
    # Legal plays: 8D, 8C, 8H. All break the triple.
    move = bot.choose_move(observation)
    assert isinstance(move, PassMove)
