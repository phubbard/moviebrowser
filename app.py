import os
import secrets
from flask import Flask, render_template, request, redirect, url_for, session, abort, send_file
from db import init_db, connect
from tmdb import TMDb
from store import (
    CACHE_DIR,
    fetch_movies_for_ids,
)

from dotenv import load_dotenv
load_dotenv()

APP_SECRET = os.getenv("APP_SECRET_KEY") or secrets.token_hex(16)

app = Flask(__name__)
app.secret_key = APP_SECRET


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

def page_url_builder(**base_params):
    def _builder(page: int):
        params = dict(base_params)
        params["page"] = page
        return url_for("browse", **params)
    return _builder


@app.get("/")
def browse():
    q = (request.args.get("q") or "").strip()
    sort = request.args.get("sort") or "popularity"
    year_min = (request.args.get("year_min") or "").strip()
    year_max = (request.args.get("year_max") or "").strip()
    page = int(request.args.get("page") or 1)
    show_plots = request.args.get("plots") == "1"
    PAGE_SIZE = 20

    where = ["1=1"]
    params = []

    if q:
        where.append("m.title LIKE ?")
        params.append(f"%{q}%")

    if year_min.isdigit():
        where.append("m.year >= ?")
        params.append(int(year_min))
    if year_max.isdigit():
        where.append("m.year <= ?")
        params.append(int(year_max))

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

    limit = PAGE_SIZE + 1
    offset = (page - 1) * PAGE_SIZE
    with connect() as conn:
        total_count = conn.execute(
            f"""
            SELECT COUNT(*)
            FROM movies m
            WHERE {" AND ".join(where)}
            """,
            params,
        ).fetchone()[0]
        movies = conn.execute(
            f"""
            SELECT m.*
            FROM movies m
            WHERE {" AND ".join(where)}
            ORDER BY {order}
            LIMIT ? OFFSET ?
            """,
            params + [limit, offset],
        ).fetchall()

    has_next = len(movies) > PAGE_SIZE
    movies = movies[:PAGE_SIZE]

    toggle_plots_url = url_for(
        "browse",
        q=q, sort=sort,
        year_min=year_min, year_max=year_max,
        page=page,
        plots="0" if show_plots else "1"
    )

    return render_template(
        "browse.html",
        title="Browse",
        movies=movies,
        q=q,
        sort=sort,
        year_min=year_min,
        year_max=year_max,
        page=page,
        has_next=has_next,
        show_plots=show_plots,
        toggle_plots_url=toggle_plots_url,
        total_movie_count=total_count,
        page_url=page_url_builder(
            q=q, sort=sort,
            year_min=year_min, year_max=year_max,
            plots="1" if show_plots else "0"
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
    url = TMDb.poster_url(poster_path, size=size)
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
