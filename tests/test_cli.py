import pytest

from logic import Move, PassMove
from card import Card
from cli import configure_cli_strategies, format_cards, parse_move, play_logic_turn
from game import BigTwoGame
from opponent_aware_bot import OpponentAwareBot


def test_parse_move_accepts_pass() -> None:
    assert isinstance(parse_move("pass"), PassMove)
    assert isinstance(parse_move("p"), PassMove)


def test_parse_move_accepts_space_or_comma_separated_cards() -> None:
    assert parse_move("3D 4C") == Move([Card.from_text("3D"), Card.from_text("4C")])
    assert parse_move("3D,4C") == Move([Card.from_text("3D"), Card.from_text("4C")])


def test_parse_move_rejects_empty_input() -> None:
    with pytest.raises(ValueError, match="Enter cards"):
        parse_move("")


def test_format_cards_sorts_cards() -> None:
    assert format_cards([Card.from_text("4D"), Card.from_text("3S"), Card.from_text("3D")]) == "3D 3S 4D"


def test_configure_cli_strategies_uses_independent_opponent_aware_strategies() -> None:
    game = BigTwoGame.new(human_count=1, seed=1)

    configure_cli_strategies(game)

    strategies = [seat.strategy for seat in game.seats if seat.kind == "logic"]
    assert all(isinstance(brain, OpponentAwareBot) for brain in strategies)
    assert len({id(brain) for brain in strategies}) == len(strategies)


def test_play_logic_turn_uses_observation_and_records_public_event() -> None:
    game = BigTwoGame.new(human_count=1)
    logic_seat = next(seat for seat in game.seats if seat.kind == "logic")
    game.current_turn_seat_id = logic_seat.seat_id
    game.hands[logic_seat.seat_id] = [Card.from_text("3D"), Card.from_text("4D")]
    messages: list[str] = []

    play_logic_turn(game, logic_seat, messages.append)

    assert len(game.public_history) == 1
    assert game.public_history[0].event_type == "play"
    assert game.public_history[0].cards == (Card.from_text("3D"),)
    assert messages
