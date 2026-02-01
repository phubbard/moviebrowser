# Movie Browser (No-JS) — Agent Instructions

## Project goals
Build a tiny responsive web app for browsing movies with posters, filters, and shareable shortlists,
with **no client-side JavaScript**. Prioritize simplicity, speed, and clean server-rendered HTML.

Must-haves:
- Poster grid browse page
- Per-movie checkbox selection
- Action button to show only selected items
- A persistent “basket” that survives pagination WITHOUT login (cookie session)
- Share links that allow others to view and “fork” into their own basket

Nice-to-haves (later):
- Export CSV
- Multi-list support (beyond basket)
- Better women-directed coverage (credits hydration improvements)
- Background updater / caching improvements

Non-goals:
- Full streaming availability (intentionally dropped)
- SPA behavior / infinite scroll (would require JS)

## Constraints
- No JS in the browser.
- Keep dependencies minimal (Flask + requests; SQLite).
- Use Water.css for styling; tiny custom CSS only.
- Use query parameters for filters and pagination; URLs should be shareable/bookmarkable.
- Don’t break accessibility: labels for inputs, semantic HTML.

## Data sources and correctness
Use TMDb for:
- movie details and credits
- posters/backdrops
- person gender field (0 unknown, 1 female, 2 male, 3 non-binary)

Important nuance:
- “Women-directed” filter requires director gender known.
- Credits and person gender may not be hydrated for every movie in browse results.
- Current approach: hydrate credits on movie detail view; women-filter on browse will only include hydrated items.
- Improve later by hydrating credits in the background or on browse for the displayed page.

## Architecture overview
- `app.py`: Flask app, routes, sessions, HTML rendering
- `tmdb.py`: TMDb API client
- `db.py`: SQLite connection and schema init
- `schema.sql`: database schema (movies, people, credits, shared sets)
- `templates/`: Jinja2 templates (server-rendered)
- `static/extra.css`: minimal CSS for grid and sticky action bars
- `cache/posters`: on-disk poster cache via `/img/poster/<size>/<id>.jpg`

### Key flows
1) Browse:
- GET `/` with query params: q, src, sort, women, year_min, year_max, page
- Pulls a page from TMDb (search/popular), upserts movies into SQLite
- Reads from SQLite and applies filters
- Renders a checkbox grid with action buttons

2) Selection actions:
- POST `/selection` with action and pick[] ids
- action=selected: render a filtered view of just the selected ids
- action=add_to_basket/remove/clear: mutate basket in cookie session and redirect back

3) Basket:
- GET `/basket`: shows movies in session basket
- POST `/basket/remove`: remove checked
- POST `/basket/clear`: empty basket

4) Sharing:
- POST `/basket/share`: creates token, stores ids in SQLite, redirects to `/s/<token>`
- GET `/s/<token>`: renders shared set
- POST `/s/<token>/fork`: adds all ids to visitor basket

## Security notes
- Use a basic CSRF token stored in session and posted with forms.
- Use a real `APP_SECRET_KEY` in production (env var).
- Consider adding basic auth at the reverse proxy if deploying publicly.

## Performance notes
- Use SQLite WAL mode.
- Poster proxy caches images to disk to reduce repeated external requests.
- Keep browse page size reasonable (TMDb pagination).
- Avoid N+1 queries: fetch director info only when needed.

## Where to extend next
### Improve women-directed filtering coverage
Option A (simple):
- On browse, for the displayed page’s TMDb IDs, call credits for each movie and upsert directors.
- This is up to ~20 API calls per page; may hit rate limits.

Option B (better):
- Queue hydration jobs (background worker / cron) to hydrate credits gradually:
  - hydrate popular pages nightly
  - hydrate any movies added to basket
  - hydrate any movies viewed

### Add multi-list support (still no login)
- Replace single basket with named lists stored in session:
  - `session["lists"] = {"Watchlist":[...], "Party":[...]}`
- Provide “share list” per name, same token mechanism.

### Add export
- CSV: title, year, tmdb_id
- Plain text list of permalinks

## Testing checklist
- Browse loads without JS
- Checkboxes select, buttons work
- Basket persists across pagination
- Share link opens in a new browser and is viewable
- Fork adds to basket
- Poster cache serves images from disk after first load
- Women-directed filter works at least on hydrated items
