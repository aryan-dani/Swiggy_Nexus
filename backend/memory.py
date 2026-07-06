import sqlite3
import os
import json

DB_PATH = os.path.join(os.path.dirname(__file__), "nexus_memory.db")

def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_profile (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT UNIQUE,
                value TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS session_history (
                session_id TEXT,
                role TEXT,
                content TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

def get_user_preferences() -> dict:
    preferences = {}
    if not os.path.exists(DB_PATH):
        init_db()
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM user_profile")
        for k, v in cursor.fetchall():
            try:
                preferences[k] = json.loads(v)
            except (json.JSONDecodeError, ValueError):
                preferences[k] = v
    return preferences

def set_user_preference(key: str, value: str):
    if not os.path.exists(DB_PATH):
        init_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("INSERT OR REPLACE INTO user_profile (key, value) VALUES (?, ?)", (key, json.dumps(value)))

# Initialize DB with some mock preferences if empty
if not os.path.exists(DB_PATH):
    init_db()
    set_user_preference("dietary_restrictions", "Vegetarian")
    set_user_preference("favorite_cuisine", "Italian")
