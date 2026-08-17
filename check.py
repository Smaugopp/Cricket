from pathlib import Path
import ast

required = [
    "app/__main__.py", "app/bot.py", "app/config.py", "app/db.py",
    "app/game/engine.py", "app/game/models.py", "app/game/manager.py",
    "app/handlers/core.py", "app/handlers/game.py", "app/handlers/profile.py",
    "app/handlers/admin.py", "app/handlers/team.py", "app/handlers/tournament.py",
    "app/handlers/league.py", "app/handlers/commands.py", "app/handlers/errors.py",
    "app/services/users.py", "app/services/admin.py", "app/services/teams.py",
    "app/services/tournaments.py", "app/services/leagues.py",
]

for name in required:
    path = Path(name)
    assert path.exists(), f"Missing: {name}"
    ast.parse(path.read_text(encoding="utf-8"))

print("OK: production Python modules exist and parse.")
