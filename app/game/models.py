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
    non_striker: Player | None = None

    batting_team: list = field(default_factory=list)
    bowling_team: list = field(default_factory=list)
    batting_captain: Player | None = None
    bowling_captain: Player | None = None

    next_batter_index: int = 2
    bowler_index: int = 0
    dismissed: list = field(default_factory=list)
    last_over_bowler_uid: int | None = None

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

    # Team-match state.  /play remains the classic 1-v-1 mode.
    team_mode: bool = False
    team_a_name: str | None = None
    team_b_name: str | None = None
    team_a: list = field(default_factory=list)
    team_b: list = field(default_factory=list)
    team_a_captain: Player | None = None
    team_b_captain: Player | None = None

    def players(self):
        return [self.creator] + ([self.opponent] if self.opponent else [])

    def touch(self):
        self.turn_started_at = time.time()
