"""SQLite database: schema, connection, helpers."""

import sqlite3
from contextlib import contextmanager
from dashboard.config import DB_PATH


SCHEMA = """
CREATE TABLE IF NOT EXISTS signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    query TEXT,
    url TEXT UNIQUE NOT NULL,
    post_id TEXT,
    subreddit TEXT,
    title TEXT,
    body TEXT,
    text_snippet TEXT,
    created_at_raw TEXT,
    author_raw TEXT,
    scraped_success BOOLEAN DEFAULT 1,
    scrape_error TEXT,
    is_question BOOLEAN DEFAULT 0,
    mentions_parent_context BOOLEAN DEFAULT 0,
    mentions_child BOOLEAN DEFAULT 0,
    child_age_signal TEXT,
    location_signal TEXT,
    activity_type_signal TEXT,
    pain_signal TEXT,
    intent_signal TEXT,
    relevance_score INTEGER DEFAULT 0,
    why_relevant TEXT,
    status TEXT DEFAULT 'new',
    closed_reason TEXT,
    not_fit_reason TEXT,
    feedback TEXT,
    discovered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status_changed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_signals_status ON signals(status);
CREATE INDEX IF NOT EXISTS idx_signals_relevance ON signals(relevance_score DESC);
CREATE INDEX IF NOT EXISTS idx_signals_subreddit ON signals(subreddit);

CREATE TABLE IF NOT EXISTS cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id INTEGER NOT NULL REFERENCES signals(id),
    reply_text TEXT,
    reply_comment_id TEXT,
    reply_url TEXT,
    replied_at TIMESTAMP,
    last_checked_at TIMESTAMP,
    new_replies_count INTEGER DEFAULT 0,
    last_reply_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closed_at TIMESTAMP,
    closed_reason TEXT
);

CREATE INDEX IF NOT EXISTS idx_cases_signal ON cases(signal_id);

CREATE TABLE IF NOT EXISTS draft_replies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id INTEGER NOT NULL REFERENCES signals(id),
    reply_type TEXT,
    reply_text TEXT,
    generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_drafts_signal ON draft_replies(signal_id);

CREATE TABLE IF NOT EXISTS thread_replies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    case_id INTEGER NOT NULL REFERENCES cases(id),
    comment_id TEXT,
    author TEXT,
    body TEXT,
    score INTEGER,
    created_utc INTEGER,
    is_op BOOLEAN DEFAULT 0,
    fetched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_thread_replies_case ON thread_replies(case_id);

CREATE TABLE IF NOT EXISTS feedback_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    signal_id INTEGER REFERENCES signals(id),
    feedback_type TEXT,
    reason TEXT,
    subreddit TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_feedback_subreddit ON feedback_log(subreddit);

CREATE TABLE IF NOT EXISTS learned_patterns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pattern_type TEXT,
    value TEXT UNIQUE,
    hit_count INTEGER DEFAULT 0,
    action TEXT,
    threshold INTEGER DEFAULT 2,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_patterns_value ON learned_patterns(value);
"""


def init_db():
    """Create database and tables."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(SCHEMA)
    print(f"Database initialized: {DB_PATH}")


@contextmanager
def get_db():
    """Get a database connection with row_factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def query_one(sql, params=()):
    """Execute query and return one row as dict."""
    with get_db() as conn:
        row = conn.execute(sql, params).fetchone()
        return dict(row) if row else None


def query_all(sql, params=()):
    """Execute query and return all rows as dicts."""
    with get_db() as conn:
        rows = conn.execute(sql, params).fetchall()
        return [dict(r) for r in rows]


def execute(sql, params=()):
    """Execute a write query and return lastrowid."""
    with get_db() as conn:
        cursor = conn.execute(sql, params)
        return cursor.lastrowid


def execute_many(sql, params_list):
    """Execute many write queries."""
    with get_db() as conn:
        conn.executemany(sql, params_list)


if __name__ == "__main__":
    init_db()
