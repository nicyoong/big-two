from __future__ import annotations

from collections.abc import Callable

from logic import Move, PassMove
from card import Card, InvalidCardError
from game import BigTwoGame, GameError, PassedEvent, PlayedEvent, PlayerSeat, TrickResetEvent, WinEvent
from opponent_aware_bot import OpponentAwareBot
from rules import InvalidPlayError, classify_play


InputFunc = Callable[[str], str]
OutputFunc = Callable[[str], None]


class CliExit(Exception):
    """Raised when the user exits the CLI game loop."""


def run_cli(
    input_func: InputFunc = input,
    output_func: OutputFunc = print,
) -> None:
    output_func("Big Two CLI")
    human_count = prompt_human_count(input_func, output_func)
    human_names = prompt_human_names(human_count, input_func)
    game = BigTwoGame.new(human_count=human_count, human_names=human_names)
    configure_cli_strategies(game)

    output_func("")
    output_func("Game started.")
    output_func(f"{seat_name(game, game.current_turn_seat_id)} starts because they hold 3D.")

    while game.winner is None:
        seat = current_seat(game)
        output_turn_summary(game, seat, output_func)
        if seat.kind == "logic":
            play_logic_turn(game, seat, output_func)
        else:
            play_human_turn(game, seat, input_func, output_func)

    output_func("")
    output_func(f"{seat_name(game, game.winner)} wins.")


def prompt_human_count(input_func: InputFunc, output_func: OutputFunc) -> int:
    while True:
        raw = input_func("Human players (1-4): ").strip()
        try:
            human_count = int(raw)
        except ValueError:
            output_func("Enter a number from 1 to 4.")
            continue
        if 1 <= human_count <= 4:
            return human_count
        output_func("Enter a number from 1 to 4.")


def prompt_human_names(human_count: int, input_func: InputFunc) -> list[str]:
    names: list[str] = []
    for index in range(human_count):
        raw = input_func(f"Name for player {index + 1} [Player {index + 1}]: ").strip()
        names.append(raw or f"Player {index + 1}")
    return names


def configure_cli_strategies(game: BigTwoGame) -> None:
    for seat in game.seats:
        if seat.kind == "logic":
            seat.strategy = OpponentAwareBot()


def play_logic_turn(game: BigTwoGame, seat: PlayerSeat, output_func: OutputFunc) -> None:
    if seat.strategy is None:
        raise RuntimeError(f"Logic seat {seat.seat_id!r} has no strategy")

    observation = game.create_observation(seat.seat_id)
    move = seat.strategy.choose_move(observation)
    event = game.apply_move(seat.seat_id, move)
    output_func(format_event(game, event))


def play_human_turn(
    game: BigTwoGame,
    seat: PlayerSeat,
    input_func: InputFunc,
    output_func: OutputFunc,
) -> None:
    while True:
        raw = input_func("Play cards, 'pass', or 'quit': ")
        if raw.strip().lower() in ("quit", "q", "exit"):
            raise CliExit()

        try:
            move = parse_move(raw)
            event = game.apply_move(seat.seat_id, move)
        except (InvalidCardError, ValueError, GameError) as exc:
            output_func(f"Invalid move: {exc}")
            continue

        output_func(format_event(game, event))
        return


def parse_move(raw: str) -> Move | PassMove:
    normalized = raw.strip()
    if not normalized:
        raise ValueError("Enter cards or pass")
    if normalized.lower() in ("pass", "p"):
        return PassMove()

    labels = normalized.replace(",", " ").split()
    return Move([Card.from_text(label) for label in labels])


def output_turn_summary(game: BigTwoGame, seat: PlayerSeat, output_func: OutputFunc) -> None:
    public_state = game.get_public_state()
    output_func("")
    output_func(f"Turn: {seat.name} ({seat.kind})")
    output_func(f"Counts: {format_card_counts(game)}")
    output_func(f"Current play: {format_current_play(game)}")
    if public_state.must_include_card is not None:
        output_func(f"Must include: {public_state.must_include_card}")
    if seat.kind == "human":
        output_func(f"Your hand: {format_cards(game.hands[seat.seat_id])}")


def format_event(game: BigTwoGame, event) -> str:  # type: ignore[no-untyped-def]
    if isinstance(event, PlayedEvent):
        return f"{seat_name(game, event.seat_id)} played {format_cards(event.cards)} ({format_play_type(event.cards)})"
    if isinstance(event, PassedEvent):
        return f"{seat_name(game, event.seat_id)} passed"
    if isinstance(event, TrickResetEvent):
        return f"Trick reset. {seat_name(game, event.new_leader_seat_id)} leads."
    if isinstance(event, WinEvent):
        return f"{seat_name(game, event.seat_id)} won"
    return event.event_type


def format_current_play(game: BigTwoGame) -> str:
    if game.current_play is None:
        return "none"
    return (
        f"{seat_name(game, game.current_play.seat_id)}: "
        f"{format_cards(game.current_play.cards)} ({format_play_type(game.current_play.cards)})"
    )


def format_play_type(cards: tuple[Card, ...] | list[Card]) -> str:
    try:
        return classify_play(cards).category.name.lower().replace("_", " ")
    except InvalidPlayError:
        return "unknown"


def format_cards(cards: tuple[Card, ...] | list[Card]) -> str:
    return " ".join(str(card) for card in sorted(cards))


def format_card_counts(game: BigTwoGame) -> str:
    counts = game.get_public_state().card_counts_by_seat
    return ", ".join(f"{seat.name}={counts[seat.seat_id]}" for seat in game.seats)


def current_seat(game: BigTwoGame) -> PlayerSeat:
    return next(seat for seat in game.seats if seat.seat_id == game.current_turn_seat_id)


def seat_name(game: BigTwoGame, seat_id: str | None) -> str:
    if seat_id is None:
        return "Unknown"
    return next((seat.name for seat in game.seats if seat.seat_id == seat_id), seat_id)


if __name__ == "__main__":
    try:
        run_cli()
    except CliExit:
        print("")
        print("Game exited.")
