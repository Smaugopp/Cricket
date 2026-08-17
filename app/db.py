from pymongo import AsyncMongoClient

class Database:
    def __init__(self, uri: str, name: str):
        self.client = AsyncMongoClient(uri, serverSelectionTimeoutMS=8000)
        self.db = self.client[name]

    async def ping(self):
        await self.client.admin.command("ping")

    async def close(self):
        self.client.close()

    @property
    def users(self): return self.db.users
    @property
    def matches(self): return self.db.matches
    @property
    def tournaments(self): return self.db.tournaments
    @property
    def sudo(self): return self.db.sudo
    @property
    def teams(self): return self.db.teams
    @property
    def chats(self): return self.db.chats
    @property
    def settings(self): return self.db.settings
    @property
    def live_matches(self): return self.db.live_matches
    @property
    def leagues(self): return self.db.leagues

    async def indexes(self):
        await self.users.create_index("rating")
        await self.users.create_index("xp")
        await self.matches.create_index([("chat_id", 1), ("created_at", -1)])
        await self.matches.create_index("players")
        await self.tournaments.create_index("status")
        await self.tournaments.create_index([("chat_id", 1), ("status", 1)])
        await self.teams.create_index([("chat_id", 1), ("name_key", 1)], unique=True)
        await self.teams.create_index([("chat_id", 1), ("captain", 1)])
        await self.chats.create_index("chat_id", unique=True)
        await self.live_matches.create_index("chat_id", unique=True)
        await self.leagues.create_index([("chat_id", 1), ("status", 1)])
        await self.leagues.create_index([("chat_id", 1), ("name_key", 1)], unique=True)
