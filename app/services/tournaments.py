from datetime import datetime, timezone
import random

def utcnow():
    return datetime.now(timezone.utc)

class TournamentService:
    def __init__(self, db):
        self.c = db.tournaments

    async def create(self, chat_id, name, owner, overs=2):
        name = " ".join(name.strip().split())
        if not name or len(name) > 32:
            return None, "Tournament name must be 1–32 characters."
        if overs not in {1, 2, 5, 10, 20}:
            return None, "Overs must be 1, 2, 5, 10 or 20."
        doc = {
            "chat_id": chat_id, "name": name, "overs": overs, "owner": owner,
            "status": "open", "participants": [], "round": 0, "rounds": [],
            "champion": None, "created_at": utcnow(), "updated_at": utcnow(),
        }
        result = await self.c.insert_one(doc)
        doc["_id"] = result.inserted_id
        return doc, None

    async def get(self, tid):
        return await self.c.find_one({"_id": tid})

    async def join(self, tournament, uid, name):
        if tournament["status"] != "open":
            return False, "Tournament is no longer open."
        if len(tournament.get("participants", [])) >= 16:
            return False, "Maximum 16 players."
        if any(p["id"] == uid for p in tournament.get("participants", [])):
            return False, "Already registered."
        await self.c.update_one(
            {"_id": tournament["_id"]},
            {"$push": {"participants": {"id": uid, "name": name}},
             "$set": {"updated_at": utcnow()}}
        )
        return True, "Joined tournament."

    @staticmethod
    def make_round(participants):
        participants = list(participants)
        random.shuffle(participants)
        # Add byes until the field can form pairs. A bye is a free advance.
        pairs = []
        while len(participants) >= 2:
            a = participants.pop()
            b = participants.pop()
            pairs.append({"home": a, "away": b, "winner": None, "played": False})
        if participants:
            pairs.append({"home": participants[0], "away": None,
                          "winner": participants[0], "played": True, "bye": True})
        return pairs

    async def start(self, tournament):
        if tournament["status"] != "open":
            return False, "Tournament is already running."
        players = tournament.get("participants", [])
        if len(players) < 2:
            return False, "Need at least 2 players."
        pairs = self.make_round(players)
        await self.c.update_one(
            {"_id": tournament["_id"]},
            {"$set": {"status": "running", "round": 1, "rounds": [pairs],
                      "updated_at": utcnow()}}
        )
        return True, f"Knockout started with {len(players)} players."

    async def record(self, tournament, match_index, winner_side):
        if tournament["status"] != "running":
            return False, "Tournament is not running."
        rounds = tournament.get("rounds", [])
        if not rounds:
            return False, "Bracket not initialized."
        current = rounds[-1]
        if match_index < 0 or match_index >= len(current):
            return False, "Invalid match number."
        match = current[match_index]
        if match.get("played"):
            return False, "Match already completed."
        if winner_side not in {"home", "away"}:
            return False, "Use HOME or AWAY."
        winner = match[winner_side]
        if not winner:
            return False, "That side has no player."
        match["winner"] = winner
        match["played"] = True

        if not all(x.get("played") for x in current):
            await self.c.update_one({"_id": tournament["_id"]},
                                    {"$set": {"rounds": rounds, "updated_at": utcnow()}})
            return True, "Result recorded."

        winners = [x["winner"] for x in current if x.get("winner")]
        if len(winners) == 1:
            await self.c.update_one(
                {"_id": tournament["_id"]},
                {"$set": {"rounds": rounds, "status": "finished",
                          "champion": winners[0], "updated_at": utcnow()}}
            )
            return True, f"🏆 Champion: {winners[0]['name']}"

        next_round = self.make_round(winners)
        rounds.append(next_round)
        await self.c.update_one(
            {"_id": tournament["_id"]},
            {"$set": {"rounds": rounds, "round": len(rounds), "updated_at": utcnow()}}
        )
        return True, f"Round complete. Round {len(rounds)} is ready."

    async def current_round(self, tournament):
        rounds = tournament.get("rounds", [])
        return rounds[-1] if rounds else []
