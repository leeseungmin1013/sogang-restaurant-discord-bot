import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass


SUPABASE_URL_ENV = "SUPABASE_URL"
SUPABASE_SERVICE_ROLE_KEY_ENV = "SUPABASE_SERVICE_ROLE_KEY"
GEMINI_API_KEY_ENV = "GEMINI_API_KEY"
GEMINI_GENERATION_MODEL_ENV = "GEMINI_GENERATION_MODEL"
GEMINI_EMBEDDING_MODEL_ENV = "GEMINI_EMBEDDING_MODEL"
GEMINI_EMBEDDING_DIMENSIONS_ENV = "GEMINI_EMBEDDING_DIMENSIONS"

DEFAULT_GENERATION_MODEL = "gemini-2.5-flash"
DEFAULT_EMBEDDING_MODEL = "gemini-embedding-001"
DEFAULT_EMBEDDING_DIMENSIONS = 768


class RagConfigurationError(RuntimeError):
    pass


@dataclass
class RagRestaurant:
    id: str
    name: str
    area: str
    category: str
    signature_menu: str
    description: str
    image_url: str
    map_provider: str
    map_url: str
    tags: list[str]
    similarity: float | None = None


_cache = {}


def rag_is_configured():
    return bool(
        os.environ.get(SUPABASE_URL_ENV)
        and os.environ.get(SUPABASE_SERVICE_ROLE_KEY_ENV)
        and os.environ.get(GEMINI_API_KEY_ENV)
    )


def _env_int(name, default):
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    return int(raw)


def _json_request(url, method="GET", headers=None, payload=None, timeout=30):
    body = None
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")

    request = urllib.request.Request(url, data=body, method=method)
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    if payload is not None:
        request.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {error.code} from {url}: {detail}") from error


def _supabase_headers(prefer=None):
    key = os.environ.get(SUPABASE_SERVICE_ROLE_KEY_ENV)
    if not key:
        raise RagConfigurationError("SUPABASE_SERVICE_ROLE_KEY is not set.")

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }
    if prefer:
        headers["Prefer"] = prefer
    return headers


def _supabase_url(path):
    base_url = os.environ.get(SUPABASE_URL_ENV, "").rstrip("/")
    if not base_url:
        raise RagConfigurationError("SUPABASE_URL is not set.")
    return f"{base_url}{path}"


def build_embedding_text(restaurant):
    map_info = restaurant.get("map") or {}
    tags = restaurant.get("tags") or []
    if isinstance(tags, str):
        tags = [item.strip() for item in tags.split(",") if item.strip()]

    parts = [
        f"이름: {restaurant.get('name', '')}",
        f"위치: {restaurant.get('area', '')}",
        f"분류: {restaurant.get('category', '')}",
        f"대표메뉴: {restaurant.get('signature_menu', '')}",
        f"설명: {restaurant.get('description', '')}",
        f"지도: {map_info.get('provider', '')} {map_info.get('url', '')}",
        f"태그: {', '.join(tags)}",
    ]
    return "\n".join(part for part in parts if part.split(":", 1)[-1].strip())


def embed_text(text):
    api_key = os.environ.get(GEMINI_API_KEY_ENV)
    if not api_key:
        raise RagConfigurationError("GEMINI_API_KEY is not set.")

    model = os.environ.get(GEMINI_EMBEDDING_MODEL_ENV, DEFAULT_EMBEDDING_MODEL)
    dimensions = _env_int(GEMINI_EMBEDDING_DIMENSIONS_ENV, DEFAULT_EMBEDDING_DIMENSIONS)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent?key={api_key}"
    payload = {
        "content": {
            "parts": [{"text": text}],
        },
        "outputDimensionality": dimensions,
    }
    result = _json_request(url, method="POST", payload=payload, timeout=30)
    try:
        return result["embedding"]["values"]
    except (KeyError, TypeError) as error:
        raise RuntimeError(f"Unexpected Gemini embedding response: {result}") from error


def generate_answer(user_query, restaurants):
    api_key = os.environ.get(GEMINI_API_KEY_ENV)
    if not api_key:
        raise RagConfigurationError("GEMINI_API_KEY is not set.")

    model = os.environ.get(GEMINI_GENERATION_MODEL_ENV, DEFAULT_GENERATION_MODEL)
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
    context = "\n\n".join(format_restaurant_context(item) for item in restaurants)
    prompt = f"""
너는 서강대 주변 맛집을 잘 아는 친절한 Discord 미식 가이드다.
아래 제공된 식당 후보만 사용해서 답하라.
후보에 없는 식당은 절대 만들지 마라.
지도 링크와 이미지 정보는 제공된 값만 사용하라.
의학, 알레르기, 건강 관련 상황은 단정하지 말고 조심스럽게 표현하라.

사용자 상황:
{user_query}

식당 후보:
{context}

답변 형식:
- 가장 잘 맞는 추천 1곳을 먼저 제시
- 대안이 있으면 1~2곳 추가
- 각 식당마다 상황에 맞는 이유를 1~2문장으로 설명
- 지도 링크가 있으면 함께 적기
""".strip()

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [{"text": prompt}],
            }
        ],
        "generationConfig": {
            "temperature": 0.4,
            "maxOutputTokens": 900,
        },
    }
    result = _json_request(url, method="POST", payload=payload, timeout=45)
    try:
        return result["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError, TypeError) as error:
        raise RuntimeError(f"Unexpected Gemini generation response: {result}") from error


def format_restaurant_context(restaurant):
    tags = restaurant.tags if isinstance(restaurant, RagRestaurant) else restaurant.get("tags", [])
    if isinstance(tags, str):
        tags = [tags]

    getter = restaurant.__dict__.get if isinstance(restaurant, RagRestaurant) else restaurant.get
    return "\n".join(
        [
            f"ID: {getter('id', '')}",
            f"이름: {getter('name', '')}",
            f"위치: {getter('area', '')}",
            f"분류: {getter('category', '')}",
            f"대표메뉴: {getter('signature_menu', '')}",
            f"설명: {getter('description', '')}",
            f"태그: {', '.join(tags)}",
            f"지도: {getter('map_provider', '')} {getter('map_url', '')}",
        ]
    )


def _to_rag_restaurant(row):
    return RagRestaurant(
        id=str(row.get("id", "")),
        name=row.get("name") or "",
        area=row.get("area") or "",
        category=row.get("category") or "",
        signature_menu=row.get("signature_menu") or "",
        description=row.get("description") or "",
        image_url=row.get("image_url") or "",
        map_provider=row.get("map_provider") or "",
        map_url=row.get("map_url") or "",
        tags=row.get("tags") or [],
        similarity=row.get("similarity"),
    )


def search_restaurants(user_query, guild_id, match_count=5):
    query_embedding = embed_text(user_query)
    payload = {
        "query_embedding": query_embedding,
        "match_guild_id": int(guild_id),
        "match_count": match_count,
    }
    rows = _json_request(
        _supabase_url("/rest/v1/rpc/match_restaurants"),
        method="POST",
        headers=_supabase_headers(),
        payload=payload,
        timeout=30,
    )
    return [_to_rag_restaurant(row) for row in rows or []]


def recommend_with_rag(user_query, guild_id, match_count=5):
    if not rag_is_configured():
        raise RagConfigurationError("Supabase/Gemini environment variables are not configured.")

    normalized_query = " ".join(user_query.split()).lower()
    cache_key = (str(guild_id), normalized_query)
    cached = _cache.get(cache_key)
    if cached and time.time() - cached["created_at"] < 900:
        return cached["answer"], cached["restaurants"], True

    restaurants = search_restaurants(user_query, guild_id, match_count=match_count)
    if not restaurants:
        return "조건에 맞는 맛집을 찾지 못했어요. 맛집 데이터 설명이나 태그를 더 보강해보면 좋아요.", [], False

    answer = generate_answer(user_query, restaurants)
    _cache[cache_key] = {
        "answer": answer,
        "restaurants": restaurants,
        "created_at": time.time(),
    }
    log_recommendation(guild_id, user_query, answer, [item.id for item in restaurants])
    return answer, restaurants, False


def restaurant_to_supabase_row(restaurant, guild_id):
    map_info = restaurant.get("map") or {}
    tags = restaurant.get("tags") or []
    embedding_text = build_embedding_text(restaurant)
    embedding = embed_text(embedding_text)
    submitted_by = restaurant.get("submitted_by") or {}
    return {
        "legacy_id": restaurant.get("id"),
        "guild_id": int(guild_id),
        "name": restaurant.get("name"),
        "area": restaurant.get("area"),
        "category": restaurant.get("category"),
        "signature_menu": restaurant.get("signature_menu"),
        "description": restaurant.get("description"),
        "image_url": restaurant.get("image_url"),
        "map_provider": map_info.get("provider"),
        "map_url": map_info.get("url"),
        "tags": tags,
        "status": restaurant.get("status", "approved"),
        "submitted_by_user_id": int(submitted_by["user_id"]) if submitted_by.get("user_id") else None,
        "submitted_by_display_name": submitted_by.get("display_name"),
        "embedding_text": embedding_text,
        "embedding": embedding,
    }


def upsert_restaurant(restaurant, guild_id):
    if not rag_is_configured():
        return None

    row = restaurant_to_supabase_row(restaurant, guild_id)
    return _json_request(
        _supabase_url("/rest/v1/restaurants?on_conflict=guild_id,legacy_id"),
        method="POST",
        headers=_supabase_headers(prefer="resolution=merge-duplicates,return=representation"),
        payload=[row],
        timeout=45,
    )


def log_recommendation(guild_id, query, answer, matched_restaurant_ids):
    try:
        _json_request(
            _supabase_url("/rest/v1/recommendation_logs"),
            method="POST",
            headers=_supabase_headers(prefer="return=minimal"),
            payload=[
                {
                    "guild_id": int(guild_id),
                    "query": query,
                    "answer": answer,
                    "matched_restaurant_ids": matched_restaurant_ids,
                }
            ],
            timeout=15,
        )
    except Exception as error:
        print(f"추천 로그 저장 실패: {error!r}")
