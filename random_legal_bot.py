from __future__ import annotations

import random
from dataclasses import dataclass
from typing import TYPE_CHECKING

from bot import BotBrain, Move, PassMove, generate_legal_plays

if TYPE_CHECKING:
    from game import Observation


@dataclass
class RandomLegalBot(BotBrain):
    rng: random.Random

    def __init__(
        self,
        seed: int | str | bytes | bytearray | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self.rng = rng if rng is not None else random.Random(seed)

    def choose_move(self, observation: "Observation") -> Move | PassMove:
        legal_plays = generate_legal_plays(
            hand=observation.my_hand,
            current_play=observation.current_play,
            must_include=observation.must_include_card,
        )
        if not legal_plays:
            return PassMove()
        return Move(cards=list(self.rng.choice(legal_plays)))
