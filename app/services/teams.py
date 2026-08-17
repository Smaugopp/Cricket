from datetime import datetime, timezone
from pymongo.errors import DuplicateKeyError

def utcnow():
    return datetime.now(timezone.utc)

class TeamService:
    def __init__(self, db):
        self.c = db.teams

    @staticmethod
    def key(name):
        return " ".join(name.strip().lower().split())

    async def create(self, chat_id, name, captain_id, captain_name):
        name = " ".join(name.strip().split())
        if not name or len(name) > 24:
            return None, "Team name must be 1–24 characters."
        doc = {
            "chat_id": chat_id, "name": name, "name_key": self.key(name),
            "captain": captain_id, "vice_captain": None,
            "players": [captain_id],
            "player_names": {str(captain_id): captain_name},
            "created_at": utcnow(), "updated_at": utcnow(),
        }
        try:
            result = await self.c.insert_one(doc)
        except DuplicateKeyError:
            return None, "A team with that name already exists in this group."
        doc["_id"] = result.inserted_id
        return doc, None

    async def get(self, chat_id, name):
        return await self.c.find_one({"chat_id": chat_id, "name_key": self.key(name)})

    async def my_team(self, chat_id, uid):
        return await self.c.find_one({"chat_id": chat_id, "players": uid})

    async def list(self, chat_id, limit=30):
        return await self.c.find({"chat_id": chat_id}).sort("name_key", 1).limit(limit).to_list(length=limit)

    async def add_player(self, team, uid, name):
        if uid in team.get("players", []):
            return False, "Player is already in the squad."
        if len(team.get("players", [])) >= 15:
            return False, "Squad limit is 15 players."
        # Prevent membership in two teams in the same group.
        other = await self.c.find_one({"chat_id": team["chat_id"], "players": uid, "_id": {"$ne": team["_id"]}})
        if other:
            return False, f"Player is already in {other['name']}."
        result = await self.c.update_one(
            {"_id": team["_id"], "players": {"$ne": uid}},
            {"$addToSet": {"players": uid},
             "$set": {f"player_names.{uid}": name, "updated_at": utcnow()}}
        )
        return bool(result.modified_count), "Player added to the squad."

    async def remove_player(self, team, uid):
        if uid == team["captain"]:
            return False, "Captain cannot be removed. Transfer captaincy first."
        if uid not in team.get("players", []):
            return False, "Player is not in this squad."
        await self.c.update_one(
            {"_id": team["_id"]},
            {"$pull": {"players": uid},
             "$unset": {f"player_names.{uid}": ""},
             "$set": {"updated_at": utcnow()}}
        )
        return True, "Player removed from the squad."

    async def transfer_captain(self, team, uid):
        if uid not in team.get("players", []):
            return False, "New captain must already be in the squad."
        await self.c.update_one({"_id": team["_id"]}, {"$set": {"captain": uid, "updated_at": utcnow()}})
        return True, "Captaincy transferred."

    async def set_vice_captain(self, team, uid):
        if uid not in team.get("players", []):
            return False, "Vice-captain must already be in the squad."
        await self.c.update_one({"_id": team["_id"]}, {"$set": {"vice_captain": uid, "updated_at": utcnow()}})
        return True, "Vice-captain updated."

    async def leave(self, team, uid):
        if uid == team["captain"]:
            return False, "Captain must transfer captaincy before leaving."
        if uid not in team.get("players", []):
            return False, "You are not in this squad."
        await self.c.update_one(
            {"_id": team["_id"]},
            {"$pull": {"players": uid},
             "$unset": {f"player_names.{uid}": ""},
             "$set": {"updated_at": utcnow()}}
        )
        return True, "You left the squad."

    async def disband(self, team):
        await self.c.delete_one({"_id": team["_id"]})

    async def set_xi(self, team, players):
        roster = set(team.get("players", []))
        players = list(dict.fromkeys(players))
        if len(players) not in {4, 5}:
            return False, "Match players must contain exactly 4 or 5 players."
        if any(uid not in roster for uid in players):
            return False, "Every XI player must belong to the squad."
        await self.c.update_one({"_id": team["_id"]},
            {"$set":{"playing_xi":players,"updated_at":utcnow()}})
        return True, "Playing XI saved."

    async def clear_xi(self, team):
        await self.c.update_one({"_id":team["_id"]},
            {"$unset":{"playing_xi":""},"$set":{"updated_at":utcnow()}})
        return True

    async def set_role(self, team, uid, role):
        if uid not in team.get("players", []):
            return False, "Player is not in this squad."
        if role not in {"keeper","all_rounder","batter","bowler"}:
            return False, "Invalid role."
        roles=team.get("roles", {})
        roles[str(uid)]=role
        await self.c.update_one({"_id":team["_id"]},{"$set":{"roles":roles,"updated_at":utcnow()}})
        return True, f"Role set to {role}."


    async def set_match_xi(self, team, players):
        roster = set(team.get("players", []))
        players = list(dict.fromkeys(players))
        if len(players) not in {4, 5}:
            return False, "Match XI must contain exactly 4 or 5 players."
        if any(uid not in roster for uid in players):
            return False, "Every match player must belong to the squad."
        await self.c.update_one(
            {"_id": team["_id"]},
            {"$set": {"match_xi": players, "updated_at": utcnow()}},
        )
        return True, "Match XI saved."

    async def clear_match_xi(self, team):
        await self.c.update_one(
            {"_id": team["_id"]},
            {"$unset": {"match_xi": ""}, "$set": {"updated_at": utcnow()}},
        )
        return True

    async def match_roster(self, team):
        """Return the 4/5-player roster used for a team match."""
        xi = team.get("match_xi") or []
        if len(xi) in {4, 5}:
            names = team.get("player_names", {})
            return [{"uid": uid, "name": names.get(str(uid), str(uid))} for uid in xi]

        players = team.get("players", [])
        if len(players) in {4, 5}:
            names = team.get("player_names", {})
            return [{"uid": uid, "name": names.get(str(uid), str(uid))} for uid in players]

        return []
