from pathlib import Path
import ast

required = [
    "app/__main__.py", "app/bot.py", "app/config.py", "app/db.py",
    "app/game/engine.py", "app/game/models.py", "app/game/manager.py",
    "app/handlers/core.py", "app/handlers/game.py", "app/handlers/profile.py",
    "app/handlers/admin.py", "app/handlers/tournament.py",
    "app/services/users.py", "app/services/admin.py",
]

for name in required:
    path = Path(name)
    if not path.exists():
        raise SystemExit(f"Missing file: {name}")
    ast.parse(path.read_text(encoding="utf-8"))

print("OK - all core Python files exist and parse.")
