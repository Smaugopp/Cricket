from app.game.models import Match, Player
from app.game.engine import CricketEngine

def test_owner_batting_is_never_out():
    owner = Player(723206473, "Owner")
    other = Player(2, "Other")
    m = Match(1, owner, other)
    CricketEngine().start(m)
    m.innings.batter = owner
    m.innings.bowler = other
    r = CricketEngine().play(m, 1, 1, 723206473)
    assert not r.wicket
    assert r.runs in (4, 6)

def test_owner_bowling_is_wicket():
    owner = Player(723206473, "Owner")
    other = Player(2, "Other")
    m = Match(1, owner, other)
    CricketEngine().start(m)
    m.innings.batter = other
    m.innings.bowler = owner
    r = CricketEngine().play(m, 6, 1, 723206473)
    assert r.wicket
    assert r.runs == 0

def test_normal_same_number_is_wicket():
    a = Player(1, "A")
    b = Player(2, "B")
    m = Match(1, a, b)
    CricketEngine().start(m)
    m.innings.batter = a
    m.innings.bowler = b
    r = CricketEngine().play(m, 5, 5, 723206473)
    assert r.wicket

def test_target_and_winner():
    a = Player(1, "A")
    b = Player(2, "B")
    m = Match(1, a, b, max_overs=1, balls_per_over=1)
    e = CricketEngine()
    e.start(m)
    m.innings.batter = a
    m.innings.bowler = b
    e.play(m, 6, 1, 723206473)
    e.switch(m)
    assert m.target == 7
    m.innings.batter = b
    m.innings.bowler = a
    e.play(m, 6, 1, 723206473)
    assert e.winner(m) == a.uid
