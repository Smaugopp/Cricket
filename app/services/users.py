from app.utils import now

class UserService:
    def __init__(self, db):
        self.c = db.users

    async def ensure(self, user):
        await self.c.update_one({"_id":user.id},
            {"$set":{"name":user.full_name,"username":user.username,"updated_at":now()},
             "$setOnInsert":{"matches":0,"wins":0,"losses":0,"ties":0,"runs":0,"wickets":0,
             "balls":0,"fours":0,"sixes":0,"dots":0,"xp":0,"rating":1000,"streak":0,
             "best_streak":0,"achievements":[],"last_daily":None,"coins":0}},upsert=True)

    async def get(self, uid): return await self.c.find_one({"_id":uid})

    async def record_match(self, uid, won=False, lost=False, tied=False, runs=0, wickets=0,
                           balls=0, fours=0, sixes=0, dots=0):
        if uid in (None,-1): return
        inc={"matches":1,"runs":runs,"wickets":wickets,"balls":balls,"fours":fours,"sixes":sixes,"dots":dots}
        if won: inc.update(wins=1,rating=25,xp=30,coins=50,streak=1)
        elif lost: inc.update(losses=1,rating=-15,xp=15,coins=15,streak=0)
        elif tied: inc.update(ties=1,rating=5,xp=20,coins=25)
        await self.c.update_one({"_id":uid},{"$inc":inc})
        d=await self.get(uid)
        if d and d.get("streak",0)>d.get("best_streak",0):
            await self.c.update_one({"_id":uid},{"$set":{"best_streak":d["streak"]}})
        await self.refresh_achievements(uid)

    async def refresh_achievements(self, uid):
        d=await self.get(uid)
        if not d: return
        earned=set(d.get("achievements",[]))
        candidates=[]
        if d.get("wins",0)>=1: candidates.append("first_win")
        if d.get("wins",0)>=10: candidates.append("ten_wins")
        if d.get("runs",0)>=100: candidates.append("century")
        if d.get("sixes",0)>=10: candidates.append("six_machine")
        if d.get("wickets",0)>=3: candidates.append("hat_trick")
        new=[x for x in candidates if x not in earned]
        if new:
            await self.c.update_one({"_id":uid},
                {"$addToSet":{"achievements":{"$each":new}},
                 "$inc":{"xp":50*len(new),"coins":100*len(new)}})

    async def daily(self, uid):
        d=await self.get(uid); today=now().date().isoformat()
        if d and d.get("last_daily")==today: return False,0
        reward=100
        await self.c.update_one({"_id":uid},{"$set":{"last_daily":today},"$inc":{"coins":reward,"xp":20}})
        return True,reward

    async def leaderboard(self, field, limit=10):
        return await self.c.find({},{"name":1,field:1}).sort(field,-1).limit(limit).to_list(length=limit)
