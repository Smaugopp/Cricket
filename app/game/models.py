from dataclasses import dataclass, field
from enum import Enum
import time

class Phase(str, Enum):
    LOBBY = "lobby"
    BAT = "bat"
    BOWL = "bowl"
    FINISHED = "finished"

@dataclass
class Player:
    uid: int
    name: str

@dataclass
class Innings:
    batter: Player
    bowler: Player
    runs: int = 0
    wickets: int = 0
    balls: int = 0
    fours: int = 0
    sixes: int = 0
    dots: int = 0
    last_ball: int = 0
    history: list = field(default_factory=list)

    def over(self, balls_per_over):
        return f"{self.balls // balls_per_over}.{self.balls % balls_per_over}"

@dataclass
class Match:
    chat_id: int
    creator: Player
    opponent: Player | None = None
    max_overs: int = 2
    balls_per_over: int = 3
    phase: Phase = Phase.LOBBY
    innings_no: int = 1
    innings: Innings | None = None
    first_score: int | None = None
    target: int | None = None
    pending_bat: int | None = None
    pending_bowl_type: int | None = None
    created_at: float = field(default_factory=time.time)
    turn_started_at: float = field(default_factory=time.time)

    def players(self):
        return [self.creator] + ([self.opponent] if self.opponent else [])

    def touch(self):
        self.turn_started_at = time.time()
