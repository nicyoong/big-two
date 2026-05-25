import pytest

from bot import Move, PassMove
from card import Card
from cli import configure_cli_bots, format_cards, parse_move, play_bot_turn
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


def test_configure_cli_bots_uses_independent_opponent_aware_bots() -> None:
    game = BigTwoGame.new(human_count=1, seed=1)

    configure_cli_bots(game)

    bot_brains = [seat.bot_brain for seat in game.seats if seat.kind == "bot"]
    assert all(isinstance(brain, OpponentAwareBot) for brain in bot_brains)
    assert len({id(brain) for brain in bot_brains}) == len(bot_brains)


def test_play_bot_turn_uses_observation_and_records_public_event() -> None:
    game = BigTwoGame.new(human_count=1)
    bot_seat = next(seat for seat in game.seats if seat.kind == "bot")
    game.current_turn_seat_id = bot_seat.seat_id
    game.hands[bot_seat.seat_id] = [Card.from_text("3D"), Card.from_text("4D")]
    messages: list[str] = []

    play_bot_turn(game, bot_seat, messages.append)

    assert len(game.public_history) == 1
    assert game.public_history[0].event_type == "play"
    assert game.public_history[0].cards == (Card.from_text("3D"),)
    assert messages
