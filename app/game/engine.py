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
    def _new_innings(self, batting, bowling):
        if len(batting) >= 2:
            striker, non_striker = batting[0], batting[1]
            next_index = 2
        else:
            striker, non_striker = batting[0], None
            next_index = 1

        return Innings(
            batter=striker,
            non_striker=non_striker,
            bowler=bowling[0],
            batting_team=list(batting),
            bowling_team=list(bowling),
            next_batter_index=next_index,
            bowler_index=0,
        )

    def start(self, match):
        """Start a classic 1-v-1 match. Bowling happens before batting."""
        assert match.opponent
        match.mode = "classic"

        if random.choice([True, False]):
            batting = [match.creator, match.opponent]
        else:
            batting = [match.opponent, match.creator]

        bowling = [p for p in [match.creator, match.opponent] if p.uid != batting[0].uid]
        match.innings = self._new_innings(batting, bowling)
        match.phase = Phase.BOWL
        match.pending_bat = None
        match.pending_bowl_type = None
        match.touch()

    def start_team(self, match, batting_side):
        """Start a team match after both captains have joined."""
        assert match.mode == "team"
        if batting_side == "a":
            batting, bowling = match.team_a, match.team_b
        else:
            batting, bowling = match.team_b, match.team_a

        match.innings = self._new_innings(batting, bowling)
        match.phase = Phase.BOWL
        match.pending_bat = None
        match.pending_bowl_type = None
        match.touch()

    def _controller_uid(self, match, player):
        return match.controller_uid_for(player)

    def _swap_strike(self, i):
        if i.non_striker:
            i.batter, i.non_striker = i.non_striker, i.batter

    def _next_batter(self, i):
        while i.next_batter_index < len(i.batting_team):
            player = i.batting_team[i.next_batter_index]
            i.next_batter_index += 1
            if player.uid not in i.dismissed:
                return player
        return None

    def _change_bowler(self, match):
        i = match.innings
        if not i or not i.bowling_team:
            return

        old = i.bowler
        i.last_over_bowler_uid = old.uid
        total = len(i.bowling_team)

        # Prefer a different bowler; with one-player bowling sides,
        # retaining the same bowler is the only possible option.
        for step in range(1, total + 1):
            idx = (i.bowler_index + step) % total
            candidate = i.bowling_team[idx]
            if total == 1 or candidate.uid != old.uid:
                i.bowler_index = idx
                i.bowler = candidate
                return

    def play(self, match, bat, bowl, owner_id):
        i = match.innings
        assert i

        ball_type, ball_emoji = BOWLING_TYPES.get(
            int(bowl), ("Unknown", "🏏")
        )

        # The current batter and bowler are captured before state changes.
        striker_before = i.batter
        bowler_before = i.bowler
        i.balls += 1

        # Owner powers work for the actual player in classic mode and for
        # the captain controlling that side in team mode.
        batter_controller = self._controller_uid(match, striker_before)
        bowler_controller = self._controller_uid(match, bowler_before)

        if batter_controller == owner_id:
            runs, wicket = random.choice([4, 6]), False
            text = "👑 OWNER POWER! " + (
                "🔥 FOUR!" if runs == 4 else "💥 SIX!"
            )
        elif bowler_controller == owner_id:
            runs, wicket = 0, True
            text = "👑 OWNER BOWLING POWER! 🎯 WICKET!"
        elif int(bat) == int(bowl):
            runs, wicket = 0, True
            text = f"🎯 WICKET! {ball_emoji} {ball_type} beats the shot."
        else:
            runs, wicket = int(bat), False
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
            if striker_before.uid not in i.dismissed:
                i.dismissed.append(striker_before.uid)

            replacement = self._next_batter(i)
            if replacement is not None:
                # A normal wicket in this game dismisses the striker.
                replacement_before = i.batter
                i.batter = replacement
        else:
            i.runs += runs
            if runs == 4:
                i.fours += 1
            elif runs == 6:
                i.sixes += 1
            elif runs == 0:
                i.dots += 1

            # Odd completed runs change ends.
            if runs % 2 == 1:
                self._swap_strike(i)

        i.last_ball = runs
        i.history.append({
            "runs": runs,
            "wicket": wicket,
            "bat": int(bat),
            "bowl": int(bowl),
            "ball_type": ball_type,
            "batter_uid": striker_before.uid,
            "bowler_uid": bowler_before.uid,
        })

        # End of over: swap ends, then rotate the bowler. This happens
        # after the delivery has been resolved, so the current bowler
        # always completes the over.
        over_complete = (
            i.balls % match.balls_per_over == 0
        )
        if over_complete:
            self._swap_strike(i)
            self._change_bowler(match)

        match.touch()
        return Result(
            runs=runs,
            wicket=wicket,
            text=text,
            ball_type=ball_type,
            ball_emoji=ball_emoji,
        )

    def innings_complete(self, match):
        i = match.innings
        if not i:
            return False

        max_balls = match.max_overs * match.balls_per_over

        if match.target is not None and i.runs >= match.target:
            return True

        if i.balls >= max_balls:
            return True

        if match.mode == "classic":
            # In 1-v-1, a wicket ends the innings/match.
            return i.wickets >= 1

        # Team match: last available batter is out => all out.
        return bool(i.batting_team) and (
            i.wickets >= len(i.batting_team) - 1
        )

    def switch(self, match):
        old = match.innings
        assert old and match.opponent

        match.first_score = old.runs
        match.target = old.runs + 1
        match.innings_no = 2

        if match.mode == "team":
            if old.batting_team == match.team_a:
                batting = match.team_b
                bowling = match.team_a
            else:
                batting = match.team_a
                bowling = match.team_b
            match.innings = self._new_innings(batting, bowling)
        else:
            match.innings = self._new_innings(
                [old.bowler, old.batter],
                [old.batter, old.bowler],
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
                return (
                    match.team_a_captain
                    if i.batting_team == match.team_a
                    else match.team_b_captain
                )
            return i.batter.uid

        max_balls = match.max_overs * match.balls_per_over
        all_out = (
            match.mode == "classic" and i.wickets >= 1
        ) or (
            match.mode == "team"
            and bool(i.batting_team)
            and i.wickets >= len(i.batting_team) - 1
        )

        if i.balls >= max_balls or all_out:
            if i.runs == match.target - 1:
                return 0
            if match.mode == "team":
                return (
                    match.team_a_captain
                    if i.bowling_team == match.team_a
                    else match.team_b_captain
                )
            return i.bowler.uid

        return None
