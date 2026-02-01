import os
import secrets
from pathlib import Path
from flask import Flask, render_template, request, redirect, url_for, session, abort, send_file
from db import init_db, connect
from tmdb import TMDb, now_iso

from dotenv import load_dotenv
load_dotenv()

APP_SECRET = os.getenv("APP_SECRET_KEY") or secrets.token_hex(16)

CACHE_DIR = Path("cache/posters")
CACHE_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_REGION = os.getenv("TMDB_REGION", "US")
DEFAULT_LANGUAGE = os.getenv("TMDB_LANGUAGE", "en-US")

app = Flask(__name__)
app.secret_key = APP_SECRET

tmdb = TMDb(region=DEFAULT_REGION, language=DEFAULT_LANGUAGE)


def basket_ids() -> set[int]:
    raw = session.get("basket", [])
    return set(int(x) for x in raw)

def set_basket(ids: set[int]) -> None:
    session["basket"] = sorted(ids)

def ensure_csrf():
    if "csrf" not in session:
        session["csrf"] = secrets.token_urlsafe(16)

def check_csrf():
    token = request.form.get("csrf", "")
    if not token or token != session.get("csrf"):
        abort(400, "Bad CSRF token")

@app.context_processor
def inject_globals():
    ensure_csrf()

    # Search link configuration
    search_links = []
    link1_label = os.getenv("SEARCH_LINK_1_LABEL")
    link1_url = os.getenv("SEARCH_LINK_1_URL")
    link2_label = os.getenv("SEARCH_LINK_2_LABEL")
    link2_url = os.getenv("SEARCH_LINK_2_URL")

    if link1_label and link1_url:
        search_links.append({"label": link1_label, "url_template": link1_url})
    if link2_label and link2_url:
        search_links.append({"label": link2_label, "url_template": link2_url})

    return {
        "basket_count": len(basket_ids()),
        "csrf_token": session.get("csrf", ""),
        "search_links": search_links,
    }

def prefetch_poster(tmdb_id: int, size: str = "w342"):
    """Download and cache a poster if not already cached."""
    with connect() as conn:
        row = conn.execute("SELECT poster_path FROM movies WHERE tmdb_id=?", (tmdb_id,)).fetchone()
    if not row or not row["poster_path"]:
        return False

    poster_path = row["poster_path"]
    cache_path = CACHE_DIR / f"{tmdb_id}_{size}.jpg"

    if cache_path.exists():
        return True  # Already cached

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
    except Exception as e:
        print(f"Failed to prefetch poster for movie {tmdb_id}: {e}")
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

def hydrate_movie_details_if_needed(tmdb_id: int):
    details = tmdb.movie_details(tmdb_id)
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

def hydrate_directors(tmdb_id: int):
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

def page_url_builder(**base_params):
    def _builder(page: int):
        params = dict(base_params)
        params["page"] = page
        return url_for("browse", **params)
    return _builder


def directors_hydrated(tmdb_id: int) -> bool:
    with connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM credits_director WHERE tmdb_id=? LIMIT 1",
            (tmdb_id,),
        ).fetchone()
    return row is not None
    
    
@app.get("/")
def browse():
    q = (request.args.get("q") or "").strip()
    src = request.args.get("src") or ("search" if q else "popular")
    sort = request.args.get("sort") or "popularity"
    women = request.args.get("women", "1") == "1"  # Default to "1" (women-directed selected)
    year_min = (request.args.get("year_min") or "").strip()
    year_max = (request.args.get("year_max") or "").strip()
    page = int(request.args.get("page") or 1)
    show_plots = request.args.get("plots") == "1"
    loading = request.args.get("loading") == "1"

    # Show interstitial page for women filter (which can be slow)
    if women and loading:
        # Build the URL to redirect to after loading
        target_url = url_for(
            "browse",
            q=q, src=src, sort=sort,
            women="1",
            year_min=year_min, year_max=year_max,
            page=page,
            plots="1" if show_plots else "0"
        )
        return render_template("loading.html", title="Loading...", target_url=target_url)

    import time

    PAGE_SIZE = 20  # Target number of movies per page

    # Stats tracking
    total_movies_inspected = 0
    tmdb_pages_fetched = 0

    if women:
        # When women filter is active, fetch TMDb pages until we have enough women-directed movies
        all_women_directed = []
        tmdb_page = 1
        max_pages_to_fetch = 50  # Safety limit to avoid fetching forever
        hydrated_count = 0

        print(f"Fetching women-directed movies for user page {page}...")

        # Fetch enough movies for current page + 1 extra to know if there's a next page
        target_count = (page * PAGE_SIZE) + 1
        while len(all_women_directed) < target_count and tmdb_page <= max_pages_to_fetch:
            if src == "search" and q:
                payload = tmdb.search_movie(q, page=tmdb_page)
            else:
                payload = tmdb.popular_movies(page=tmdb_page)

            results = payload.get("results") or []
            if not results:
                break

            tmdb_pages_fetched += 1
            total_movies_inspected += len(results)

            # Upsert and hydrate
            for m in results:
                upsert_movie_from_tmdb_payload(m)
                mid = m.get("id")
                if mid and not directors_hydrated(int(mid)):
                    try:
                        hydrate_directors(int(mid))
                        hydrated_count += 1
                        time.sleep(0.05)
                    except Exception as e:
                        print(f"Failed to hydrate directors for movie {mid}: {e}")

            # Check which movies are women-directed
            page_ids = [int(m["id"]) for m in results if m.get("id")]
            if page_ids:
                placeholders = ",".join(["?"] * len(page_ids))
                with connect() as conn:
                    women_movies = conn.execute(
                        f"""
                        SELECT m.tmdb_id
                        FROM movies m
                        WHERE m.tmdb_id IN ({placeholders})
                          AND EXISTS (
                            SELECT 1
                            FROM credits_director cd
                            JOIN people p ON p.tmdb_person_id = cd.tmdb_person_id
                            WHERE cd.tmdb_id = m.tmdb_id
                              AND p.gender = 1
                          )
                        """,
                        page_ids,
                    ).fetchall()

                # Prefetch posters for women-directed movies
                for row in women_movies:
                    prefetch_poster(row["tmdb_id"])

                all_women_directed.extend([r["tmdb_id"] for r in women_movies])

            print(f"  TMDb page {tmdb_page}: found {len(all_women_directed)} women-directed movies so far")
            tmdb_page += 1

        if hydrated_count > 0:
            print(f"Hydrated directors for {hydrated_count} movies")

        # Paginate the women-directed movies
        start_idx = (page - 1) * PAGE_SIZE
        end_idx = start_idx + PAGE_SIZE
        page_movie_ids = all_women_directed[start_idx:end_idx]
        has_next = len(all_women_directed) > end_idx

        where = ["1=1"]
        params = []

        if page_movie_ids:
            placeholders = ",".join(["?"] * len(page_movie_ids))
            where.append(f"m.tmdb_id IN ({placeholders})")
            params.extend(page_movie_ids)
        else:
            where.append("0=1")
    else:
        # Normal mode: just fetch one page from TMDb
        if src == "search" and q:
            payload = tmdb.search_movie(q, page=page)
        else:
            payload = tmdb.popular_movies(page=page)

        results = payload.get("results") or []
        has_next = page < int(payload.get("total_pages") or page)

        for m in results:
            upsert_movie_from_tmdb_payload(m)

        where = ["1=1"]
        params = []

        page_ids = [int(m["id"]) for m in results if m.get("id")]
        if page_ids:
            placeholders = ",".join(["?"] * len(page_ids))
            where.append(f"m.tmdb_id IN ({placeholders})")
            params.extend(page_ids)
        else:
            where.append("0=1")

    if year_min.isdigit():
        where.append("m.year >= ?")
        params.append(int(year_min))
    if year_max.isdigit():
        where.append("m.year <= ?")
        params.append(int(year_max))

    if women:
        where.append("""
          EXISTS (
            SELECT 1
            FROM credits_director cd
            JOIN people p ON p.tmdb_person_id = cd.tmdb_person_id
            WHERE cd.tmdb_id = m.tmdb_id
              AND p.gender = 1
          )
        """)

    order = {
        "popularity": "m.popularity DESC NULLS LAST",
        "rating": "m.vote_avg DESC NULLS LAST",
        "votes": "m.vote_count DESC NULLS LAST",
        "year": "m.year DESC NULLS LAST",
    }.get(sort, "m.popularity DESC NULLS LAST")

    with connect() as conn:
        movies = conn.execute(
            f"""
            SELECT m.*
            FROM movies m
            WHERE {" AND ".join(where)}
            ORDER BY {order}
            """,
            params,
        ).fetchall()

    toggle_plots_url = url_for(
        "browse",
        q=q, src=src, sort=sort,
        women="1" if women else "0",
        year_min=year_min, year_max=year_max,
        page=page,
        plots="0" if show_plots else "1"
    )

    return render_template(
        "browse.html",
        title="Browse",
        movies=movies,
        q=q,
        src=src,
        sort=sort,
        women=women,
        year_min=year_min,
        year_max=year_max,
        page=page,
        has_next=has_next,
        show_plots=show_plots,
        toggle_plots_url=toggle_plots_url,
        total_movies_inspected=total_movies_inspected,
        tmdb_pages_fetched=tmdb_pages_fetched,
        movies_shown=len(movies),
        page_url=page_url_builder(
            q=q, src=src, sort=sort,
            women="1" if women else "0",
            year_min=year_min, year_max=year_max,
            plots="1" if show_plots else "0",
            loading="1" if women else "0"
        ),
    )

@app.post("/selection")
def selection_action():
    check_csrf()
    action = request.form.get("action") or ""
    picked = request.form.getlist("pick")
    picked_ids = [int(x) for x in picked if x.isdigit()]
    b = basket_ids()

    if action == "selected":
        movies = fetch_movies_for_ids(picked_ids)
        return_to = request.form.get("return_to") or url_for("browse")
        show_plots = request.args.get("plots") == "1"

        # Build toggle URL by adding/removing plots parameter from return_to
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
        parsed = urlparse(return_to)
        params = parse_qs(parsed.query)
        if show_plots:
            params["plots"] = ["0"]
        else:
            params["plots"] = ["1"]
        new_query = urlencode(params, doseq=True)
        toggle_plots_url = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))

        return render_template(
            "selected.html",
            title="Selected",
            movies=movies,
            return_to=return_to,
            show_plots=show_plots,
            toggle_plots_url=toggle_plots_url
        )

    if action == "add_to_basket":
        b.update(picked_ids)
        set_basket(b)

    elif action == "remove_from_basket":
        for i in picked_ids:
            b.discard(i)
        set_basket(b)

    elif action == "clear_basket":
        set_basket(set())

    return_to = request.form.get("return_to") or url_for("browse")
    return redirect(return_to)

@app.get("/basket")
def basket():
    ids = sorted(basket_ids())
    movies = fetch_movies_for_ids(ids)
    show_plots = request.args.get("plots") == "1"
    toggle_plots_url = url_for("basket", plots="0" if show_plots else "1")
    return render_template(
        "basket.html",
        title="Basket",
        movies=movies,
        show_plots=show_plots,
        toggle_plots_url=toggle_plots_url
    )

@app.post("/basket/remove")
def basket_remove():
    check_csrf()
    picked = request.form.getlist("pick")
    picked_ids = [int(x) for x in picked if x.isdigit()]
    b = basket_ids()
    for i in picked_ids:
        b.discard(i)
    set_basket(b)
    return redirect(url_for("basket"))

@app.post("/basket/clear")
def basket_clear():
    check_csrf()
    set_basket(set())
    return redirect(url_for("basket"))

@app.post("/basket/share")
def basket_share():
    check_csrf()
    ids = sorted(basket_ids())
    if not ids:
        return redirect(url_for("basket"))

    token = secrets.token_urlsafe(6).replace("-", "").replace("_", "")
    title = (request.form.get("title") or "").strip() or None

    with connect() as conn:
        conn.execute(
            "INSERT INTO shared_sets (token,title,created_at) VALUES (?,?,?)",
            (token, title, now_iso()),
        )
        for tmdb_id in ids:
            conn.execute(
                "INSERT OR IGNORE INTO shared_set_items (token, tmdb_id) VALUES (?,?)",
                (token, tmdb_id),
            )

    return redirect(url_for("share_view", token=token))

@app.get("/s/<token>")
def share_view(token: str):
    with connect() as conn:
        share = conn.execute("SELECT * FROM shared_sets WHERE token=?", (token,)).fetchone()
        if not share:
            abort(404)
        items = conn.execute(
            "SELECT tmdb_id FROM shared_set_items WHERE token=? ORDER BY tmdb_id",
            (token,),
        ).fetchall()

    ids = [int(r["tmdb_id"]) for r in items]
    movies = fetch_movies_for_ids(ids)
    show_plots = request.args.get("plots") == "1"
    toggle_plots_url = url_for("share_view", token=token, plots="0" if show_plots else "1")
    return render_template(
        "share.html",
        title="Shared",
        token=token,
        share_title=share["title"],
        movies=movies,
        show_plots=show_plots,
        toggle_plots_url=toggle_plots_url
    )

@app.post("/s/<token>/fork")
def share_fork(token: str):
    check_csrf()
    with connect() as conn:
        items = conn.execute(
            "SELECT tmdb_id FROM shared_set_items WHERE token=?",
            (token,),
        ).fetchall()
    ids = [int(r["tmdb_id"]) for r in items]
    b = basket_ids()
    b.update(ids)
    set_basket(b)
    return redirect(url_for("basket"))

@app.get("/movie/<int:tmdb_id>")
def movie(tmdb_id: int):
    hydrate_movie_details_if_needed(tmdb_id)
    hydrate_directors(tmdb_id)

    with connect() as conn:
        m = conn.execute("SELECT * FROM movies WHERE tmdb_id=?", (tmdb_id,)).fetchone()
        directors = conn.execute(
            """
            SELECT p.*
            FROM credits_director cd
            JOIN people p ON p.tmdb_person_id = cd.tmdb_person_id
            WHERE cd.tmdb_id=?
            ORDER BY p.name
            """,
            (tmdb_id,),
        ).fetchall()

    if not m:
        abort(404)

    movie_obj = dict(m)
    movie_obj["tmdb_id"] = tmdb_id
    return render_template("movie.html", title=movie_obj["title"], movie=movie_obj, directors=directors)

@app.get("/img/poster/<size>/<int:tmdb_id>.jpg")
def poster(size: str, tmdb_id: int):
    if size not in {"w185", "w342", "w500", "w780"}:
        size = "w342"

    with connect() as conn:
        row = conn.execute("SELECT poster_path FROM movies WHERE tmdb_id=?", (tmdb_id,)).fetchone()
    if not row or not row["poster_path"]:
        abort(404)

    poster_path = row["poster_path"]
    cache_path = CACHE_DIR / f"{tmdb_id}_{size}.jpg"

    if cache_path.exists():
        return send_file(cache_path, mimetype="image/jpeg")

    import requests
    url = tmdb.poster_url(poster_path, size=size)
    r = requests.get(url, stream=True, timeout=20)
    r.raise_for_status()
    with open(cache_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=1024 * 64):
            if chunk:
                f.write(chunk)

    return send_file(cache_path, mimetype="image/jpeg")


if __name__ == "__main__":
    init_db()
    debug_mode = os.getenv("DEBUG", "false").lower() in ("true", "1", "yes")
    # Bind to 0.0.0.0 in production for network access, 127.0.0.1 in debug mode
    host = "127.0.0.1" if debug_mode else "0.0.0.0"
    app.run(host=host, port=int(os.getenv("PORT", "5150")), debug=debug_mode)
