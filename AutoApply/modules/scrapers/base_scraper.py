from abc import ABC, abstractmethod
from loguru import logger
from core.database import save_job
import uuid
from datetime import datetime


# ─── Base platform class ────────────────────────────────────────────────────

class BasePlatform(ABC):
    """Base class for all job search platforms.
    
    To add a new platform, create a file in modules/scrapers/ and implement:
        - name: str property
        - search(titles, regions, config) -> int  (returns new jobs saved count)
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Platform identifier, e.g. 'linkedin'."""
        ...

    @abstractmethod
    def search(self, titles: list[str], regions: list[str], config: dict) -> int:
        """Run search across all title×region combos. Returns total new jobs saved."""
        ...

    def _save_jobs(self, jobs: list[dict]) -> int:
        """Save a batch of jobs to DB. Returns count of newly inserted jobs.
        
        Uses INSERT OR IGNORE so duplicates (by URL) are silently skipped.
        Tracks insertions via sqlite rowcount instead of querying the full table.
        """
        new_count = 0
        for job in jobs:
            if "id" not in job:
                job["id"] = str(uuid.uuid4())
            if "discovered_at" not in job:
                job["discovered_at"] = datetime.now().isoformat()
            if "status" not in job:
                job["status"] = "discovered"
            if "platform" not in job:
                job["platform"] = self.name
            inserted = save_job(job)
            if inserted:
                new_count += 1
        return new_count
