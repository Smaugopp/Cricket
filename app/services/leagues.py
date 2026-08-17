from datetime import datetime, timezone
import random

def utcnow():
    return datetime.now(timezone.utc)

class LeagueService:
    def __init__(self, db):
        self.c=db.leagues

    @staticmethod
    def key(name): return " ".join(name.strip().lower().split())

    async def create(self, chat_id, name, owner):
        name=" ".join(name.strip().split())
        if not name or len(name)>32: return None, "League name must be 1–32 characters."
        doc={"chat_id":chat_id,"name":name,"name_key":self.key(name),"owner":owner,
             "status":"open","teams":[],"fixtures":[],"table":{},"round":0,
             "created_at":utcnow(),"updated_at":utcnow()}
        try:
            r=await self.c.insert_one(doc)
        except Exception:
            return None, "A league with this name already exists in this group."
        doc["_id"]=r.inserted_id
        return doc,None

    async def get(self, chat_id, name):
        return await self.c.find_one({"chat_id":chat_id,"name_key":self.key(name)})

    async def add_team(self, league, team_id, team_name):
        if league["status"]!="open": return False,"League is already running."
        if team_id in league.get("teams",[]): return False,"Team is already registered."
        if len(league.get("teams",[]))>=16: return False,"League limit is 16 teams."
        await self.c.update_one({"_id":league["_id"]},
            {"$push":"__bad__"} if False else
            {"$addToSet":{"teams":team_id},
             "$set":{f"team_names.{team_id}":team_name,"updated_at":utcnow()}})
        return True,"Team registered."

    def make_round_robin(self, team_ids):
        ids=list(team_ids)
        if len(ids)<2: return []
        if len(ids)%2: ids.append(None)
        n=len(ids); rounds=[]
        arr=ids[:]
        for rnd in range(n-1):
            fixtures=[]
            for i in range(n//2):
                a,b=arr[i],arr[n-1-i]
                if a is not None and b is not None:
                    fixtures.append({"home":a,"away":b,"played":False,"winner":None,"runs":{"home":0,"away":0}})
            rounds.append(fixtures)
            arr=[arr[0]]+[arr[-1]]+arr[1:-1]
        # second leg reversed
        second=[]
        for r in rounds:
            second.append([{"home":x["away"],"away":x["home"],"played":False,"winner":None,"runs":{"home":0,"away":0}} for x in r])
        return rounds+second

    async def start(self, league):
        teams=league.get("teams",[])
        if len(teams)<2: return False,"Need at least 2 teams."
        fixtures=self.make_round_robin(teams)
        table={str(t):{"played":0,"won":0,"lost":0,"tied":0,"points":0,"runs_for":0,"runs_against":0} for t in teams}
        await self.c.update_one({"_id":league["_id"]},
            {"$set":{"status":"running","fixtures":fixtures,"table":table,"round":1,"updated_at":utcnow()}})
        return True,f"League started with {len(teams)} teams."

    async def record_fixture(self, league, index, winner):
        fixtures=league.get("fixtures",[])
        if index<0 or index>=len(fixtures): return False,"Invalid fixture."
        f=fixtures[index]
        if f.get("played"): return False,"Fixture already played."
        if winner not in {f["home"],f["away"],0}: return False,"Invalid winner."
        f["played"]=True; f["winner"]=winner
        table=league.get("table",{})
        for t in (f["home"],f["away"]):
            row=table[str(t)]; row["played"]+=1
        if winner==0:
            table[str(f["home"])]["tied"]+=1; table[str(f["away"])]["tied"]+=1
            table[str(f["home"])]["points"]+=1; table[str(f["away"])]["points"]+=1
        else:
            table[str(winner)]["won"]+=1; table[str(winner)]["points"]+=2
            loser=f["away"] if winner==f["home"] else f["home"]
            table[str(loser)]["lost"]+=1
        await self.c.update_one({"_id":league["_id"]},{"$set":{"fixtures":fixtures,"table":table,"updated_at":utcnow()}})
        return True,"Fixture recorded."

    async def table(self, league):
        names=league.get("team_names",{})
        rows=[]
        for tid,row in league.get("table",{}).items():
            x=dict(row); x["team"]=names.get(tid,tid); x["id"]=tid; rows.append(x)
        return sorted(rows,key=lambda x:(-x["points"],-x["won"],x["lost"],x["team"]))
