import os
import logging
import asyncio
import libsql_client
from core.config import TURSO_URL, TURSO_TOKEN, DEV_MODE

logger = logging.getLogger(__name__)

# In DEV_MODE, ALWAYS use local SQLite (even if TURSO_URL is set)
# This prevents DNS failures against unreachable cloud databases during local dev
if DEV_MODE:
    DB_URL = "file:data/shortsforge.db"
    DB_TOKEN = None
    logger.info("DEV_MODE: Using local SQLite database")
else:
    DB_URL = TURSO_URL or "file:data/shortsforge.db"
    DB_TOKEN = TURSO_TOKEN

class Database:
    def __init__(self):
        self.url = DB_URL
        self.token = DB_TOKEN
        self.client = None

    def _connect_sync(self):
        """Synchronous connection for internal use."""
        if self.client:
            return self.client
            
        # Ensure proper file URL format for absolute path
        if self.url.startswith("file:") and not self.url.startswith("file:///"):
            abs_path = os.path.abspath(self.url.replace("file:", ""))
            self.url = f"file:///{abs_path}"
        elif self.url.startswith("libsql://"):
            # Force HTTPS as WSS might fail with 505
            self.url = self.url.replace("libsql://", "https://")

        logger.info(f"Connecting to database at {self.url}...")
        # Use sync client to avoid event loop issues with libsql-client 0.3.0
        self.client = libsql_client.create_client_sync(self.url, auth_token=self.token)
        return self.client

    async def connect(self):
        """Asynchronously connect (runs sync connect in thread)."""
        return await asyncio.to_thread(self._connect_sync)

    def _close_sync(self):
        if self.client:
            try:
                self.client.close()
            except Exception as e:
                logger.debug(f"Database close suppressed error: {e}")
            finally:
                self.client = None

    async def close(self):
        """Closes the database connection."""
        await asyncio.to_thread(self._close_sync)

    def _execute_sync(self, sql: str, args: list = None):
        client = self._connect_sync()
        try:
            return client.execute(sql, args or [])
        except Exception as e:
            logger.debug(f"Database execute error: {e} | SQL: {sql}")
            raise

    async def execute(self, sql: str, args: list = None):
        """Executes a single SQL statement asynchronously."""
        return await asyncio.to_thread(self._execute_sync, sql, args)

    async def fetch_all(self, sql: str, args: list = None):
        """Executes SQL and returns all rows."""
        result = await self.execute(sql, args)
        return result.rows

    async def fetch_one(self, sql: str, args: list = None):
        """Executes SQL and returns the first row."""
        result = await self.execute(sql, args)
        if result.rows:
            return result.rows[0]
        return None

    async def init_schema(self):
        """Initializes the database schema."""
        # Enable foreign keys, WAL mode for concurrency, and busy timeout for SQLite
        if "file:" in self.url:
            await self.execute("PRAGMA foreign_keys = ON;")
            await self.execute("PRAGMA journal_mode = WAL;")
            await self.execute("PRAGMA busy_timeout = 5000;")

        schema_statements = [
            """
            CREATE TABLE IF NOT EXISTS workspaces (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                plan TEXT DEFAULT 'free',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                full_name TEXT,
                is_verified BOOLEAN DEFAULT FALSE,
                mfa_secret TEXT,
                mfa_enabled BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS workspace_members (
                workspace_id TEXT,
                user_id TEXT,
                role TEXT DEFAULT 'member',
                invited_by TEXT,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (workspace_id, user_id),
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS global_settings (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                global_gen_quota INTEGER DEFAULT 10,
                global_upload_quota INTEGER DEFAULT 5,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS channels (
                id TEXT PRIMARY KEY,
                workspace_id TEXT,
                name TEXT NOT NULL,
                youtube_id TEXT,
                niche TEXT,
                voice_config JSON,
                schedule JSON,
                is_active BOOLEAN DEFAULT TRUE,
                language_pair TEXT DEFAULT 'en-only',
                caption_style TEXT DEFAULT 'highlight',
                allow_internet_images BOOLEAN DEFAULT 1,
                video_format TEXT DEFAULT 'vertical',
                enable_heavy_shadows BOOLEAN DEFAULT 1,
                oauth_token TEXT,
                channel_gen_quota INTEGER DEFAULT 0,
                channel_upload_quota INTEGER DEFAULT 0,
                is_shorts_only BOOLEAN DEFAULT 0,
                visual_mode TEXT DEFAULT 'classic',
                dynamic_media_type TEXT DEFAULT 'image',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS story_series (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id TEXT,
                channel_id TEXT,
                topic TEXT,
                target_language TEXT DEFAULT 'en',
                protagonist_gender TEXT,
                status TEXT DEFAULT 'pending',
                assigned_quota INTEGER DEFAULT 0,
                global_hook TEXT,
                bg_image_path TEXT,
                base_description TEXT,
                youtube_playlist_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
                FOREIGN KEY (channel_id) REFERENCES channels(id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS story_parts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                series_id INTEGER,
                file_path TEXT,
                sequence_order INTEGER,
                status TEXT DEFAULT 'pending',
                chunk_progress INTEGER DEFAULT 0,
                total_chunks INTEGER DEFAULT 0,
                shorts_generated BOOLEAN DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (series_id) REFERENCES story_series(id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS videos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                series_id INTEGER,
                part_id INTEGER,
                video_path TEXT,
                youtube_url TEXT,
                thumbnail_path TEXT,
                title TEXT,
                is_short BOOLEAN DEFAULT 0,
                status TEXT DEFAULT 'pending',
                error_log TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                FOREIGN KEY (series_id) REFERENCES story_series(id),
                FOREIGN KEY (part_id) REFERENCES story_parts(id)
            );
            """,
            """
             CREATE TABLE IF NOT EXISTS trends (
                id TEXT PRIMARY KEY,
                source TEXT,
                topic TEXT,
                url TEXT,
                volume INT,
                scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS templates (
                id TEXT PRIMARY KEY,
                workspace_id TEXT,
                niche TEXT NOT NULL,
                template_name TEXT NOT NULL,
                script_structure JSON,
                visual_style JSON,
                voice_config JSON,
                caption_style JSON,
                is_active BOOLEAN DEFAULT TRUE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS auth_tokens (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                token_hash TEXT NOT NULL,
                token_type TEXT DEFAULT 'refresh',
                expires_at TIMESTAMP,
                is_used BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS topic_bank (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                workspace_id TEXT,
                channel_id TEXT,
                topic TEXT NOT NULL,
                angle TEXT,
                scheduled_date TEXT,
                status TEXT DEFAULT 'pending',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
                FOREIGN KEY (channel_id) REFERENCES channels(id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id INTEGER UNIQUE,
                views_48h INTEGER DEFAULT 0,
                watch_time_pct REAL DEFAULT 0,
                likes INTEGER DEFAULT 0,
                comments INTEGER DEFAULT 0,
                recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (video_id) REFERENCES videos(id)
            );
            """,
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version INTEGER PRIMARY KEY,
                description TEXT NOT NULL,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        ]

        try:
            for sql in schema_statements:
                 await self.execute(sql)
                 
            # Schema Migrations
            migrations = {
                1: [
                    "ALTER TABLE channels ADD COLUMN language_pair TEXT DEFAULT 'en-only'",
                    "ALTER TABLE channels ADD COLUMN caption_style TEXT DEFAULT 'highlight'"
                ],
                2: [
                    "ALTER TABLE channels ADD COLUMN image_search_style TEXT"
                ],
                3: [
                    "CREATE TABLE IF NOT EXISTS global_settings (id INTEGER PRIMARY KEY CHECK (id = 1), global_gen_quota INTEGER DEFAULT 10, global_upload_quota INTEGER DEFAULT 5, updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)",
                    "ALTER TABLE channels ADD COLUMN channel_gen_quota INTEGER DEFAULT 1",
                    "ALTER TABLE channels ADD COLUMN channel_upload_quota INTEGER DEFAULT 1"
                ],
                4: [
                    "ALTER TABLE videos ADD COLUMN title TEXT"
                ],
                5: [
                    "ALTER TABLE story_series ADD COLUMN base_description TEXT"
                ],
                6: [
                    "ALTER TABLE story_series ADD COLUMN youtube_playlist_id TEXT"
                ],
                7: [
                    "ALTER TABLE channels ADD COLUMN is_shorts_only BOOLEAN DEFAULT 0"
                ],
                8: [
                    "ALTER TABLE channels ADD COLUMN allow_internet_images BOOLEAN DEFAULT 1",
                    "ALTER TABLE channels ADD COLUMN video_format TEXT DEFAULT 'vertical'",
                    "ALTER TABLE channels ADD COLUMN enable_heavy_shadows BOOLEAN DEFAULT 1"
                ],
                9: [
                    "ALTER TABLE channels ADD COLUMN enable_dark_gradient_box BOOLEAN DEFAULT 1"
                ],
                10: [
                    "ALTER TABLE story_series ADD COLUMN target_language TEXT DEFAULT 'en'",
                    "ALTER TABLE story_series ADD COLUMN protagonist_gender TEXT DEFAULT NULL"
                ]
            }
            
            # Identify highest applied migration
            result = await self.fetch_one("SELECT MAX(version) FROM schema_migrations")
            current_version = result[0] if result and result[0] is not None else 0
            
            for target_version in sorted(migrations.keys()):
                if target_version > current_version:
                    logger.info(f"Applying schema migration v{target_version}...")
                    for statement in migrations[target_version]:
                        try:
                            await self.execute(statement)
                        except Exception as e:
                            # sqlite specifically errors when adding duplicate columns despite schema tracking
                            if "duplicate column name" in str(e).lower():
                                pass
                            else:
                                raise
                    await self.execute("INSERT INTO schema_migrations (version, description) VALUES (?, ?)", [target_version, f"Migration v{target_version}"])

            # Auto-seed global_settings
            try:
                await self.execute("INSERT OR IGNORE INTO global_settings (id, global_gen_quota, global_upload_quota) VALUES (1, 10, 5)")
            except Exception as e:
                logger.warning(f"Could not auto-seed global_settings: {e}")

            # Auto-seed workspace membership if the table is empty (fixes existing DBs from old seed)
            # Without this, auth.py can't look up workspace_id and all API calls fail.
            existing_members = await self.fetch_one("SELECT COUNT(*) FROM workspace_members")
            if not existing_members or existing_members[0] == 0:
                try:
                    await self.execute(
                        "INSERT OR IGNORE INTO workspace_members (workspace_id, user_id, role) VALUES ('default_workspace', 'user_1', 'owner')"
                    )
                    logger.info("Auto-seeded default workspace membership (user_1 -> default_workspace)")
                except Exception as e:
                    logger.warning(f"Could not auto-seed workspace membership: {e}")

            logger.info("Database schema initialized successfully.")
        except Exception as e:
            logger.critical(f"Failed to initialize schema: {e}")
            raise

# Singleton instance
db = Database()

if __name__ == "__main__":
    # Initialize schema when run as script
    logging.basicConfig(level=logging.INFO)
    asyncio.run(db.init_schema())
    asyncio.run(db.close())
    print("Database initialized and connection closed.")
