from dataclasses import dataclass, field
from enum import Enum
import time


class Phase(str, Enum):
    LOBBY = "lobby"
    BAT = "bat"       # waiting for batter
    BOWL = "bowl"     # waiting for bowler
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

    next_batter_index: int = 0
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
    balls_per_over: int = 6
    phase: Phase = Phase.LOBBY
    innings_no: int = 1
    innings: Innings | None = None
    first_score: int | None = None
    target: int | None = None

    # One-v-one: "classic"; team mode: "team"
    mode: str = "classic"

    # Team-mode snapshot. Each side is a list of Player objects.
    team_a: list = field(default_factory=list)
    team_b: list = field(default_factory=list)
    team_a_name: str | None = None
    team_b_name: str | None = None
    team_a_captain: int | None = None
    team_b_captain: int | None = None

    pending_bat: int | None = None
    pending_bowl_type: int | None = None

    created_at: float = field(default_factory=time.time)
    turn_started_at: float = field(default_factory=time.time)

    def players(self):
        if self.mode == "team":
            return self.team_a + self.team_b
        return [self.creator] + ([self.opponent] if self.opponent else [])

    def team_for_uid(self, uid):
        if self.mode != "team":
            return None
        if any(p.uid == uid for p in self.team_a):
            return "a"
        if any(p.uid == uid for p in self.team_b):
            return "b"
        return None

    def captain_for_uid(self, uid):
        if self.mode != "team":
            return uid
        if uid == self.team_a_captain:
            return "a"
        if uid == self.team_b_captain:
            return "b"
        return None

    def controller_uid_for(self, player):
        if self.mode != "team":
            return player.uid
        if player in self.team_a:
            return self.team_a_captain
        if player in self.team_b:
            return self.team_b_captain
        return None

    def touch(self):
        self.turn_started_at = time.time()
