import os
import sys

from rag_service import recommend_with_rag, search_restaurants


def main():
    guild_id = sys.argv[1]
    query = " ".join(sys.argv[2:]) or "교정 중이라 부드러운 음식 먹고 싶어"

    matches = search_restaurants(query, guild_id, match_count=3)
    print(f"matches={len(matches)}")
    for match in matches:
        print(f"- {match.name} / {match.area} / {match.similarity}")

    answer, matched, cached = recommend_with_rag(query, guild_id, match_count=3)
    print(f"cached={cached}")
    print(answer[:1000])


if __name__ == "__main__":
    main()
