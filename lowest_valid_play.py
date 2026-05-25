from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from logic import Strategy, Move, PassMove, generate_legal_plays
from rules import play_strength

if TYPE_CHECKING:
    from game import Observation


@dataclass
class LowestValidPlay(Strategy):
    def choose_move(self, observation: "Observation") -> Move | PassMove:
        legal_plays = generate_legal_plays(
            hand=observation.my_hand,
            current_play=observation.current_play,
            must_include=observation.must_include_card,
        )
        if not legal_plays:
            return PassMove()
        return Move(cards=list(sorted(legal_plays, key=play_strength)[0]))
