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
    """Pure-ish match engine. Telegram handlers only orchestrate turns/messages."""

    def _new_innings(self, batting, bowling, bat_captain=None, bowl_captain=None):
        if len(batting) >= 2:
            batter, non_striker = batting[0], batting[1]
            next_index = 2
        else:
            batter = batting[0]
            non_striker = None
            next_index = 1
        return Innings(
            batter=batter,
            non_striker=non_striker,
            bowler=bowling[0],
            batting_team=list(batting),
            bowling_team=list(bowling),
            batting_captain=bat_captain,
            bowling_captain=bowl_captain,
            next_batter_index=next_index,
            bowler_index=0,
        )

    def start(self, match):
        assert match.opponent

        if match.team_mode:
            assert len(match.team_a) >= 2 and len(match.team_b) >= 1
            if random.choice([True, False]):
                batting, bowling = match.team_a, match.team_b
                bat_cap, bowl_cap = match.team_a_captain, match.team_b_captain
            else:
                batting, bowling = match.team_b, match.team_a
                bat_cap, bowl_cap = match.team_b_captain, match.team_a_captain
            match.innings = self._new_innings(batting, bowling, bat_cap, bowl_cap)
        else:
            if random.choice([True, False]):
                batter, bowler = match.creator, match.opponent
            else:
                batter, bowler = match.opponent, match.creator
            match.innings = Innings(
                batter=batter,
                bowler=bowler,
                batting_team=[batter],
                bowling_team=[bowler],
                batting_captain=batter,
                bowling_captain=bowler,
                next_batter_index=1,
            )

        match.phase = Phase.BAT
        match.touch()

    def _is_owner_batting(self, match, innings, owner_id):
        if match.team_mode:
            return bool(innings.batting_captain and innings.batting_captain.uid == owner_id)
        return innings.batter.uid == owner_id

    def _is_owner_bowling(self, match, innings, owner_id):
        if match.team_mode:
            return bool(innings.bowling_captain and innings.bowling_captain.uid == owner_id)
        return innings.bowler.uid == owner_id

    def next_batter(self, innings):
        while innings.next_batter_index < len(innings.batting_team):
            player = innings.batting_team[innings.next_batter_index]
            innings.next_batter_index += 1
            if player.uid not in innings.dismissed:
                return player
        return None

    def change_bowler(self, match):
        i = match.innings
        if not i or not i.bowling_team:
            return

        previous = i.bowler.uid
        i.last_over_bowler_uid = previous
        total = len(i.bowling_team)

        # Prefer the next player in rotation who did not bowl the just-ended over.
        for offset in range(1, total + 1):
            idx = (i.bowler_index + offset) % total
            candidate = i.bowling_team[idx]
            if candidate.uid != previous:
                i.bowler_index = idx
                i.bowler = candidate
                return

    def swap_strike(self, innings):
        if innings.non_striker is not None:
            innings.batter, innings.non_striker = innings.non_striker, innings.batter

    def play(self, match, bat, bowl, owner_id):
        i = match.innings
        assert i

        bat = int(bat)
        bowl = int(bowl)
        if bat not in range(1, 7) or bowl not in BOWLING_TYPES:
            raise ValueError("bat and bowl must be 1-6")

        ball_type, ball_emoji = BOWLING_TYPES[bowl]
        # Snapshot the batter/bowler for history before state can rotate.
        batter_before = i.batter
        bowler_before = i.bowler
        i.balls += 1

        if self._is_owner_batting(match, i, owner_id):
            runs, wicket = random.choice([4, 6]), False
            text = "👑 OWNER POWER! " + ("🔥 FOUR!" if runs == 4 else "💥 SIX!")
        elif self._is_owner_bowling(match, i, owner_id):
            runs, wicket = 0, True
            text = "👑 OWNER BOWLING POWER! 🎯 WICKET!"
        elif bat == bowl:
            runs, wicket = 0, True
            text = f"🎯 WICKET! {ball_emoji} {ball_type} beats the shot."
        else:
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
            if batter_before.uid not in i.dismissed:
                i.dismissed.append(batter_before.uid)
            incoming = self.next_batter(i)
            if incoming is not None:
                # Wicket replaces the striker. Bowler remains unchanged.
                i.batter = incoming
        else:
            i.runs += runs
            if runs == 4:
                i.fours += 1
            elif runs == 6:
                i.sixes += 1
            elif runs == 0:
                i.dots += 1

            if runs % 2 == 1:
                self.swap_strike(i)

        # Over-end rotation happens after the legal delivery.
        over_complete = i.balls % match.balls_per_over == 0
        if over_complete:
            self.swap_strike(i)
            self.change_bowler(match)

        i.last_ball = runs
        i.history.append({
            "runs": runs,
            "wicket": wicket,
            "bat": bat,
            "bowl": bowl,
            "ball_type": ball_type,
            "batter_uid": batter_before.uid,
            "batter_name": batter_before.name,
            "bowler_uid": bowler_before.uid,
            "bowler_name": bowler_before.name,
            "over_complete": over_complete,
        })
        match.touch()
        return Result(runs, wicket, text, ball_type, ball_emoji)

    def innings_complete(self, match):
        i = match.innings
        if not i:
            return False
        max_balls = match.max_overs * match.balls_per_over
        if match.target is not None and i.runs >= match.target:
            return True
        if i.balls >= max_balls:
            return True
        # 10 wickets ends a normal 11-player innings. For the simplified
        # 1-v-1 mode, a wicket ends the innings too.
        if match.team_mode and len(i.batting_team) > 1:
            return i.wickets >= len(i.batting_team) - 1
        return i.wickets >= 1

    def switch(self, match):
        old = match.innings
        assert old and match.opponent

        match.first_score = old.runs
        match.target = old.runs + 1
        match.innings_no = 2

        if match.team_mode:
            batting = old.bowling_team
            bowling = old.batting_team
            bat_cap = old.bowling_captain
            bowl_cap = old.batting_captain
            match.innings = self._new_innings(batting, bowling, bat_cap, bowl_cap)
        else:
            match.innings = Innings(
                batter=old.bowler,
                bowler=old.batter,
                batting_team=[old.bowler],
                bowling_team=[old.batter],
                batting_captain=old.bowler,
                bowling_captain=old.batter,
                next_batter_index=1,
            )

        match.phase = Phase.BAT
        match.pending_bat = None
        match.pending_bowl_type = None
        match.touch()

    def winner(self, match):
        i = match.innings
        if not i or match.innings_no != 2 or match.target is None:
            return None
        if i.runs >= match.target:
            return i.batting_captain.uid if i.batting_captain else i.batter.uid
        max_balls = match.max_overs * match.balls_per_over
        if i.balls >= max_balls or (
            match.team_mode and i.wickets >= len(i.batting_team) - 1
        ):
            if i.runs == match.target - 1:
                return 0
            return i.bowling_captain.uid if i.bowling_captain else i.bowler.uid
        return None
