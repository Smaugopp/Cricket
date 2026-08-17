class AdminService:
    def __init__(self, db, owner_id):
        self.c=db.sudo; self.settings=db.settings; self.chats=db.chats; self.owner_id=owner_id

    async def is_sudo(self, uid):
        return uid==self.owner_id or await self.c.find_one({"_id":uid}) is not None

    async def add_sudo(self, uid):
        if uid==self.owner_id: return False
        r=await self.c.update_one({"_id":uid},{"$set":{"created_by":self.owner_id}},upsert=True)
        return r.upserted_id is not None

    async def remove_sudo(self, uid):
        r=await self.c.delete_one({"_id":uid}); return r.deleted_count>0

    async def list_sudo(self):
        return await self.c.find({},{"_id":1}).to_list(length=500)

    async def register_chat(self, chat_id, chat_type, title=None):
        await self.chats.update_one({"chat_id":chat_id},
            {"$set":{"chat_type":chat_type,"title":title}},upsert=True)

    async def chat_ids(self):
        rows=await self.chats.find({},{"chat_id":1}).to_list(length=100000)
        return [r["chat_id"] for r in rows]

    async def set_maintenance(self, value):
        await self.settings.update_one({"_id":"global"},{"$set":{"maintenance":value}},upsert=True)

    async def maintenance(self):
        d=await self.settings.find_one({"_id":"global"}) or {}
        return bool(d.get("maintenance",False))
