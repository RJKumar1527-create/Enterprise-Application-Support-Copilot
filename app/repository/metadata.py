import json
import sqlite3
from pathlib import Path
DB=Path("data/metadata.db")

def connect():
    DB.parent.mkdir(parents=True,exist_ok=True); c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def initialize():
    with connect() as c:
        c.executescript("""CREATE TABLE IF NOT EXISTS documents(document_id TEXT PRIMARY KEY,document_type TEXT,domain TEXT,title TEXT,version TEXT,source TEXT,content_hash TEXT,status TEXT,updated_at TEXT); CREATE TABLE IF NOT EXISTS ingestion_runs(run_id TEXT PRIMARY KEY,started_at TEXT,documents INTEGER,chunks INTEGER,added INTEGER,changed INTEGER,removed INTEGER,unchanged INTEGER,status TEXT);""")

def save_run(run):
    with connect() as c: c.execute("INSERT OR REPLACE INTO ingestion_runs VALUES(?,?,?,?,?,?,?,?,?)",tuple(run[k] for k in ["run_id","started_at","documents","chunks","added","changed","removed","unchanged","status"]))
def list_runs():
    with connect() as c: return [dict(x) for x in c.execute("SELECT * FROM ingestion_runs ORDER BY started_at DESC").fetchall()]
