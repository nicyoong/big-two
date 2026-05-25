import random

from bot import Move, PassMove, generate_legal_plays
from random_legal_bot import RandomLegalBot
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
        is_starting_new_trick=current_play is None,
        must_include_card=must_include_card,
        recent_events=(),
        memory_window=8,
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


def test_bot_does_not_play_2_spades_as_last_card() -> None:
    two_spades = Card.from_text("2S")
    observation = make_observation(
        my_hand=[two_spades],
        current_play=None, # New trick
    )
    
    legal_plays = generate_legal_plays(
        hand=observation.my_hand,
        current_play=observation.current_play,
        must_include=observation.must_include_card,
    )
    
    assert (two_spades,) not in legal_plays
    assert len(legal_plays) == 0
