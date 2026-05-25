from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from bot import BotBrain, Move, PassMove, RandomLegalBot
from card import Card, create_standard_deck


PlayerKind = Literal["human", "bot"]
PublicEventType = Literal["play", "pass", "trick_reset", "win"]


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
    event_type: PublicEventType
    seat_id: str | None = None
    cards: tuple[Card, ...] = ()


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
    played_cards: tuple[Card, ...]
    recent_history: tuple[PublicEvent, ...]
    is_starting_new_trick: bool
    must_include_card: Card | None


@dataclass(frozen=True)
class PublicState:
    seat_order: tuple[str, ...]
    seats: tuple[PublicSeat, ...]
    current_turn_seat_id: str
    current_play: Play | None
    current_trick_leader: str | None
    passed_seat_ids: frozenset[str]
    card_counts_by_seat: dict[str, int]
    played_cards: tuple[Card, ...]
    winner: str | None
    public_history: tuple[PublicEvent, ...]
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

    @classmethod
    def new(cls, human_count: int, human_names: list[str] | None = None) -> "BigTwoGame":
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

        hands = _deal_hands(seats)
        starting_seat_id = _find_card_holder(hands, Card.from_text("3D"))
        return cls(seats=seats, hands=hands, current_turn_seat_id=starting_seat_id)

    @property
    def seat_order(self) -> tuple[str, ...]:
        return tuple(seat.seat_id for seat in self.seats)

    def create_observation(self, seat_id: str) -> Observation:
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
            played_cards=self._played_cards(),
            recent_history=tuple(self.public_history[-10:]),
            is_starting_new_trick=self.current_play is None,
            must_include_card=self._must_include_card(),
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
            played_cards=self._played_cards(),
            winner=self.winner,
            public_history=tuple(self.public_history),
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
        event = PublicEvent(event_type="play", seat_id=seat_id, cards=cards)
        self.public_history.append(event)

        if not hand:
            self.winner = seat_id
            self.public_history.append(PublicEvent(event_type="win", seat_id=seat_id))
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
        event = PublicEvent(event_type="pass", seat_id=seat_id)
        self.public_history.append(event)

        if len(self.passed_seat_ids) == len(self.seats) - 1:
            leader = self.current_trick_leader
            self.current_play = None
            self.passed_seat_ids.clear()
            self.current_turn_seat_id = leader or seat_id
            self.public_history.append(PublicEvent(event_type="trick_reset", seat_id=leader))
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
        return tuple(card for event in self.public_history for card in event.cards)

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


def _deal_hands(seats: list[PlayerSeat]) -> dict[str, list[Card]]:
    hands = {seat.seat_id: [] for seat in seats}
    for index, card in enumerate(create_standard_deck()):
        hands[seats[index % len(seats)].seat_id].append(card)
    return hands


def _find_card_holder(hands: dict[str, list[Card]], card: Card) -> str:
    for seat_id, hand in hands.items():
        if card in hand:
            return seat_id
    raise InvalidMoveError(f"No seat holds required starting card {card}")
