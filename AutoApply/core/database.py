import sqlite3
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
import os

DB_PATH = os.path.join("data", "jobs.db")

def _get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _init_db():
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id                TEXT PRIMARY KEY,
                platform          TEXT NOT NULL,
                title             TEXT NOT NULL,
                company           TEXT NOT NULL,
                location          TEXT,
                region            TEXT,
                url               TEXT UNIQUE NOT NULL,
                description       TEXT,
                match_score       INTEGER DEFAULT 0,
                matching_skills   TEXT,
                skill_gaps        TEXT,
                cv_used           TEXT,
                status            TEXT DEFAULT 'discovered',
                cover_letter_path TEXT,
                easy_apply        INTEGER DEFAULT 0,
                date_posted       TEXT,
                discovered_at     TEXT NOT NULL,
                applied_at        TEXT,
                error_log         TEXT
            )
        """)
        # Migrate existing DB: add columns if missing
        new_cols = [
            "date_posted TEXT", "search_query TEXT", "ai_provider TEXT",
            "is_remote INTEGER", "requires_sponsorship INTEGER", "required_experience_years INTEGER"
        ]
        for col in new_cols:
            try:
                cursor.execute(f"ALTER TABLE jobs ADD COLUMN {col}")
            except sqlite3.OperationalError:
                pass  # column already exists
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS applications (
                id            TEXT PRIMARY KEY,
                job_id        TEXT REFERENCES jobs(id),
                submitted_at  TEXT NOT NULL,
                method        TEXT,
                cv_used       TEXT,
                cover_letter  TEXT,
                status        TEXT DEFAULT 'submitted'
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS profile (
                id   INTEGER PRIMARY KEY DEFAULT 1,
                data TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS answers_bank (
                question_key  TEXT PRIMARY KEY,
                answer        TEXT NOT NULL,
                context       TEXT,
                updated_at    TEXT
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS stats (
                date       TEXT PRIMARY KEY,
                discovered INTEGER DEFAULT 0,
                applied    INTEGER DEFAULT 0,
                skipped    INTEGER DEFAULT 0,
                failed     INTEGER DEFAULT 0,
                manual     INTEGER DEFAULT 0
            )
        """)
        conn.commit()

# Initialize DB on module import
_init_db()

def save_job(job: Dict[str, Any]) -> bool:
    """Save a job to the database. Returns True if the row was newly inserted, False if duplicate."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        
        # Pre-process lists/dicts to JSON strings if they are present in the dictionary
        processed_job = dict(job)
        if 'matching_skills' in processed_job and isinstance(processed_job['matching_skills'], list):
            processed_job['matching_skills'] = json.dumps(processed_job['matching_skills'])
        if 'skill_gaps' in processed_job and isinstance(processed_job['skill_gaps'], list):
            processed_job['skill_gaps'] = json.dumps(processed_job['skill_gaps'])

        columns = ', '.join(processed_job.keys())
        placeholders = ', '.join(['?'] * len(processed_job))
        query = f"INSERT OR IGNORE INTO jobs ({columns}) VALUES ({placeholders})"
        
        cursor.execute(query, tuple(processed_job.values()))
        conn.commit()
        return cursor.rowcount > 0

def is_duplicate_job(title: str, company: str) -> bool:
    """Check if a job with the same title and company already exists."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM jobs WHERE title = ? AND company = ?", (title, company))
        return cursor.fetchone() is not None

def get_jobs(status: Optional[str] = None) -> List[Dict[str, Any]]:
    with _get_connection() as conn:
        cursor = conn.cursor()
        if status:
            cursor.execute("SELECT * FROM jobs WHERE status = ?", (status,))
        else:
            cursor.execute("SELECT * FROM jobs")
        
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

def update_job(id: str, **fields) -> None:
    if not fields:
        return
        
    with _get_connection() as conn:
        cursor = conn.cursor()
        
        # Pre-process lists/dicts to JSON strings
        for key, value in fields.items():
            if isinstance(value, (list, dict)):
                fields[key] = json.dumps(value)
                
        set_clause = ', '.join([f"{k} = ?" for k in fields.keys()])
        query = f"UPDATE jobs SET {set_clause} WHERE id = ?"
        
        values = list(fields.values())
        values.append(id)
        
        cursor.execute(query, tuple(values))
        conn.commit()

def get_profile() -> Optional[Dict[str, Any]]:
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT data FROM profile WHERE id = 1")
        row = cursor.fetchone()
        
        if row:
            return json.loads(row['data'])
        return None


def mark_jobs_applied(urls: list[str]) -> int:
    """Mark jobs as 'applied' by their URLs. Returns count of jobs updated."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        updated = 0
        now = datetime.now().isoformat()
        for url in urls:
            cursor.execute(
                "UPDATE jobs SET status = 'applied', applied_at = ? WHERE url = ? AND status != 'applied'",
                (now, url),
            )
            updated += cursor.rowcount
        conn.commit()
        return updated

def mark_jobs_skipped(urls: list[str]) -> int:
    """Mark jobs as 'skipped' by their URLs. Returns count of jobs updated."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        updated = 0
        for url in urls:
            cursor.execute(
                "UPDATE jobs SET status = 'skipped' WHERE url = ? AND status != 'skipped'",
                (url,),
            )
            updated += cursor.rowcount
        conn.commit()
        return updated

def save_profile(data: Dict[str, Any]) -> None:
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO profile (id, data) VALUES (1, ?)", 
            (json.dumps(data),)
        )
        conn.commit()

def get_answer(question_key: str) -> Optional[str]:
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT answer FROM answers_bank WHERE question_key = ?", (question_key,))
        row = cursor.fetchone()
        
        if row:
            return row['answer']
        return None

def save_answer(question_key: str, answer: str, context: str = "") -> None:
    from datetime import datetime
    
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO answers_bank (question_key, answer, context, updated_at) VALUES (?, ?, ?, ?)",
            (question_key, answer, context, datetime.now().isoformat())
        )
        conn.commit()

def get_stats(date: str) -> Dict[str, Any]:
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM stats WHERE date = ?", (date,))
        row = cursor.fetchone()
        
        if row:
            return dict(row)
        return {
            "date": date,
            "discovered": 0,
            "applied": 0,
            "skipped": 0,
            "failed": 0,
            "manual": 0
        }

def update_stats(date: str, field: str, increment: int = 1) -> None:
    with _get_connection() as conn:
        cursor = conn.cursor()
        
        # Check if record exists
        cursor.execute("SELECT 1 FROM stats WHERE date = ?", (date,))
        if not cursor.fetchone():
            cursor.execute("INSERT INTO stats (date) VALUES (?)", (date,))
            
        # Update the chosen field
        allowed_fields = ['discovered', 'applied', 'skipped', 'failed', 'manual']
        if field in allowed_fields:
            query = f"UPDATE stats SET {field} = {field} + ? WHERE date = ?"
            cursor.execute(query, (increment, date))
            conn.commit()
