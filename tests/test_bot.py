import random

from bot import LowestValidBot, Move, PassMove, RandomLegalBot, generate_legal_plays
from card import Card
from game import Observation, Play


class IndexedRandom(random.Random):
    def __init__(self, index: int) -> None:
        super().__init__(0)
        self.index = index
        self.calls = 0

    def choice(self, seq):  # type: ignore[no-untyped-def]
        self.calls += 1
        return seq[self.index]


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


def test_bot_passes_when_no_legal_plays_exist() -> None:
    bot = RandomLegalBot(rng=IndexedRandom(0))
    observation = make_observation(
        my_hand=[Card.from_text("3D")],
        current_play=Play(seat_id="seat-2", cards=tuple(Card.from_text(card) for card in ["4D", "4C"])),
    )

    move = bot.choose_move(observation)

    assert isinstance(move, PassMove)


def test_bot_returns_only_legal_moves() -> None:
    bot = RandomLegalBot(rng=IndexedRandom(1))
    observation = make_observation(
        my_hand=[Card.from_text("3D"), Card.from_text("4D"), Card.from_text("5D")],
        current_play=Play(seat_id="seat-2", cards=(Card.from_text("3C"),)),
    )

    move = bot.choose_move(observation)

    assert isinstance(move, Move)
    assert tuple(move.cards) in generate_legal_plays(
        hand=observation.my_hand,
        current_play=observation.current_play,
        must_include=observation.must_include_card,
    )


def test_bot_respects_must_include_card_on_first_play() -> None:
    required_card = Card.from_text("3D")
    bot = RandomLegalBot(rng=IndexedRandom(0))
    observation = make_observation(
        my_hand=[required_card, Card.from_text("4D"), Card.from_text("5D")],
        must_include_card=required_card,
    )

    move = bot.choose_move(observation)

    assert isinstance(move, Move)
    assert required_card in move.cards


def test_bot_does_not_need_access_to_opponents_private_hands() -> None:
    bot = RandomLegalBot(seed=1)
    observation = make_observation(
        my_hand=[Card.from_text("3D"), Card.from_text("4D")],
        must_include_card=Card.from_text("3D"),
    )

    move = bot.choose_move(observation)

    assert isinstance(move, Move)
    assert not hasattr(observation, "hands")
    assert set(observation.card_counts_by_seat) == {"seat-1", "seat-2", "seat-3", "seat-4"}


def test_two_bot_instances_make_decisions_independently() -> None:
    first_rng = IndexedRandom(0)
    second_rng = IndexedRandom(1)
    first_bot = RandomLegalBot(rng=first_rng)
    second_bot = RandomLegalBot(rng=second_rng)
    observation = make_observation(
        my_hand=[Card.from_text("3D"), Card.from_text("4D"), Card.from_text("5D")],
        current_play=Play(seat_id="seat-2", cards=(Card.from_text("3C"),)),
    )

    first_move = first_bot.choose_move(observation)
    second_move = second_bot.choose_move(observation)

    assert isinstance(first_move, Move)
    assert isinstance(second_move, Move)
    assert first_move.cards != second_move.cards
    assert first_rng.calls == 1
    assert second_rng.calls == 1


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
