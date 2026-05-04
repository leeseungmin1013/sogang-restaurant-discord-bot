import json
import os
import urllib.request


def main():
    token = os.environ["DISCORD_TOKEN"]
    req = urllib.request.Request(
        "https://discord.com/api/v10/users/@me/guilds",
        headers={"Authorization": f"Bot {token}"},
    )
    with urllib.request.urlopen(req, timeout=20) as response:
        guilds = json.loads(response.read().decode("utf-8"))

    for guild in guilds:
        print(f"{guild['id']}\t{guild['name']}")


if __name__ == "__main__":
    main()
