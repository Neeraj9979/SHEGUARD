import os
import re
import sqlite3
import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_BACKEND = None  # Will be 'postgres' or 'sqlite'
SQLITE_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sheguard.db")


class SQLiteCursorWrapper:
    """Wraps an SQLite cursor to accept '%s' parameter placeholders like psycopg2."""
    def __init__(self, cursor):
        self._cur = cursor

    def execute(self, query, params=None):
        # Translate %s placeholder to ? for SQLite
        q = re.sub(r'(?<!%)(%s)', '?', query)
        if params is not None:
            # Convert booleans to 1/0 for SQLite compatibility if needed
            converted = [int(p) if isinstance(p, bool) else p for p in params]
            return self._cur.execute(q, converted)
        return self._cur.execute(q)

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    def close(self):
        return self._cur.close()

    @property
    def rowcount(self):
        return self._cur.rowcount

    @property
    def description(self):
        return self._cur.description


class SQLiteConnectionWrapper:
    """Wraps an SQLite connection to mirror psycopg2 connection interface."""
    def __init__(self, db_path):
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA foreign_keys = ON;")

    def cursor(self):
        return SQLiteCursorWrapper(self._conn.cursor())

    def commit(self):
        return self._conn.commit()

    def rollback(self):
        return self._conn.rollback()

    def close(self):
        return self._conn.close()


def get_db():
    """
    Connect to PostgreSQL if available; otherwise automatically fallback to SQLite.
    Set DB_TYPE=sqlite in .env to force SQLite.
    """
    global DB_BACKEND
    force_sqlite = os.getenv("DB_TYPE", "").lower() == "sqlite"

    if not force_sqlite:
        try:
            conn = psycopg2.connect(
                host=os.getenv("DB_HOST", "localhost"),
                database=os.getenv("DB_NAME", "sheguard_db"),
                user=os.getenv("DB_USER", "postgres"),
                password=os.getenv("DB_PASSWORD", ""),
                port=os.getenv("DB_PORT", "5432"),
                connect_timeout=2
            )
            DB_BACKEND = "postgres"
            return conn
        except Exception:
            # Fall back to SQLite
            pass

    DB_BACKEND = "sqlite"
    return SQLiteConnectionWrapper(SQLITE_DB_PATH)


def create_tables():
    """Initializes tables for either PostgreSQL or SQLite."""
    con = get_db()
    cur = con.cursor()

    if DB_BACKEND == "postgres":
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id SERIAL PRIMARY KEY,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(150) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                phone VARCHAR(20),
                sms_enabled BOOLEAN DEFAULT FALSE,
                tracking_enabled BOOLEAN DEFAULT FALSE
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS emergency_contacts (
                contact_id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(user_id)
                    ON DELETE CASCADE,
                contact_name VARCHAR(100) NOT NULL,
                phone VARCHAR(20) NOT NULL
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS sos_alerts (
                alert_id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(user_id)
                    ON DELETE CASCADE,
                latitude DOUBLE PRECISION NOT NULL,
                longitude DOUBLE PRECISION NOT NULL,
                alert_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR(30) DEFAULT 'ACTIVE'
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS location_history (
                location_id BIGSERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(user_id)
                    ON DELETE CASCADE,
                latitude DOUBLE PRECISION NOT NULL,
                longitude DOUBLE PRECISION NOT NULL,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_location_user_time
            ON location_history(user_id, recorded_at DESC)
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS risk_analysis (
                analysis_id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(user_id)
                    ON DELETE CASCADE,
                risk_level VARCHAR(30),
                risk_score FLOAT,
                analysis_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS sms_logs (
                sms_id SERIAL PRIMARY KEY,
                user_id INTEGER REFERENCES users(user_id)
                    ON DELETE CASCADE,
                contact_id INTEGER REFERENCES emergency_contacts(contact_id)
                    ON DELETE SET NULL,
                alert_id INTEGER REFERENCES sos_alerts(alert_id)
                    ON DELETE SET NULL,
                phone VARCHAR(20),
                message_sid VARCHAR(100),
                status VARCHAR(50),
                error_message TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS sms_enabled
            BOOLEAN DEFAULT FALSE
        """)

        cur.execute("""
            ALTER TABLE users
            ADD COLUMN IF NOT EXISTS tracking_enabled
            BOOLEAN DEFAULT FALSE
        """)

    else:
        # SQLite schema
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(100) NOT NULL,
                email VARCHAR(150) UNIQUE NOT NULL,
                password VARCHAR(255) NOT NULL,
                phone VARCHAR(20),
                sms_enabled BOOLEAN DEFAULT 0,
                tracking_enabled BOOLEAN DEFAULT 0
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS emergency_contacts (
                contact_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES users(user_id)
                    ON DELETE CASCADE,
                contact_name VARCHAR(100) NOT NULL,
                phone VARCHAR(20) NOT NULL
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS sos_alerts (
                alert_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES users(user_id)
                    ON DELETE CASCADE,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                alert_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status VARCHAR(30) DEFAULT 'ACTIVE'
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS location_history (
                location_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES users(user_id)
                    ON DELETE CASCADE,
                latitude REAL NOT NULL,
                longitude REAL NOT NULL,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_location_user_time
            ON location_history(user_id, recorded_at DESC)
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS risk_analysis (
                analysis_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES users(user_id)
                    ON DELETE CASCADE,
                risk_level VARCHAR(30),
                risk_score REAL,
                analysis_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS sms_logs (
                sms_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER REFERENCES users(user_id)
                    ON DELETE CASCADE,
                contact_id INTEGER REFERENCES emergency_contacts(contact_id)
                    ON DELETE SET NULL,
                alert_id INTEGER REFERENCES sos_alerts(alert_id)
                    ON DELETE SET NULL,
                phone VARCHAR(20),
                message_sid VARCHAR(100),
                status VARCHAR(50),
                error_message TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    con.commit()
    cur.close()
    con.close()
    print(f"Database initialized successfully using backend: {DB_BACKEND}")
