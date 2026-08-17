import sys
sys.path.insert(0, ".")

from app.game.engine import CricketEngine, BOWLING_TYPES
from app.game.models import Match, Player

engine = CricketEngine()
m = Match(1, Player(10, "Batter"), Player(20, "Bowler"), max_overs=1, balls_per_over=3)
engine.start(m)
m.innings.batter = m.creator
m.innings.bowler = m.opponent

r = engine.play(m, 4, 2, owner_id=999)
assert r.ball_type == "Yorker"
assert r.runs == 4 and not r.wicket
assert m.innings.balls == 1
assert m.innings.over(3) == "0.1"

r2 = engine.play(m, 2, 2, owner_id=999)
assert r2.wicket and r2.runs == 0
assert m.innings.balls == 2

engine.play(m, 6, 1, owner_id=999)
assert m.innings.over(3) == "1.0"

assert set(BOWLING_TYPES) == {1,2,3,4,5,6}
print("ENGINE SMOKE: PASS")
