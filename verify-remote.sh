#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/home/seungminlee1013/discord-sogang-bot"

cd "${APP_DIR}"
python3 -m json.tool restaurants.json >/dev/null
python3 - <<'PY'
import json
from pathlib import Path

data = json.loads(Path("restaurants.json").read_text(encoding="utf-8"))
approved = [item for item in data if item.get("status") == "approved"]
pending = [item for item in data if item.get("status") == "pending"]

print(f"restaurants={len(data)}")
print(f"approved={len(approved)}")
print(f"pending={len(pending)}")
print(f"first_id={data[0]['id'] if data else 'none'}")
PY
ls -l bot.py restaurants.json
