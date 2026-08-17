import time
from app.game.models import Match, Player, Innings, Phase


def _player(p):
    return {"uid": p.uid, "name": p.name} if p else None


def _players(items):
    return [_player(p) for p in items]


def _load_player(doc):
    return Player(doc["uid"], doc["name"]) if doc else None


class MatchManager:
    def __init__(self, lobby_ttl=600, match_ttl=7200):
        self.matches = {}
        self.lobby_ttl = lobby_ttl
        self.match_ttl = match_ttl

    def get(self, chat_id):
        return self.matches.get(chat_id)

    def create(self, match):
        self.matches[match.chat_id] = match
        return match

    def remove(self, chat_id):
        return self.matches.pop(chat_id, None)

    def all(self):
        return list(self.matches.values())

    def expired(self):
        now = time.time()
        result = []
        for match in self.matches.values():
            age = now - match.created_at
            ttl = self.lobby_ttl if match.phase == Phase.LOBBY else self.match_ttl
            if age > ttl:
                result.append(match)
        return result

    @staticmethod
    def serialize(match):
        doc = {
            "chat_id": match.chat_id,
            "creator": _player(match.creator),
            "opponent": _player(match.opponent),
            "max_overs": match.max_overs,
            "balls_per_over": match.balls_per_over,
            "phase": match.phase.value,
            "innings_no": match.innings_no,
            "first_score": match.first_score,
            "target": match.target,
            "pending_bat": match.pending_bat,
            "pending_bowl_type": match.pending_bowl_type,
            "created_at": match.created_at,
            "turn_started_at": match.turn_started_at,
            "team_mode": match.team_mode,
            "team_a_name": match.team_a_name,
            "team_b_name": match.team_b_name,
            "team_a": _players(match.team_a),
            "team_b": _players(match.team_b),
            "team_a_captain": _player(match.team_a_captain),
            "team_b_captain": _player(match.team_b_captain),
        }

        if match.innings:
            i = match.innings
            doc["innings"] = {
                "batter": _player(i.batter),
                "bowler": _player(i.bowler),
                "non_striker": _player(i.non_striker),
                "batting_team": _players(i.batting_team),
                "bowling_team": _players(i.bowling_team),
                "batting_captain": _player(i.batting_captain),
                "bowling_captain": _player(i.bowling_captain),
                "next_batter_index": i.next_batter_index,
                "bowler_index": i.bowler_index,
                "dismissed": i.dismissed,
                "last_over_bowler_uid": i.last_over_bowler_uid,
                "runs": i.runs,
                "wickets": i.wickets,
                "balls": i.balls,
                "fours": i.fours,
                "sixes": i.sixes,
                "dots": i.dots,
                "last_ball": i.last_ball,
                "history": i.history,
            }
        else:
            doc["innings"] = None

        return doc

    @staticmethod
    def deserialize(doc):
        match = Match(
            chat_id=doc["chat_id"],
            creator=_load_player(doc["creator"]),
            opponent=_load_player(doc.get("opponent")),
            max_overs=doc.get("max_overs", 2),
            balls_per_over=doc.get("balls_per_over", 3),
            phase=Phase(doc.get("phase", "lobby")),
            innings_no=doc.get("innings_no", 1),
            first_score=doc.get("first_score"),
            target=doc.get("target"),
            pending_bat=doc.get("pending_bat"),
            pending_bowl_type=doc.get("pending_bowl_type"),
            team_mode=doc.get("team_mode", False),
            team_a_name=doc.get("team_a_name"),
            team_b_name=doc.get("team_b_name"),
            team_a=[_load_player(x) for x in doc.get("team_a", [])],
            team_b=[_load_player(x) for x in doc.get("team_b", [])],
            team_a_captain=_load_player(doc.get("team_a_captain")),
            team_b_captain=_load_player(doc.get("team_b_captain")),
        )
        match.created_at = doc.get("created_at", time.time())
        match.turn_started_at = doc.get("turn_started_at", time.time())

        i = doc.get("innings")
        if i:
            # Backward compatible with old live-match documents.
            batting_team = [_load_player(x) for x in i.get("batting_team", [])]
            bowling_team = [_load_player(x) for x in i.get("bowling_team", [])]
            if not batting_team and i.get("batter"):
                batting_team = [_load_player(i["batter"])]
            if not bowling_team and i.get("bowler"):
                bowling_team = [_load_player(i["bowler"])]

            match.innings = Innings(
                batter=_load_player(i["batter"]),
                bowler=_load_player(i["bowler"]),
                non_striker=_load_player(i.get("non_striker")),
                batting_team=batting_team,
                bowling_team=bowling_team,
                batting_captain=_load_player(i.get("batting_captain")),
                bowling_captain=_load_player(i.get("bowling_captain")),
                next_batter_index=i.get("next_batter_index", 1 if len(batting_team) <= 1 else 2),
                bowler_index=i.get("bowler_index", 0),
                dismissed=i.get("dismissed", []),
                last_over_bowler_uid=i.get("last_over_bowler_uid"),
                runs=i.get("runs", 0),
                wickets=i.get("wickets", 0),
                balls=i.get("balls", 0),
                fours=i.get("fours", 0),
                sixes=i.get("sixes", 0),
                dots=i.get("dots", 0),
                last_ball=i.get("last_ball", 0),
                history=i.get("history", []),
            )
            if not match.team_mode:
                if not match.innings.batting_captain:
                    match.innings.batting_captain = match.innings.batter
                if not match.innings.bowling_captain:
                    match.innings.bowling_captain = match.innings.bowler

        return match
