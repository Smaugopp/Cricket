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
    def _new_innings(self, batting, bowling, classic=False):
        batting = list(batting or [])
        bowling = list(bowling or [])
        if not batting or not bowling:
            raise ValueError("An innings needs at least one batter and one bowler.")

        if classic:
            # True 1v1: exactly one active batter and one bowler.
            return Innings(
                batter=batting[0],
                bowler=bowling[0],
                non_striker=None,
                batting_team=batting[:1],
                bowling_team=bowling[:1],
                next_batter_index=1,
            )

        if len(batting) < 2:
            raise ValueError("A team innings needs at least two batters.")

        return Innings(
            batter=batting[0],
            non_striker=batting[1],
            bowler=bowling[0],
            batting_team=batting,
            bowling_team=bowling,
            next_batter_index=2,
            bowler_index=0,
        )

    def start(self, match):
        """Start a classic 1v1 match: bowler chooses first."""
        assert match.opponent
        match.mode = "classic"

        if random.choice([True, False]):
            batter, bowler = match.creator, match.opponent
        else:
            batter, bowler = match.opponent, match.creator

        match.innings = self._new_innings([batter], [bowler], classic=True)
        match.phase = Phase.BOWL
        match.pending_bat = None
        match.pending_bowl_type = None
        match.touch()

    def start_team(self, match, batting_side):
        """Start a 4/5-player team innings."""
        if match.mode != "team":
            raise ValueError("start_team requires team mode.")

        batting = match.team_a if batting_side == "a" else match.team_b
        bowling = match.team_b if batting_side == "a" else match.team_a

        match.innings = self._new_innings(batting, bowling, classic=False)
        match.phase = Phase.BOWL
        match.pending_bat = None
        match.pending_bowl_type = None
        match.touch()

    def _controller_uid(self, match, player):
        return match.controller_uid_for(player)

    @staticmethod
    def _swap_strike(i):
        if i.non_striker is not None:
            i.batter, i.non_striker = i.non_striker, i.batter

    @staticmethod
    def _next_batter(i):
        while i.next_batter_index < len(i.batting_team):
            player = i.batting_team[i.next_batter_index]
            i.next_batter_index += 1
            if player.uid not in i.dismissed:
                return player
        return None

    def _change_bowler(self, match):
        i = match.innings
        if not i or len(i.bowling_team) <= 1:
            return

        old_uid = i.bowler.uid
        i.last_over_bowler_uid = old_uid
        total = len(i.bowling_team)

        # Prefer a different player from the previous bowler.
        for step in range(1, total + 1):
            idx = (i.bowler_index + step) % total
            candidate = i.bowling_team[idx]
            if candidate.uid != old_uid:
                i.bowler_index = idx
                i.bowler = candidate
                return

    def play(self, match, bat, bowl, owner_id):
        i = match.innings
        if not i:
            raise ValueError("No active innings.")

        bat = int(bat)
        bowl = int(bowl)
        if bat not in range(1, 7) or bowl not in BOWLING_TYPES:
            raise ValueError("Batting and bowling choices must be 1–6.")

        ball_type, ball_emoji = BOWLING_TYPES[bowl]
        striker_before = i.batter
        bowler_before = i.bowler

        i.balls += 1

        batter_controller = self._controller_uid(match, striker_before)
        bowler_controller = self._controller_uid(match, bowler_before)

        if batter_controller == owner_id:
            runs, wicket = random.choice([4, 6]), False
            text = "👑 OWNER POWER  •  " + (
                "🔥 FOUR!" if runs == 4 else "💥 SIX!"
            )
        elif bowler_controller == owner_id:
            runs, wicket = 0, True
            text = "👑 OWNER BOWLING POWER  •  🎯 WICKET!"
        elif bat == bowl:
            runs, wicket = 0, True
            text = f"🎯 WICKET!  {ball_emoji} {ball_type} beats the shot."
        else:
            runs, wicket = bat, False
            if runs == 6:
                text = f"💥 SIX!  {ball_emoji} {ball_type}"
            elif runs == 4:
                text = f"🔥 FOUR!  {ball_emoji} {ball_type}"
            elif runs == 0:
                text = f"🛡 DOT BALL!  {ball_emoji} {ball_type}"
            else:
                text = f"🏏 {runs} RUNS!  {ball_emoji} {ball_type}"

        if wicket:
            i.wickets += 1
            if striker_before.uid not in i.dismissed:
                i.dismissed.append(striker_before.uid)

            if match.mode == "team":
                replacement = self._next_batter(i)
                if replacement is not None:
                    i.batter = replacement
        else:
            i.runs += runs
            if runs == 4:
                i.fours += 1
            elif runs == 6:
                i.sixes += 1
            elif runs == 0:
                i.dots += 1

            if match.mode == "team" and runs % 2 == 1:
                self._swap_strike(i)

        i.last_ball = runs
        i.history.append({
            "runs": runs,
            "wicket": wicket,
            "bat": bat,
            "bowl": bowl,
            "ball_type": ball_type,
            "batter_uid": striker_before.uid,
            "bowler_uid": bowler_before.uid,
        })

        over_complete = i.balls % match.balls_per_over == 0
        if over_complete:
            if match.mode == "team":
                self._swap_strike(i)
                self._change_bowler(match)

        match.touch()
        return Result(runs, wicket, text, ball_type, ball_emoji)

    def innings_complete(self, match):
        i = match.innings
        if not i:
            return False

        if match.target is not None and i.runs >= match.target:
            return True

        if i.balls >= match.max_overs * match.balls_per_over:
            return True

        if match.mode == "classic":
            return i.wickets >= 1

        return bool(i.batting_team) and i.wickets >= len(i.batting_team) - 1

    def switch(self, match):
        old = match.innings
        if not old:
            raise ValueError("No innings to switch.")

        match.first_score = old.runs
        match.target = old.runs + 1
        match.innings_no = 2

        if match.mode == "team":
            if old.batting_team == match.team_a:
                batting, bowling = match.team_b, match.team_a
            else:
                batting, bowling = match.team_a, match.team_b
            match.innings = self._new_innings(batting, bowling, classic=False)
        else:
            # Classic 1v1: roles simply reverse.
            match.innings = self._new_innings(
                [old.bowler], [old.batter], classic=True
            )

        match.phase = Phase.BOWL
        match.pending_bat = None
        match.pending_bowl_type = None
        match.touch()

    def winner(self, match):
        i = match.innings
        if not i or match.innings_no != 2 or match.target is None:
            return None

        if i.runs >= match.target:
            if match.mode == "team":
                return match.team_a_captain if i.batting_team == match.team_a else match.team_b_captain
            return i.batter.uid

        max_balls = match.max_overs * match.balls_per_over
        all_out = (
            (match.mode == "classic" and i.wickets >= 1)
            or (match.mode == "team" and bool(i.batting_team) and i.wickets >= len(i.batting_team) - 1)
        )

        if i.balls >= max_balls or all_out:
            if i.runs == match.target - 1:
                return 0
            if match.mode == "team":
                return match.team_a_captain if i.bowling_team == match.team_a else match.team_b_captain
            return i.bowler.uid

        return None
