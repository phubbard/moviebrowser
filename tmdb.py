import os
import time
import requests

TMDB_BASE = "https://api.themoviedb.org/3"
TMDB_IMG = "https://image.tmdb.org/t/p"

class TMDb:
    def __init__(self, api_key: str | None = None, region: str = "US", language: str = "en-US"):
        self.api_key = api_key or os.getenv("TMDB_API_KEY")
        if not self.api_key:
            raise RuntimeError("TMDB_API_KEY is required")
        self.region = region
        self.language = language
        self.session = requests.Session()

    def _get(self, path: str, **params):
        url = f"{TMDB_BASE}{path}"
        params.setdefault("api_key", self.api_key)
        params.setdefault("language", self.language)
        r = self.session.get(url, params=params, timeout=20)
        r.raise_for_status()
        return r.json()

    def search_movie(self, query: str, page: int = 1):
        return self._get("/search/movie", query=query, page=page, include_adult="false", region=self.region)

    def popular_movies(self, page: int = 1):
        return self._get("/movie/popular", page=page, region=self.region)

    def movie_details(self, tmdb_id: int):
        return self._get(f"/movie/{tmdb_id}")

    def movie_credits(self, tmdb_id: int):
        return self._get(f"/movie/{tmdb_id}/credits")

    def movie_changes(self, start_date: str | None = None, end_date: str | None = None, page: int = 1):
        params = {"page": page}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
        return self._get("/movie/changes", **params)

    @staticmethod
    def poster_url(poster_path: str, size: str = "w342") -> str:
        return f"{TMDB_IMG}/{size}{poster_path}"

    @staticmethod
    def backdrop_url(backdrop_path: str, size: str = "w780") -> str:
        return f"{TMDB_IMG}/{size}{backdrop_path}"

def now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
