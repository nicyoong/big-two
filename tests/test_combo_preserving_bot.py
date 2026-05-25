from bot import Move
from card import Card
from combo_preserving_bot import ComboPreservingBot
from game import Observation, Play


def cards(*labels: str) -> list[Card]:
    return [Card.from_text(label) for label in labels]


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
        played_cards=(),
        recent_history=(),
        is_starting_new_trick=current_play is None,
        must_include_card=must_include_card,
    )


def test_combo_preserving_bot_chooses_winning_move_when_available() -> None:
    bot = ComboPreservingBot()
    observation = make_observation(
        my_hand=cards("8D", "8C"),
        current_play=Play(seat_id="seat-2", cards=tuple(cards("7D", "7C"))),
    )

    move = bot.choose_move(observation)

    assert move == Move(cards("8D", "8C"))


def test_combo_preserving_bot_avoids_breaking_pair_if_similar_single_is_available() -> None:
    bot = ComboPreservingBot()
    observation = make_observation(
        my_hand=cards("7C", "7S", "8D"),
        current_play=Play(seat_id="seat-2", cards=(Card.from_text("7D"),)),
    )

    move = bot.choose_move(observation)

    assert move == Move(cards("8D"))


def test_combo_preserving_bot_avoids_wasting_rank_two_when_lower_legal_move_exists() -> None:
    bot = ComboPreservingBot()
    observation = make_observation(
        my_hand=cards("8D", "2D"),
        current_play=Play(seat_id="seat-2", cards=(Card.from_text("7D"),)),
    )

    move = bot.choose_move(observation)

    assert move == Move(cards("8D"))


def test_combo_preserving_bot_prefers_five_cards_when_starting_if_it_improves_hand_shape() -> None:
    bot = ComboPreservingBot()
    observation = make_observation(
        my_hand=cards("3D", "4C", "5H", "6S", "7D", "9D"),
    )

    move = bot.choose_move(observation)

    assert move == Move(cards("3D", "4C", "5H", "6S", "7D"))


def test_combo_preserving_bot_is_deterministic() -> None:
    bot = ComboPreservingBot()
    observation = make_observation(
        my_hand=cards("7C", "7S", "8D", "2D"),
        current_play=Play(seat_id="seat-2", cards=(Card.from_text("7D"),)),
    )

    moves = [bot.choose_move(observation) for _ in range(5)]

    assert moves == [Move(cards("8D"))] * 5
