from pathlib import Path
from db import connect
from tmdb import now_iso

CACHE_DIR = Path("cache/posters")
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def prefetch_poster(tmdb, tmdb_id: int, size: str = "w342") -> bool:
    """Download and cache a poster if not already cached. Returns True if downloaded."""
    with connect() as conn:
        row = conn.execute("SELECT poster_path FROM movies WHERE tmdb_id=?", (tmdb_id,)).fetchone()
    if not row or not row["poster_path"]:
        return False

    poster_path = row["poster_path"]
    cache_path = CACHE_DIR / f"{tmdb_id}_{size}.jpg"

    if cache_path.exists():
        return False

    try:
        import requests
        url = tmdb.poster_url(poster_path, size=size)
        r = requests.get(url, stream=True, timeout=20)
        r.raise_for_status()
        with open(cache_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 64):
                if chunk:
                    f.write(chunk)
        return True
    except Exception:
        return False


def upsert_movie_from_tmdb_payload(m: dict):
    year = None
    rd = m.get("release_date") or ""
    if len(rd) >= 4 and rd[:4].isdigit():
        year = int(rd[:4])

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO movies (tmdb_id,title,year,runtime,overview,poster_path,backdrop_path,vote_avg,vote_count,popularity,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(tmdb_id) DO UPDATE SET
              title=excluded.title,
              year=excluded.year,
              overview=excluded.overview,
              poster_path=excluded.poster_path,
              backdrop_path=excluded.backdrop_path,
              vote_avg=excluded.vote_avg,
              vote_count=excluded.vote_count,
              popularity=excluded.popularity,
              updated_at=excluded.updated_at
            """,
            (
                m["id"],
                m.get("title") or m.get("name") or "",
                year,
                None,
                m.get("overview"),
                m.get("poster_path"),
                m.get("backdrop_path"),
                m.get("vote_average"),
                m.get("vote_count"),
                m.get("popularity"),
                now_iso(),
            ),
        )


def upsert_movie_details(details: dict):
    year = None
    rd = details.get("release_date") or ""
    if len(rd) >= 4 and rd[:4].isdigit():
        year = int(rd[:4])

    with connect() as conn:
        conn.execute(
            """
            INSERT INTO movies (tmdb_id,title,year,runtime,overview,poster_path,backdrop_path,vote_avg,vote_count,popularity,updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(tmdb_id) DO UPDATE SET
              title=excluded.title,
              year=excluded.year,
              runtime=excluded.runtime,
              overview=excluded.overview,
              poster_path=excluded.poster_path,
              backdrop_path=excluded.backdrop_path,
              vote_avg=excluded.vote_avg,
              vote_count=excluded.vote_count,
              popularity=excluded.popularity,
              updated_at=excluded.updated_at
            """,
            (
                details["id"],
                details.get("title") or "",
                year,
                details.get("runtime"),
                details.get("overview"),
                details.get("poster_path"),
                details.get("backdrop_path"),
                details.get("vote_average"),
                details.get("vote_count"),
                details.get("popularity"),
                now_iso(),
            ),
        )


def hydrate_movie_details(tmdb, tmdb_id: int):
    details = tmdb.movie_details(tmdb_id)
    upsert_movie_details(details)


def hydrate_directors(tmdb, tmdb_id: int):
    credits = tmdb.movie_credits(tmdb_id)
    crew = credits.get("crew") or []
    directors = [c for c in crew if c.get("job") == "Director" and c.get("id")]

    with connect() as conn:
        for d in directors:
            conn.execute(
                """
                INSERT INTO people (tmdb_person_id,name,gender,updated_at)
                VALUES (?,?,?,?)
                ON CONFLICT(tmdb_person_id) DO UPDATE SET
                  name=excluded.name,
                  gender=excluded.gender,
                  updated_at=excluded.updated_at
                """,
                (d["id"], d.get("name") or "", int(d.get("gender") or 0), now_iso()),
            )
            conn.execute(
                """
                INSERT OR IGNORE INTO credits_director (tmdb_id, tmdb_person_id)
                VALUES (?,?)
                """,
                (tmdb_id, d["id"]),
            )


def directors_hydrated(tmdb_id: int) -> bool:
    with connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM credits_director WHERE tmdb_id=? LIMIT 1",
            (tmdb_id,),
        ).fetchone()
    return row is not None


def is_women_directed(tmdb_id: int) -> bool:
    with connect() as conn:
        row = conn.execute(
            """
            SELECT 1
            FROM credits_director cd
            JOIN people p ON p.tmdb_person_id = cd.tmdb_person_id
            WHERE cd.tmdb_id = ?
              AND p.gender = 1
            LIMIT 1
            """,
            (tmdb_id,),
        ).fetchone()
    return row is not None


def fetch_movies_for_ids(ids: list[int]):
    if not ids:
        return []
    placeholders = ",".join(["?"] * len(ids))
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM movies WHERE tmdb_id IN ({placeholders})",
            ids,
        ).fetchall()

    by_id = {r["tmdb_id"]: r for r in rows}
    out = []
    for i in ids:
        r = by_id.get(i)
        if r:
            out.append(r)
    return out
