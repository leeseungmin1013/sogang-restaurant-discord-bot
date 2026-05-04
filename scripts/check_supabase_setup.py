import json
import os
import urllib.error
import urllib.request


def request_json(url, headers):
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            body = response.read().decode("utf-8")
            return response.status, json.loads(body) if body else None
    except urllib.error.HTTPError as error:
        body = error.read().decode("utf-8", errors="replace")
        return error.code, body


def main():
    url = os.environ["SUPABASE_URL"].rstrip("/")
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }

    status, body = request_json(f"{url}/rest/v1/restaurants?select=id&limit=1", headers)
    print(f"restaurants_table_status={status}")
    if status >= 400:
        print(f"restaurants_table_error={str(body)[:300]}")

    status, body = request_json(f"{url}/rest/v1/recommendation_logs?select=id&limit=1", headers)
    print(f"recommendation_logs_table_status={status}")
    if status >= 400:
        print(f"recommendation_logs_table_error={str(body)[:300]}")


if __name__ == "__main__":
    main()
