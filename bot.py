from __future__ import annotations

import random
from dataclasses import dataclass
from itertools import combinations
from typing import TYPE_CHECKING

from card import Card
from rules import InvalidPlayError, can_beat, classify_play

if TYPE_CHECKING:
    from game import Observation, Play


@dataclass(frozen=True)
class Move:
    cards: list[Card]


@dataclass(frozen=True)
class PassMove:
    pass


class BotBrain:
    def choose_move(self, observation: "Observation") -> Move | PassMove:
        raise NotImplementedError


def generate_legal_plays(
    hand: list[Card] | tuple[Card, ...],
    current_play: "Play | None",
    must_include: Card | None = None,
) -> list[tuple[Card, ...]]:
    sorted_hand = tuple(sorted(hand))
    if current_play is None:
        sizes = (1, 2, 3, 5)
    else:
        sizes = (len(current_play.cards),)

    legal_plays: list[tuple[Card, ...]] = []
    for size in sizes:
        if size > len(sorted_hand):
            continue
        for cards in combinations(sorted_hand, size):
            if must_include is not None and must_include not in cards:
                continue
            try:
                classify_play(cards)
            except InvalidPlayError:
                continue
            if current_play is not None and not can_beat(cards, current_play.cards):
                continue
            if len(cards) == len(sorted_hand) and Card.from_text("2S") in cards:
                continue
            legal_plays.append(cards)
    return legal_plays
