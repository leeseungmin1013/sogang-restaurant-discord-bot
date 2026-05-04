import os

for key in ["DATABASE_URL", "SUPABASE_DB_URL", "SUPABASE_DB_PASSWORD", "POSTGRES_PASSWORD"]:
    print(f"{key}={'set' if os.environ.get(key) else 'missing'}")
