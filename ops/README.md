# VPS Operations

Recommended VPS: Ubuntu 22.04/24.04, 2 CPU, 2-4 GB RAM, 30+ GB SSD.

The bot uses Telegram long polling, so no domain, Nginx or SSL certificate is required for gameplay.

## First deployment

```bash
sudo apt update
sudo apt install -y ca-certificates curl git
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker "$USER"
newgrp docker

git clone YOUR_REPOSITORY_URL cricket-bot
cd cricket-bot

cp .env.example .env
nano .env

./deploy.sh
docker compose ps
docker compose logs -f bot
```

## Update

```bash
git pull
./deploy.sh
```

## Restart

```bash
docker compose restart bot
```

## Stop

```bash
docker compose down
```

## Backup

```bash
./backup.sh
```

Copy backups off the VPS as well. A backup on the same disk is not a disaster-recovery backup.

## Restore

```bash
./restore.sh backups/cricket_bot_YYYYMMDD_HHMMSS.archive
```

## Logs

```bash
docker compose logs --tail=200 bot
docker compose logs --tail=200 mongo
```

## Health

```bash
docker compose ps
docker inspect --format='{{.State.Status}}' cricket-bot-bot-1
```

## Security

- Never commit `.env`.
- Use a long random Mongo password.
- Keep SSH key authentication enabled.
- Disable root SSH login if your VPS provider permits.
- Allow only SSH (22) inbound unless you deliberately expose another service.
- The Telegram bot does not need port 80/443 when using polling.
- Take regular off-server Mongo backups.

## Telegram

Add the bot to the target group. For group gameplay, disable privacy mode in BotFather if you want the bot to receive ordinary `1`–`6` messages from users.

If you use commands only, privacy mode can remain enabled, but the number-based gameplay requires the bot to receive those messages.
