import random
from dataclasses import dataclass
from app.game.models import Innings, Match, Phase

BOWLING_TYPES = {
    1: ("Swing", "🌪️"),
    2: ("Yorker", "🎯"),
    3: ("Bouncer", "⬆️"),
    4: ("Slower Ball", "🐢"),
    5: ("Inswing", "↩️"),
    6: ("Outswing", "↪️"),
}

@dataclass
class Result:
    runs: int
    wicket: bool
    text: str
    ball_type: str
    ball_emoji: str

class CricketEngine:
    def start(self, match):
        assert match.opponent
        batter, bowler = (
            (match.creator, match.opponent)
            if random.choice([True, False])
            else (match.opponent, match.creator)
        )
        match.innings = Innings(batter=batter, bowler=bowler)
        match.phase = Phase.BAT
        match.touch()

    def play(self, match, bat, bowl, owner_id):
        i = match.innings
        assert i
        ball_type, ball_emoji = BOWLING_TYPES.get(int(bowl), ("Unknown", "🏏"))
        i.balls += 1

        if i.batter.uid == owner_id:
            runs, wicket = random.choice([4, 6]), False
            text = "👑 OWNER POWER! " + ("🔥 FOUR!" if runs == 4 else "💥 SIX!")
        elif i.bowler.uid == owner_id:
            runs, wicket = 0, True
            text = "👑 OWNER BOWLING POWER! 🎯 WICKET!"
        elif bat == bowl:
            runs, wicket = 0, True
            text = f"🎯 WICKET! {ball_emoji} {ball_type} beats the shot."
        else:
            # Batter's 1–6 remains the scoring choice. Bowling input is the
            # delivery type, not a run value.
            runs, wicket = bat, False
            if runs == 6:
                text = f"💥 SIX! {ball_emoji} {ball_type}"
            elif runs == 4:
                text = f"🔥 FOUR! {ball_emoji} {ball_type}"
            elif runs == 0:
                text = f"🛡 DOT BALL! {ball_emoji} {ball_type}"
            else:
                text = f"🏏 {runs} RUNS! {ball_emoji} {ball_type}"

        if wicket:
            i.wickets += 1
        else:
            i.runs += runs
        if runs == 4:
            i.fours += 1
        if runs == 6:
            i.sixes += 1
        if runs == 0 and not wicket:
            i.dots += 1

        i.last_ball = runs
        i.history.append({
            "runs": runs,
            "wicket": wicket,
            "bat": bat,
            "bowl": bowl,
            "ball_type": ball_type,
        })
        match.touch()
        return Result(runs, wicket, text, ball_type, ball_emoji)

    def innings_complete(self, match):
        i = match.innings
        return bool(
            i and (
                i.balls >= match.max_overs * match.balls_per_over
                or (match.target is not None and i.runs >= match.target)
            )
        )

    def switch(self, match):
        old = match.innings
        assert old and match.opponent
        match.first_score = old.runs
        match.target = old.runs + 1
        match.innings_no = 2
        match.innings = Innings(batter=old.bowler, bowler=old.batter)
        match.phase = Phase.BAT
        match.pending_bat = None
        match.touch()

    def winner(self, match):
        i = match.innings
        if not i or match.innings_no != 2 or match.target is None:
            return None
        if i.runs >= match.target:
            return i.batter.uid
        if i.balls >= match.max_overs * match.balls_per_over:
            if i.runs == match.target - 1:
                return 0
            return i.bowler.uid
        return None
