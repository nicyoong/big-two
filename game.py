from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import ClassVar, Literal

from bot import BotBrain, Move, PassMove, RandomLegalBot
from card import Card, create_standard_deck
from rules import InvalidPlayError, can_beat, classify_play


PlayerKind = Literal["human", "bot"]


class GameError(ValueError):
    """Base exception for game action validation errors."""


class InvalidPlayerCountError(GameError):
    """Raised when a game is created with an invalid human player count."""


class UnknownSeatError(GameError):
    """Raised when an action references a seat that does not exist."""


class NotPlayersTurnError(GameError):
    """Raised when a seat acts outside its turn."""


class InvalidMoveError(GameError):
    """Raised when a move is not legal for the current game state."""


@dataclass
class PlayerSeat:
    seat_id: str
    name: str
    kind: PlayerKind
    bot_brain: BotBrain | None = None

    def __post_init__(self) -> None:
        if self.kind not in ("human", "bot"):
            raise ValueError(f"Invalid player kind: {self.kind!r}")
        if self.kind == "human" and self.bot_brain is not None:
            raise ValueError("Human seats cannot have a bot brain")
        if self.kind == "bot" and self.bot_brain is None:
            raise ValueError("Bot seats require a bot brain")


@dataclass(frozen=True)
class PublicSeat:
    seat_id: str
    name: str
    kind: PlayerKind


@dataclass(frozen=True)
class Play:
    seat_id: str
    cards: tuple[Card, ...]


@dataclass(frozen=True)
class PublicEvent:
    turn_number: int
    trick_number: int


@dataclass(frozen=True)
class PlayedEvent(PublicEvent):
    seat_id: str
    cards: tuple[Card, ...]
    play_kind: str
    event_type: ClassVar[str] = "play"


@dataclass(frozen=True)
class PassedEvent(PublicEvent):
    seat_id: str
    event_type: ClassVar[str] = "pass"


@dataclass(frozen=True)
class TrickResetEvent(PublicEvent):
    new_leader_seat_id: str | None
    event_type: ClassVar[str] = "trick_reset"


@dataclass(frozen=True)
class WinEvent(PublicEvent):
    seat_id: str
    event_type: ClassVar[str] = "win"


@dataclass(frozen=True)
class Observation:
    my_seat_id: str
    my_hand: tuple[Card, ...]
    seat_order: tuple[str, ...]
    current_turn_seat_id: str
    current_play: Play | None
    current_trick_leader: str | None
    passed_seat_ids: frozenset[str]
    card_counts_by_seat: dict[str, int]
    is_starting_new_trick: bool
    must_include_card: Card | None
    recent_events: tuple[PublicEvent, ...] = ()
    memory_window: int = 8


@dataclass(frozen=True)
class PublicState:
    seat_order: tuple[str, ...]
    seats: tuple[PublicSeat, ...]
    current_turn_seat_id: str
    current_play: Play | None
    current_trick_leader: str | None
    passed_seat_ids: frozenset[str]
    card_counts_by_seat: dict[str, int]
    winner: str | None
    is_starting_new_trick: bool
    must_include_card: Card | None


@dataclass
class BigTwoGame:
    seats: list[PlayerSeat]
    hands: dict[str, list[Card]]
    current_turn_seat_id: str
    current_play: Play | None = None
    current_trick_leader: str | None = None
    passed_seat_ids: set[str] = field(default_factory=set)
    winner: str | None = None
    public_history: list[PublicEvent] = field(default_factory=list)
    turn_number: int = 0
    trick_number: int = 1

    @classmethod
    def new(
        cls,
        human_count: int,
        human_names: list[str] | None = None,
        seed: int | str | bytes | bytearray | None = None,
        rng: random.Random | None = None,
    ) -> "BigTwoGame":
        if human_count < 1 or human_count > 4:
            raise InvalidPlayerCountError("human_count must be between 1 and 4")

        human_names = human_names or []
        seats: list[PlayerSeat] = []
        for index in range(4):
            seat_id = f"seat-{index + 1}"
            if index < human_count:
                name = human_names[index] if index < len(human_names) else f"Player {index + 1}"
                seats.append(PlayerSeat(seat_id=seat_id, name=name, kind="human"))
            else:
                bot_number = index - human_count + 1
                seats.append(
                    PlayerSeat(
                        seat_id=seat_id,
                        name=f"Bot {bot_number}",
                        kind="bot",
                        bot_brain=RandomLegalBot(),
                    )
                )

        hands = _deal_hands(seats, rng if rng is not None else random.Random(seed))
        starting_seat_id = _find_card_holder(hands, Card.from_text("3D"))
        return cls(seats=seats, hands=hands, current_turn_seat_id=starting_seat_id)

    @property
    def seat_order(self) -> tuple[str, ...]:
        return tuple(seat.seat_id for seat in self.seats)

    def create_observation(self, seat_id: str, memory_window: int = 8) -> Observation:
        self._require_known_seat(seat_id)
        return Observation(
            my_seat_id=seat_id,
            my_hand=tuple(self.hands[seat_id]),
            seat_order=self.seat_order,
            current_turn_seat_id=self.current_turn_seat_id,
            current_play=self.current_play,
            current_trick_leader=self.current_trick_leader,
            passed_seat_ids=frozenset(self.passed_seat_ids),
            card_counts_by_seat=self._card_counts_by_seat(),
            is_starting_new_trick=self.current_play is None,
            must_include_card=self._must_include_card(),
            recent_events=tuple(self.public_history[-memory_window:]),
            memory_window=memory_window,
        )

    def get_public_state(self) -> PublicState:
        return PublicState(
            seat_order=self.seat_order,
            seats=tuple(PublicSeat(seat.seat_id, seat.name, seat.kind) for seat in self.seats),
            current_turn_seat_id=self.current_turn_seat_id,
            current_play=self.current_play,
            current_trick_leader=self.current_trick_leader,
            passed_seat_ids=frozenset(self.passed_seat_ids),
            card_counts_by_seat=self._card_counts_by_seat(),
            winner=self.winner,
            is_starting_new_trick=self.current_play is None,
            must_include_card=self._must_include_card(),
        )

    def apply_move(self, seat_id: str, move: Move | PassMove) -> PublicEvent:
        self._require_can_act(seat_id)
        if isinstance(move, PassMove):
            return self.pass_turn(seat_id)

        cards = tuple(move.cards)
        self._validate_play(seat_id, cards)
        hand = self.hands[seat_id]
        for card in cards:
            hand.remove(card)

        self.current_play = Play(seat_id=seat_id, cards=cards)
        self.current_trick_leader = seat_id
        self.passed_seat_ids.clear()
        self.turn_number += 1
        event = PlayedEvent(
            turn_number=self.turn_number,
            trick_number=self.trick_number,
            seat_id=seat_id,
            cards=cards,
            play_kind=classify_play(cards).category.name.lower(),
        )
        self.public_history.append(event)

        if not hand:
            self.winner = seat_id
            self.public_history.append(
                WinEvent(turn_number=self.turn_number, trick_number=self.trick_number, seat_id=seat_id)
            )
        else:
            self.current_turn_seat_id = self._next_seat_after(seat_id)

        return event

    def pass_turn(self, seat_id: str) -> PublicEvent:
        self._require_can_act(seat_id)
        if self.current_play is None:
            raise InvalidMoveError("Cannot pass when starting a new trick")
        if seat_id == self.current_trick_leader:
            raise InvalidMoveError("Trick leader cannot pass against their own play")

        self.passed_seat_ids.add(seat_id)
        self.turn_number += 1
        event = PassedEvent(turn_number=self.turn_number, trick_number=self.trick_number, seat_id=seat_id)
        self.public_history.append(event)

        if len(self.passed_seat_ids) == len(self.seats) - 1:
            leader = self.current_trick_leader
            self.current_play = None
            self.passed_seat_ids.clear()
            self.current_turn_seat_id = leader or seat_id
            self.public_history.append(
                TrickResetEvent(
                    turn_number=self.turn_number,
                    trick_number=self.trick_number,
                    new_leader_seat_id=leader,
                )
            )
            self.trick_number += 1
        else:
            self.current_turn_seat_id = self._next_unpassed_seat_after(seat_id)

        return event

    def _validate_play(self, seat_id: str, cards: tuple[Card, ...]) -> None:
        if len(cards) not in (1, 2, 3, 5):
            raise InvalidMoveError("A play must contain 1, 2, 3, or 5 cards")
        if len(set(cards)) != len(cards):
            raise InvalidMoveError("A play cannot contain duplicate cards")

        hand = self.hands[seat_id]
        missing_cards = [card for card in cards if card not in hand]
        if missing_cards:
            raise InvalidMoveError(f"Seat {seat_id!r} does not hold all played cards")

        required_card = self._must_include_card()
        if required_card is not None and required_card not in cards:
            raise InvalidMoveError(f"First play must include {required_card}")

        if self.current_play is not None and len(cards) != len(self.current_play.cards):
            raise InvalidMoveError("A play must match the current play's card count")

        try:
            classify_play(cards)
        except InvalidPlayError as exc:
            raise InvalidMoveError(str(exc)) from exc

        if self.current_play is not None and not can_beat(cards, self.current_play.cards):
            raise InvalidMoveError("Play does not beat the current play")

        if len(cards) == len(hand):
            two_spades = Card.from_text("2S")
            if two_spades in cards:
                raise InvalidMoveError("Cannot end the game on the 2 of Spades")

    def _require_can_act(self, seat_id: str) -> None:
        self._require_known_seat(seat_id)
        if self.winner is not None:
            raise InvalidMoveError("Game is already over")
        if seat_id != self.current_turn_seat_id:
            raise NotPlayersTurnError(f"It is {self.current_turn_seat_id!r}'s turn")

    def _require_known_seat(self, seat_id: str) -> None:
        if seat_id not in self.hands:
            raise UnknownSeatError(f"Unknown seat: {seat_id!r}")

    def _card_counts_by_seat(self) -> dict[str, int]:
        return {seat_id: len(self.hands[seat_id]) for seat_id in self.seat_order}

    def _played_cards(self) -> tuple[Card, ...]:
        return tuple(
            card
            for event in self.public_history
            if isinstance(event, PlayedEvent)
            for card in event.cards
        )

    def _must_include_card(self) -> Card | None:
        three_diamonds = Card.from_text("3D")
        if not self._played_cards() and any(three_diamonds in hand for hand in self.hands.values()):
            return three_diamonds
        return None

    def _next_seat_after(self, seat_id: str) -> str:
        seat_order = self.seat_order
        start = seat_order.index(seat_id)
        return seat_order[(start + 1) % len(seat_order)]

    def _next_unpassed_seat_after(self, seat_id: str) -> str:
        seat_order = self.seat_order
        start = seat_order.index(seat_id)
        for offset in range(1, len(seat_order) + 1):
            candidate = seat_order[(start + offset) % len(seat_order)]
            if candidate not in self.passed_seat_ids:
                return candidate
        raise InvalidMoveError("No unpassed seat is available")


def _deal_hands(seats: list[PlayerSeat], rng: random.Random) -> dict[str, list[Card]]:
    deck = list(create_standard_deck())
    rng.shuffle(deck)
    hands = {seat.seat_id: [] for seat in seats}
    for index, card in enumerate(deck):
        hands[seats[index % len(seats)].seat_id].append(card)
    for hand in hands.values():
        hand.sort()
    return hands


def _find_card_holder(hands: dict[str, list[Card]], card: Card) -> str:
    for seat_id, hand in hands.items():
        if card in hand:
            return seat_id
    raise InvalidMoveError(f"No seat holds required starting card {card}")


def recent_events_by_seat(observation: Observation, seat_id: str) -> list[PublicEvent]:
    return [
        event
        for event in observation.recent_events
        if _event_seat_id(event) == seat_id
    ]


def recent_passes_by_seat(observation: Observation, seat_id: str) -> list[PassedEvent]:
    return [
        event
        for event in observation.recent_events
        if isinstance(event, PassedEvent) and event.seat_id == seat_id
    ]


def recent_plays_by_seat(observation: Observation, seat_id: str) -> list[PlayedEvent]:
    return [
        event
        for event in observation.recent_events
        if isinstance(event, PlayedEvent) and event.seat_id == seat_id
    ]


def recently_passed_on_kind(observation: Observation, seat_id: str, play_kind: str) -> bool:
    for index, event in enumerate(observation.recent_events):
        if not isinstance(event, PassedEvent) or event.seat_id != seat_id:
            continue
        current_play = _latest_play_before(observation.recent_events, index)
        if current_play is not None and current_play.play_kind == play_kind:
            return True
    return False


def recently_passed_on_size(observation: Observation, seat_id: str, size: int) -> bool:
    for index, event in enumerate(observation.recent_events):
        if not isinstance(event, PassedEvent) or event.seat_id != seat_id:
            continue
        current_play = _latest_play_before(observation.recent_events, index)
        if current_play is not None and len(current_play.cards) == size:
            return True
    return False


def _event_seat_id(event: PublicEvent) -> str | None:
    if isinstance(event, TrickResetEvent):
        return event.new_leader_seat_id
    if isinstance(event, (PlayedEvent, PassedEvent, WinEvent)):
        return event.seat_id
    return None


def _latest_play_before(events: tuple[PublicEvent, ...], index: int) -> PlayedEvent | None:
    for event in reversed(events[:index]):
        if isinstance(event, TrickResetEvent):
            return None
        if isinstance(event, PlayedEvent):
            return event
    return None
