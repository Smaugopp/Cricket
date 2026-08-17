from app.services.teams import TeamService

def test_team_name_key():
    assert TeamService.key("  Royal   Challengers ") == "royal challengers"
