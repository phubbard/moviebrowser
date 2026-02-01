# Movie Browser (No-JS)

A lightweight, server-rendered web app for browsing movies with a focus on women-directed films. Built with Flask and TMDb API, featuring zero client-side JavaScript.

## Features

- 🎬 Browse movies from TMDb (popular or search)
- 👩‍🎨 Filter by women-directed films
- 🗓️ Year range filtering
- 🛒 Session-based basket (no login required)
- 🔗 Shareable movie lists
- 📱 Responsive design (Water.css)
- 🖼️ Poster caching for fast loads
- 🔍 Search links (JustWatch integration)
- 📊 Shows fetch stats (movies inspected per page)

## Tech Stack

- **Backend**: Flask 3.0
- **Database**: SQLite with WAL mode
- **API**: TMDb API v3
- **Styling**: Water.css + minimal custom CSS
- **Zero JavaScript**: Pure server-rendered HTML

## Installation

### Prerequisites

- Python 3.10+
- TMDb API key ([get one here](https://www.themoviedb.org/settings/api))

### Setup

1. **Clone the repository**
   ```bash
   git clone git@github.com:phubbard/moviebrowser.git
   cd moviebrowser
   ```

2. **Create a virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**
   ```bash
   cp .env.example .env
   ```

   Edit `.env` and add your TMDb API key:
   ```
   TMDB_API_KEY=your_api_key_here
   ```

5. **Run the application**
   ```bash
   python app.py
   ```

6. **Open your browser**
   ```
   http://127.0.0.1:5150
   ```

## Getting a TMDb API Key

1. Create a free account at [themoviedb.org](https://www.themoviedb.org/signup)
2. Go to [Account Settings → API](https://www.themoviedb.org/settings/api)
3. Click "Request an API Key"
4. Choose "Developer" option
5. Fill out the form (personal use is fine)
6. Copy your API Key (v3 auth)
7. Add it to your `.env` file

## Configuration

Environment variables (optional):

- `TMDB_API_KEY` - **Required**. Your TMDb API key
- `APP_SECRET_KEY` - Flask secret key (auto-generated if not set)
- `TMDB_REGION` - Default: "US"
- `TMDB_LANGUAGE` - Default: "en-US"
- `PORT` - Default: 5150
- `SEARCH_LINK_1_LABEL` / `SEARCH_LINK_1_URL` - First search link (e.g., JustWatch)
- `SEARCH_LINK_2_LABEL` / `SEARCH_LINK_2_URL` - Second search link (e.g., local server)

### Customizing Search Links

Edit `.env` to customize the search links shown on each movie card:

```bash
SEARCH_LINK_1_LABEL=Google
SEARCH_LINK_1_URL=https://www.google.com/search?q={title}+movie

SEARCH_LINK_2_LABEL=IMDb
SEARCH_LINK_2_URL=https://www.imdb.com/find?q={title}
```

Use `{title}` as a placeholder - it will be replaced with the movie title (URL-encoded automatically). You can configure 0-2 search links. Leave blank to disable.

## Usage

### Browsing Movies

1. **Women-directed filter** is on by default
2. Use filters for year range, sort order, etc.
3. Click "Apply" to refresh results
4. Toggle "Show plots" to see movie synopses

### Managing Your Basket

1. Check movie posters to select them
2. Click "Add selected to basket"
3. Basket persists across pages (session cookie)
4. View your basket anytime via the header link

### Sharing Lists

1. Add movies to your basket
2. Go to Basket page
3. Enter a title (optional)
4. Click "Create share link"
5. Share the generated URL with others
6. Others can "fork" your list to their basket

## Project Structure

```
movielist/
├── app.py              # Flask routes and logic
├── db.py               # Database connection
├── tmdb.py             # TMDb API client
├── schema.sql          # Database schema
├── requirements.txt    # Python dependencies
├── .env                # Environment variables (not in git)
├── templates/          # Jinja2 templates
│   ├── base.html
│   ├── browse.html
│   ├── basket.html
│   ├── movie.html
│   ├── selected.html
│   ├── share.html
│   └── loading.html
├── static/
│   └── extra.css       # Custom CSS
└── cache/
    └── posters/        # Cached poster images
```

## How It Works

### Women-Directed Filter

When active, the app:
1. Fetches pages from TMDb's popular/search endpoints
2. Hydrates director credits for each movie
3. Checks director gender from TMDb person data
4. Filters to only show movies with female directors
5. Continues fetching until a full page is collected

The footer shows stats: e.g., "20 movies found from 221 inspected (12 TMDb pages)"

### Poster Caching

- First request: Downloads from TMDb and saves to `cache/posters/`
- Subsequent requests: Serves from disk
- Pre-fetches posters for women-directed movies during filtering

### No JavaScript Architecture

All interactions use standard HTML forms and links:
- Filters → GET parameters
- Actions → POST forms
- State → Session cookies
- Loading → Meta refresh

## Development

Run in debug mode (auto-reload enabled):
```bash
python app.py
```

Database is created automatically on first run at `movies.sqlite3`.

## Deployment Notes

- Use a real `APP_SECRET_KEY` in production
- Consider adding basic auth at reverse proxy level
- SQLite is suitable for small-scale deployment
- Poster cache grows over time (no expiration yet)
- Rate limit: TMDb allows 50 requests/second

## Credits

- Movie data from [The Movie Database (TMDb)](https://www.themoviedb.org/)
- Styling by [Water.css](https://watercss.kognise.dev/)
- Built by Paul Hubbard © 2026

## License

This product uses the TMDb API but is not endorsed or certified by TMDb.
