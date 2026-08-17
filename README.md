# 🏏 Cricket Arena — Production Telegram Cricket Bot

Telegram-native cricket bot for private chats, groups and supergroups. No web/Mini-App gameplay.

## Included

- Multiplayer group matches
- Solo AI matches
- Custom 1/2/5/10/20-over formats
- 3-ball and 6-ball modes
- Ball-by-ball gameplay
- Wickets, 4s, 6s, targets and innings
- Persistent MongoDB Atlas data
- Live-match recovery after container restart
- Teams / squads / captain / vice-captain
- Playing XI of 11
- Player roles
- Group-scoped team membership
- Round-robin leagues with home/away fixtures
- Knockout tournaments with persistent brackets
- Player profile, rating, XP, coins, stats and history
- Daily rewards and achievements
- Leaderboards
- Owner and sudo system
- Maintenance mode
- Broadcast to registered chats
- Telegram command menu
- Global error reporting to owner
- Automatic stale-match cleanup
- MongoDB Atlas backup/restore scripts
- Docker + Docker Compose
- GitHub CI

## Fixed configuration

```env
OWNER_ID=723206473
SUPPORT_GROUP=@arcchatz
UPDATES_CHANNEL=@arcupdates
```

## Requirements

- Ubuntu/Debian VPS
- Docker + Docker Compose plugin
- Telegram bot token
- MongoDB Atlas URI

The app uses PyMongo's native async client, which is officially supported in current PyMongo; AsyncMongoClient became generally available in PyMongo 4.13. MongoDB's official docs recommend this API for asyncio applications. 

## Preflight check

```bash
bash check.sh
```

This checks Python compilation, shell syntax and Docker Compose configuration when Docker is available.

## Fresh VPS deployment

```bash
git clone https://github.com/YOUR_USERNAME/cricket-bot.git /opt/cricket-bot
cd /opt/cricket-bot

cp .env.example .env
nano .env
```

Only set:

```env
BOT_TOKEN=YOUR_BOT_TOKEN
MONGO_URI=mongodb+srv://USERNAME:PASSWORD@YOUR_CLUSTER.mongodb.net/cricket_bot?retryWrites=true&w=majority
```

Then:

```bash
chmod +x *.sh
bash deploy.sh
```

If Docker is not installed:

```bash
sudo bash install.sh
```

`install.sh` installs Docker/Compose when required and then calls the production deploy script.

## Check status

```bash
docker compose ps
docker compose logs --tail=100 bot
```

Live logs:

```bash
docker compose logs -f bot
```

## Update from GitHub

```bash
cd /opt/cricket-bot
bash update.sh
```

## Backup Atlas database

```bash
cd /opt/cricket-bot
bash backup.sh
```

Backups are written to:

```text
backups/
```

Restore:

```bash
bash restore.sh backups/cricket_bot_YYYYMMDD_HHMMSS.archive.gz
```

Restore asks for `RESTORE` before replacing data.

## Group batting + private bowling

This is intentionally Telegram-native:

```text
GROUP
Batter → 1–6
       ↓
BOT → tells bowler to check DM

BOWLER DM
1️⃣ Swing
2️⃣ Yorker
3️⃣ Bouncer
4️⃣ Slower Ball
5️⃣ Inswing
6️⃣ Outswing
       ↓
BOT → posts the delivery type + result in GROUP
```

The bowler's numeric choice is never exposed as a raw number in the group. The over is derived automatically from legal balls, so players never need to type an over number.

## Group setup

Add the bot to the group. For gameplay based on ordinary `1`–`6` messages, BotFather Group Privacy must be disabled for the bot.

The bot keeps matches, teams and leagues separated by Telegram group chat ID.

## Main commands

```text
/start
/commands
/help
/rules
/ping
/id

/play
/join
/solo
/custom 1|2|5|10|20
/score
/status
/cancel

/teams
/team create NAME
/team my
/team roster NAME
/team add USER_ID
/team remove USER_ID
/team captain USER_ID
/team vice USER_ID
/team xi
/team xi set ID1 ID2 ... ID11
/team role USER_ID batter|bowler|all_rounder|keeper

/league help
/league create NAME
/league join NAME TEAM_NAME
/league start NAME
/league fixtures NAME
/league table NAME
/league result NAME FIXTURE_INDEX HOME|AWAY|TIE

/tournament list
/tournament create NAME 2
/tournament join ID
/tournament start ID
/tournament fixtures ID
/tournament result ID MATCH_NUMBER HOME|AWAY

/profile
/stats
/history
/achievements
/daily
/leaderboard

/admin
/sudo
/broadcast TEXT
/maintenance on|off
```

## Owner powers

Owner ID is `723206473`.

Owner batting is protected:
- every valid ball gives 4 or 6
- owner cannot be dismissed

Owner bowling:
- every valid ball dismisses the opponent

Sudo users can be managed by the owner.


### Anti-double-submit protection

Each active match is serialized with an asyncio lock. A player's first accepted
number is consumed for that delivery; repeated/rapid duplicate messages are
ignored because the turn state changes immediately. This prevents double-run
or double-wicket processing from race-condition duplicates.

## Production note

This build is intended for one VPS / one bot process. MongoDB Atlas stores persistent business data and active matches are also persisted so a container restart can recover them.

Do not run multiple bot replicas until a shared distributed lock / Redis match layer is added.

No static review can honestly guarantee zero runtime errors against an external Telegram bot and MongoDB Atlas account. The deployment scripts therefore perform environment validation, Docker Compose validation, image build, startup verification and show the exact container logs when startup fails.
