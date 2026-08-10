import sqlite3
import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scraper.db")

def init_db():
    """Initializes the scraper database and tables if they don't exist."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS scrape_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_type TEXT NOT NULL,
            source_id TEXT NOT NULL UNIQUE,
            title TEXT,
            niche TEXT,
            channel_name TEXT,
            scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    logger.info(f"Initialized database at {DB_PATH}")

def check_exists(source_id: str) -> bool:
    """Checks if a source ID has already been scraped."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM scrape_history WHERE source_id = ?", (source_id,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def add_to_history(source_type: str, source_id: str, title: str, niche: str, channel_name: str):
    """Adds a newly scraped item to the history tracking database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO scrape_history (source_type, source_id, title, niche, channel_name, scraped_at) VALUES (?, ?, ?, ?, ?, ?)",
            (source_type, source_id, title, niche, channel_name, datetime.now())
        )
        conn.commit()
    except sqlite3.IntegrityError:
        logger.warning(f"Attempted to insert duplicate source_id: {source_id}")
    finally:
        conn.close()
