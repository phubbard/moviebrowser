import argparse
import gzip
import json
import time
from datetime import date, timedelta

import requests
from dotenv import load_dotenv

from db import connect, init_db
from tmdb import TMDb
from store import (
    hydrate_directors,
    hydrate_movie_details,
    is_women_directed,
    prefetch_poster,
)
from tmdb import now_iso


EXPORT_BASE = "https://files.tmdb.org/p/exports"

load_dotenv()


class RateLimiter:
    def __init__(self, rate_per_sec: float):
        self.min_interval = 1.0 / rate_per_sec if rate_per_sec > 0 else 0.0
        self.next_time = 0.0

    def wait(self):
        if self.min_interval <= 0:
            return
        now = time.monotonic()
        if now < self.next_time:
            time.sleep(self.next_time - now)
        self.next_time = max(now, self.next_time) + self.min_interval


def get_state(key: str) -> str | None:
    with connect() as conn:
        row = conn.execute("SELECT value FROM ingest_state WHERE key=?", (key,)).fetchone()
    return row["value"] if row else None


def set_state(key: str, value: str) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO ingest_state (key,value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
            (key, value),
        )


def enqueue_ids(ids: list[int]) -> int:
    if not ids:
        return 0

    to_add = []
    chunk = 500
    for i in range(0, len(ids), chunk):
        batch = ids[i : i + chunk]
        placeholders = ",".join(["?"] * len(batch))
        with connect() as conn:
            existing_credits = conn.execute(
                f"SELECT DISTINCT tmdb_id FROM credits_director WHERE tmdb_id IN ({placeholders})",
                batch,
            ).fetchall()
            existing_queue = conn.execute(
                f"SELECT tmdb_id FROM ingest_queue WHERE tmdb_id IN ({placeholders})",
                batch,
            ).fetchall()

        existing = {r["tmdb_id"] for r in existing_credits} | {r["tmdb_id"] for r in existing_queue}
        for mid in batch:
            if mid not in existing:
                to_add.append(mid)

    if not to_add:
        return 0

    with connect() as conn:
        conn.executemany(
            "INSERT OR IGNORE INTO ingest_queue (tmdb_id,status,added_at) VALUES (?,?,?)",
            [(mid, "pending", now_iso()) for mid in to_add],
        )
    return len(to_add)


def latest_export(days_back: int = 7) -> tuple[str, requests.Response]:
    for i in range(days_back):
        d = date.today() - timedelta(days=i)
        fname = f"movie_ids_{d.strftime('%m_%d_%Y')}.json.gz"
        url = f"{EXPORT_BASE}/{fname}"
        r = requests.get(url, stream=True, timeout=30)
        if r.status_code == 200:
            return d.isoformat(), r
        r.close()
    raise RuntimeError("No export file found in the last 7 days.")


def ingest_export(days_back: int = 7, batch_size: int = 1000) -> int:
    export_date, resp = latest_export(days_back=days_back)
    added = 0
    total = 0

    with gzip.GzipFile(fileobj=resp.raw) as gz:
        batch = []
        for line in gz:
            obj = json.loads(line.decode("utf-8"))
            mid = obj.get("id")
            if not mid:
                continue
            total += 1
            batch.append(int(mid))
            if len(batch) >= batch_size:
                added += enqueue_ids(batch)
                batch = []
        if batch:
            added += enqueue_ids(batch)

    set_state("last_export_date", export_date)
    resp.close()
    print(f"Export {export_date}: scanned {total}, queued {added}.")
    return added


def ingest_changes(tmdb: TMDb, start_date: str, end_date: str, rate: RateLimiter) -> int:
    page = 1
    added = 0

    while True:
        rate.wait()
        payload = tmdb.movie_changes(start_date=start_date, end_date=end_date, page=page)
        results = payload.get("results") or []
        if not results:
            break

        ids = [int(r["id"]) for r in results if r.get("id")]
        added += enqueue_ids(ids)

        total_pages = int(payload.get("total_pages") or page)
        if page >= total_pages:
            break
        page += 1

    set_state("last_changes_date", end_date)
    print(f"Changes {start_date}→{end_date}: queued {added}.")
    return added


def next_queue_item(include_failed: bool, max_attempts: int) -> int | None:
    statuses = ["pending"]
    if include_failed:
        statuses.append("failed")

    placeholders = ",".join(["?"] * len(statuses))
    with connect() as conn:
        row = conn.execute(
            f"""
            SELECT tmdb_id
            FROM ingest_queue
            WHERE status IN ({placeholders})
              AND attempts < ?
            ORDER BY added_at
            LIMIT 1
            """,
            statuses + [max_attempts],
        ).fetchone()
    return int(row["tmdb_id"]) if row else None


def update_queue(tmdb_id: int, status: str, attempts: int | None = None, error: str | None = None):
    with connect() as conn:
        if attempts is None:
            conn.execute(
                "UPDATE ingest_queue SET status=?, last_attempt=? WHERE tmdb_id=?",
                (status, now_iso(), tmdb_id),
            )
        else:
            conn.execute(
                "UPDATE ingest_queue SET status=?, attempts=?, last_attempt=?, last_error=? WHERE tmdb_id=?",
                (status, attempts, now_iso(), error, tmdb_id),
            )


def worker(
    tmdb: TMDb,
    rate: RateLimiter,
    poster_sizes: list[str],
    poster_sleep: float,
    max_items: int,
    include_failed: bool,
    max_attempts: int,
):
    processed = 0

    while True:
        if max_items > 0 and processed >= max_items:
            break

        tmdb_id = next_queue_item(include_failed=include_failed, max_attempts=max_attempts)
        if tmdb_id is None:
            break

        update_queue(tmdb_id, "in_progress")
        try:
            rate.wait()
            hydrate_directors(tmdb, tmdb_id)

            if is_women_directed(tmdb_id):
                rate.wait()
                hydrate_movie_details(tmdb, tmdb_id)
                for size in poster_sizes:
                    rate.wait()
                    downloaded = prefetch_poster(tmdb, tmdb_id, size=size)
                    if downloaded and poster_sleep > 0:
                        time.sleep(poster_sleep)

            update_queue(tmdb_id, "done")
        except Exception as e:
            with connect() as conn:
                row = conn.execute(
                    "SELECT attempts FROM ingest_queue WHERE tmdb_id=?",
                    (tmdb_id,),
                ).fetchone()
            attempts = int(row["attempts"] or 0) + 1 if row else 1
            update_queue(tmdb_id, "failed", attempts=attempts, error=str(e)[:500])

        processed += 1

    print(f"Worker processed {processed} items.")


def run_weekly(tmdb: TMDb, rate: RateLimiter, poster_sizes: list[str], poster_sleep: float):
    today = date.today()
    start_date = (today - timedelta(days=7)).isoformat()
    end_date = today.isoformat()

    ingest_export(days_back=7)
    ingest_changes(tmdb, start_date=start_date, end_date=end_date, rate=rate)
    worker(
        tmdb,
        rate=rate,
        poster_sizes=poster_sizes,
        poster_sleep=poster_sleep,
        max_items=0,
        include_failed=True,
        max_attempts=5,
    )


def main():
    parser = argparse.ArgumentParser(description="TMDb ingestion pipeline.")
    parser.add_argument("--mode", choices=["export", "changes", "worker", "weekly"], default="weekly")
    parser.add_argument("--rate", type=float, default=20.0, help="Max requests per second")
    parser.add_argument("--poster-sizes", default="w342", help="Comma list of poster sizes to cache")
    parser.add_argument("--poster-sleep", type=float, default=0.05, help="Sleep after poster downloads (seconds)")
    parser.add_argument("--start-date", default=None, help="Changes start date (YYYY-MM-DD)")
    parser.add_argument("--end-date", default=None, help="Changes end date (YYYY-MM-DD)")
    parser.add_argument("--max-items", type=int, default=0, help="Max items to process in worker (0 = no limit)")
    parser.add_argument("--include-failed", action="store_true", help="Retry failed queue items")
    parser.add_argument("--max-attempts", type=int, default=5, help="Max attempts for failed items")
    parser.add_argument("--region", default=None, help="TMDb region override")
    parser.add_argument("--language", default=None, help="TMDb language override")
    args = parser.parse_args()

    init_db()
    tmdb = TMDb(
        region=args.region or "US",
        language=args.language or "en-US",
    )
    rate = RateLimiter(args.rate)
    sizes = [s.strip() for s in args.poster_sizes.split(",") if s.strip()]

    if args.mode == "export":
        ingest_export(days_back=7)
        return

    if args.mode == "changes":
        if not args.start_date or not args.end_date:
            today = date.today()
            args.end_date = today.isoformat()
            args.start_date = (today - timedelta(days=7)).isoformat()
        ingest_changes(tmdb, start_date=args.start_date, end_date=args.end_date, rate=rate)
        return

    if args.mode == "worker":
        worker(
            tmdb,
            rate=rate,
            poster_sizes=sizes,
            poster_sleep=args.poster_sleep,
            max_items=args.max_items,
            include_failed=args.include_failed,
            max_attempts=args.max_attempts,
        )
        return

    run_weekly(tmdb, rate=rate, poster_sizes=sizes, poster_sleep=args.poster_sleep)


if __name__ == "__main__":
    main()
