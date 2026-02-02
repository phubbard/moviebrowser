PRAGMA journal_mode=WAL;

CREATE TABLE IF NOT EXISTS movies (
  tmdb_id         INTEGER PRIMARY KEY,
  title           TEXT NOT NULL,
  year            INTEGER,
  runtime         INTEGER,
  overview        TEXT,
  poster_path     TEXT,
  backdrop_path   TEXT,
  vote_avg        REAL,
  vote_count      INTEGER,
  popularity      REAL,
  updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS people (
  tmdb_person_id  INTEGER PRIMARY KEY,
  name            TEXT NOT NULL,
  gender          INTEGER NOT NULL,   -- 0 unknown, 1 female, 2 male, 3 non-binary (TMDb)
  updated_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS credits_director (
  tmdb_id         INTEGER NOT NULL,
  tmdb_person_id  INTEGER NOT NULL,
  PRIMARY KEY (tmdb_id, tmdb_person_id)
);

CREATE TABLE IF NOT EXISTS shared_sets (
  token           TEXT PRIMARY KEY,
  title           TEXT,
  created_at      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS shared_set_items (
  token           TEXT NOT NULL,
  tmdb_id         INTEGER NOT NULL,
  PRIMARY KEY (token, tmdb_id)
);

CREATE TABLE IF NOT EXISTS ingest_queue (
  tmdb_id         INTEGER PRIMARY KEY,
  status          TEXT NOT NULL,  -- pending, in_progress, done, failed
  attempts        INTEGER NOT NULL DEFAULT 0,
  last_attempt    TEXT,
  last_error      TEXT,
  added_at        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS ingest_state (
  key             TEXT PRIMARY KEY,
  value           TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_movies_year ON movies(year);
CREATE INDEX IF NOT EXISTS idx_movies_vote_avg ON movies(vote_avg);
CREATE INDEX IF NOT EXISTS idx_movies_vote_count ON movies(vote_count);
CREATE INDEX IF NOT EXISTS idx_movies_popularity ON movies(popularity);
CREATE INDEX IF NOT EXISTS idx_movies_title ON movies(title);
CREATE INDEX IF NOT EXISTS idx_cd_person ON credits_director(tmdb_person_id);
CREATE INDEX IF NOT EXISTS idx_people_gender ON people(gender);
CREATE INDEX IF NOT EXISTS idx_ingest_status ON ingest_queue(status);
