import time
from app.game.models import Match, Player, Innings, Phase


def _player_doc(p):
    return {"uid": p.uid, "name": p.name}


def _players_doc(players):
    return [_player_doc(p) for p in (players or [])]


def _players_from(doc):
    return [Player(int(p["uid"]), p["name"]) for p in (doc or [])]


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
            "creator": _player_doc(match.creator),
            "opponent": _player_doc(match.opponent) if match.opponent else None,
            "max_overs": match.max_overs,
            "balls_per_over": match.balls_per_over,
            "phase": match.phase.value,
            "innings_no": match.innings_no,
            "first_score": match.first_score,
            "target": match.target,
            "mode": match.mode,
            "team_a": _players_doc(match.team_a),
            "team_b": _players_doc(match.team_b),
            "team_a_name": match.team_a_name,
            "team_b_name": match.team_b_name,
            "team_a_captain": match.team_a_captain,
            "team_b_captain": match.team_b_captain,
            "pending_bat": match.pending_bat,
            "pending_bowl_type": match.pending_bowl_type,
            "created_at": match.created_at,
            "turn_started_at": match.turn_started_at,
        }

        if match.innings:
            i = match.innings
            doc["innings"] = {
                "batter": _player_doc(i.batter),
                "bowler": _player_doc(i.bowler),
                "non_striker": _player_doc(i.non_striker) if i.non_striker else None,
                "batting_team": _players_doc(i.batting_team),
                "bowling_team": _players_doc(i.bowling_team),
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
            creator=Player(doc["creator"]["uid"], doc["creator"]["name"]),
            opponent=Player(doc["opponent"]["uid"], doc["opponent"]["name"]) if doc.get("opponent") else None,
            max_overs=doc.get("max_overs", 2),
            balls_per_over=doc.get("balls_per_over", 3),
            phase=Phase(doc.get("phase", "lobby")),
            innings_no=doc.get("innings_no", 1),
            first_score=doc.get("first_score"),
            target=doc.get("target"),
            mode=doc.get("mode", "classic"),
            team_a=_players_from(doc.get("team_a")),
            team_b=_players_from(doc.get("team_b")),
            team_a_name=doc.get("team_a_name"),
            team_b_name=doc.get("team_b_name"),
            team_a_captain=doc.get("team_a_captain"),
            team_b_captain=doc.get("team_b_captain"),
            pending_bat=doc.get("pending_bat"),
            pending_bowl_type=doc.get("pending_bowl_type"),
        )
        match.created_at = doc.get("created_at", time.time())
        match.turn_started_at = doc.get("turn_started_at", time.time())

        i = doc.get("innings")
        if i:
            match.innings = Innings(
                batter=Player(i["batter"]["uid"], i["batter"]["name"]),
                bowler=Player(i["bowler"]["uid"], i["bowler"]["name"]),
                non_striker=Player(i["non_striker"]["uid"], i["non_striker"]["name"]) if i.get("non_striker") else None,
                batting_team=_players_from(i.get("batting_team")),
                bowling_team=_players_from(i.get("bowling_team")),
                next_batter_index=i.get("next_batter_index", 0),
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
        return match
