import json
import os
import urllib.request


def main():
    token = os.environ["DISCORD_TOKEN"]
    channel_id = os.environ.get("ADMIN_CHANNEL_ID")
    if not channel_id:
        raise SystemExit("ADMIN_CHANNEL_ID is not set.")

    req = urllib.request.Request(
        f"https://discord.com/api/v10/channels/{channel_id}",
        headers={"Authorization": f"Bot {token}"},
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        channel = json.loads(response.read().decode("utf-8"))

    print(channel["guild_id"])


if __name__ == "__main__":
    main()
