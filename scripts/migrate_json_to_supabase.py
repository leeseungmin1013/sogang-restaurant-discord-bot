import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from rag_service import rag_is_configured, upsert_restaurant


def main():
    guild_id = os.environ.get("MIGRATION_GUILD_ID")
    if not guild_id:
        raise SystemExit("Set MIGRATION_GUILD_ID to the Discord server ID before running.")
    if not rag_is_configured():
        raise SystemExit("Set SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, and GEMINI_API_KEY first.")

    data_file = Path(__file__).resolve().parents[1] / "restaurants.json"
    restaurants = json.loads(data_file.read_text(encoding="utf-8"))

    for restaurant in restaurants:
        result = upsert_restaurant(restaurant, guild_id)
        print(f"upserted {restaurant.get('id')}: {result[0].get('id') if result else 'ok'}")


if __name__ == "__main__":
    main()
