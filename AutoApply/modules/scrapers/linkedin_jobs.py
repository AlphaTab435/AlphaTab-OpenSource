import time
import uuid
from datetime import datetime
from loguru import logger
from jobspy import scrape_jobs
from modules.scrapers.base_scraper import BasePlatform
from modules.ai_scorer.filters import is_location_blocked
from core.database import get_jobs, update_job, is_duplicate_job

# Maps jobspy DataFrame columns → our DB schema
JOBSPY_FIELD_MAP = {
    "title":       "title",
    "company":     "company",
    "location":    "location",
    "job_url":     "url",
    "description": "description",
    "date_posted": "date_posted",
}


class LinkedInJobs(BasePlatform):
    """LinkedIn job search via python-jobspy. No login required.
    
    Strategy: Lazy Fetching approach.
    Pass 1: Fetch listings WITHOUT descriptions (fast, ~1s per query).
    Descriptions are fetched on-demand by the AI scorer.
    """

    @property
    def name(self) -> str:
        return "linkedin"

    def search(self, titles: list[str], regions: list[str], config: dict) -> int:
        delay = config["search"].get("jobspy_linkedin_delay", 600)
        hours_old = self._get_hours_old(config)
        results_wanted = config["search"].get("results_per_query", 50)

        # Pass 1: Fast listing scan (no descriptions)
        logger.info(f"Pass 1 — Fast scan: {len(titles)} titles × {len(regions)} regions")
        total_new = 0
        for title in titles:
            for region in regions:
                count = self._search_single(title, region, hours_old, delay, results_wanted, fetch_desc=False)
                total_new += count

        if total_new == 0:
            logger.info("No new jobs found")
            return 0

        logger.info(f"LinkedIn Jobs total: {total_new} new jobs saved")
        return total_new

    def _search_single(self, title: str, region: str, hours_old: int, retry_delay: int, results_wanted: int = 50, fetch_desc: bool = False) -> int:
        """Search one title×region combo with 429 retry."""
        if region.strip().lower() == "worldwide":
            logger.warning(f"  Skipping '{region}' for LinkedIn due to a known JobSpy bug with global country lists. Please use explicit countries.")
            return 0
            
        logger.info(f"  Searching: '{title}' in '{region}'")
        try:
            df = self._fetch(title, region, hours_old, fetch_desc, results_wanted)
            return self._process_results(df, region, title)
        except Exception as e:
            if "429" in str(e) or "rate" in str(e).lower():
                logger.warning(f"  LinkedIn 429 — waiting {retry_delay}s")
                time.sleep(retry_delay)
                logger.info("  Resuming search...")
                try:
                    df = self._fetch(title, region, hours_old, fetch_desc, results_wanted)
                    return self._process_results(df, region, title)
                except Exception as e2:
                    logger.error(f"  LinkedIn retry failed: {e2}")
                    return 0
            logger.error(f"  LinkedIn search failed: {e}")
            return 0

    def _fetch(self, title: str, region: str, hours_old: int, fetch_desc: bool, results_wanted: int = 50):
        """Call jobspy scrape_jobs for LinkedIn."""
        df = scrape_jobs(
            site_name=["linkedin"],
            search_term=title,
            location=region,
            results_wanted=results_wanted,
            hours_old=hours_old,
            linkedin_fetch_description=fetch_desc,
            verbose=0,
        )
        return df

    @staticmethod
    def fetch_single_description(url: str, retry_delay: int = 10) -> str:
        """Fetch description for a single LinkedIn job URL."""
        import requests
        from bs4 import BeautifulSoup
        import re

        if not url:
            return ""

        match = re.search(r'/jobs/view/(\d+)', url)
        if not match:
            return ""
        job_id = match.group(1)

        session = requests.Session()
        session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        })

        try:
            resp = session.get(f"https://www.linkedin.com/jobs/view/{job_id}", timeout=10)

            if resp.status_code == 429:
                logger.warning(f"  LinkedIn 429 during description fetch — waiting {retry_delay}s")
                time.sleep(retry_delay)
                resp = session.get(f"https://www.linkedin.com/jobs/view/{job_id}", timeout=10)

            if resp.status_code != 200 or "linkedin.com/signup" in resp.url:
                return ""

            soup = BeautifulSoup(resp.text, "html.parser")
            div_content = soup.find("div", class_=lambda x: x and "show-more-less-html__markup" in x)

            if div_content:
                description = div_content.get_text(separator="\n", strip=True)
                if len(description) > 50:
                    return description
        except Exception as e:
            if "429" in str(e) or "rate" in str(e).lower():
                logger.warning(f"  429 during description fetch — waiting {retry_delay}s")
                time.sleep(retry_delay)
        return ""

    def _process_results(self, df, region: str, search_title: str = "") -> int:
        """Convert DataFrame rows to job dicts and save to DB."""
        if df is None or df.empty:
            return 0

        jobs = []
        for _, row in df.iterrows():
            job = {
                "id": str(uuid.uuid4()),
                "region": region,
                "search_query": search_title,
                "discovered_at": datetime.now().isoformat(),
                "status": "discovered",
            }

            for jobspy_col, our_col in JOBSPY_FIELD_MAP.items():
                val = row.get(jobspy_col)
                if val is not None and str(val) != "nan":
                    if isinstance(val, bool):
                        job[our_col] = int(val)
                    else:
                        job[our_col] = str(val)

            # Ensure required fields exist
            if not job.get("url") or not job.get("title") or not job.get("company"):
                continue

            # Filter out onsite jobs in countries where user can't work
            if is_location_blocked(job.get("location", "")):
                continue

            # Strict Deduplication by Title + Company
            if is_duplicate_job(job.get("title"), job.get("company")):
                continue

            job["platform"] = "linkedin"
            jobs.append(job)

        new_count = self._save_jobs(jobs)
        if new_count > 0:
            logger.info(f"    {len(df)} found, {new_count} new")
        return new_count

    def _get_hours_old(self, config: dict) -> int:
        """Convert config time_filters to hours."""
        filters = config["search"].get("time_filters", ["24h"])
        for f in filters:
            if f == "week":
                return 168
            if f == "24h":
                return 24
        return 72  # default 3 days
