#!/usr/bin/env bash
set -euo pipefail

APP_USER="seungminlee1013"
APP_GROUP="seungminlee1013"
APP_DIR="/home/${APP_USER}/discord-sogang-bot"
SERVICE_NAME="discord-sogang-bot.service"

install -d -o "${APP_USER}" -g "${APP_GROUP}" -m 700 "${APP_DIR}"

if [[ -f "/home/${APP_USER}/bot.py" ]]; then
  cp -a "/home/${APP_USER}/bot.py" "/home/${APP_USER}/bot.py.backup.$(date +%Y%m%d%H%M%S)"
fi

install -o "${APP_USER}" -g "${APP_GROUP}" -m 644 /tmp/bot.py "${APP_DIR}/bot.py"
install -o "${APP_USER}" -g "${APP_GROUP}" -m 644 /tmp/requirements.txt "${APP_DIR}/requirements.txt"
install -o root -g root -m 644 /tmp/discord-sogang-bot.service "/etc/systemd/system/${SERVICE_NAME}"

if [[ -f /tmp/bot.env ]]; then
  install -o "${APP_USER}" -g "${APP_GROUP}" -m 600 /tmp/bot.env "${APP_DIR}/.env"
fi

if [[ ! -f "${APP_DIR}/restaurants.json" ]]; then
  install -o "${APP_USER}" -g "${APP_GROUP}" -m 644 /tmp/restaurants.json "${APP_DIR}/restaurants.json"
elif [[ -f /tmp/restaurants.json ]]; then
  install -d -o "${APP_USER}" -g "${APP_GROUP}" -m 700 "${APP_DIR}/backups"
  cp -a "${APP_DIR}/restaurants.json" "${APP_DIR}/backups/restaurants-before-deploy-$(date +%Y%m%d%H%M%S).json"
fi

systemctl daemon-reload

if pgrep -u "${APP_USER}" -f "python3 bot.py" >/dev/null; then
  pkill -u "${APP_USER}" -f "python3 bot.py"
fi

systemctl enable "${SERVICE_NAME}"
systemctl restart "${SERVICE_NAME}"
sleep 3
systemctl --no-pager --full status "${SERVICE_NAME}"
