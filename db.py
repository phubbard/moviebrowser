import sqlite3
from pathlib import Path

DB_PATH = Path("movies.sqlite3")

def connect():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    schema = Path("schema.sql").read_text(encoding="utf-8")
    with connect() as conn:
        conn.executescript(schema)
