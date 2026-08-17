import asyncio
from app.services.leagues import LeagueService

def test_round_robin_even():
    svc=LeagueService(None)
    rounds=svc.make_round_robin(["a","b","c","d"])
    assert len(rounds)==6
    assert all(len(r)==2 for r in rounds)
