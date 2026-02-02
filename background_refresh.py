import argparse
import time

from db import init_db
from tmdb import TMDb
from store import (
    upsert_movie_from_tmdb_payload,
    hydrate_movie_details,
    hydrate_directors,
    directors_hydrated,
    is_women_directed,
    prefetch_poster,
)


def main():
    parser = argparse.ArgumentParser(
        description="Hydrate women-directed movies into the local cache."
    )
    parser.add_argument("--pages", type=int, default=10, help="Number of popular pages to scan")
    parser.add_argument("--sleep", type=float, default=0.25, help="Sleep between TMDb API calls (seconds)")
    parser.add_argument("--poster-sleep", type=float, default=0.1, help="Sleep after poster downloads (seconds)")
    parser.add_argument("--poster-sizes", default="w342", help="Comma list of poster sizes to cache")
    parser.add_argument("--region", default=None, help="TMDb region override")
    parser.add_argument("--language", default=None, help="TMDb language override")
    args = parser.parse_args()

    init_db()
    tmdb = TMDb(
        region=args.region or "US",
        language=args.language or "en-US",
    )

    sizes = [s.strip() for s in args.poster_sizes.split(",") if s.strip()]

    women_count = 0
    scanned = 0

    for page in range(1, args.pages + 1):
        payload = tmdb.popular_movies(page=page)
        results = payload.get("results") or []
        if not results:
            break

        for m in results:
            mid = m.get("id")
            if not mid:
                continue

            scanned += 1
            upsert_movie_from_tmdb_payload(m)

            if not directors_hydrated(int(mid)):
                hydrate_directors(tmdb, int(mid))
                time.sleep(args.sleep)

            if is_women_directed(int(mid)):
                hydrate_movie_details(tmdb, int(mid))
                time.sleep(args.sleep)
                for size in sizes:
                    downloaded = prefetch_poster(tmdb, int(mid), size=size)
                    if downloaded:
                        time.sleep(args.poster_sleep)
                women_count += 1

        time.sleep(args.sleep)

    print(f"Scanned {scanned} movies. Hydrated {women_count} women-directed movies.")


if __name__ == "__main__":
    main()
