import json
import os
from datetime import datetime, timedelta
from loguru import logger
import pandas as pd
from core.database import get_jobs
from modules.ai_scorer.filters import is_job_suitable


def export_jobs(
    min_score: int = 0,
    statuses: list[str] | None = None,
    output_dir: str = "data",
    days: int | None = None,
) -> str | None:
    """Export jobs from DB to a timestamped CSV file.
    
    Args:
        min_score: Minimum match_score to include (0 = all scored jobs)
        statuses: Filter by these statuses. None = all non-discovered.
        output_dir: Directory for the CSV file.
        days: Only include jobs discovered in the last N days. None = all.
    
    Returns:
        Path to the created CSV file, or None if no jobs.
    """
    all_jobs = get_jobs()

    # Time cutoff
    cutoff = None
    if days is not None:
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        logger.info(f"Filtering to jobs discovered in last {days} day(s)")

    # Filter
    jobs = []
    for job in all_jobs:
        if job.get("status") == "applied":
            continue  # skip already-applied jobs
        if statuses and job.get("status") not in statuses:
            continue
        if not statuses and job.get("status") == "discovered":
            continue  # skip unscored by default
        if job.get("match_score", 0) < min_score:
            continue
        if cutoff and (job.get("discovered_at", "") < cutoff):
            continue
        jobs.append(job)

    if not jobs:
        logger.info("No jobs to export")
        return None

    # Prepare rows for CSV
    rows = []
    for job in jobs:
        # Parse JSON fields
        matching = job.get("matching_skills", "")
        if isinstance(matching, str) and matching.startswith("["):
            matching = ", ".join(json.loads(matching))
        
        gaps = job.get("skill_gaps", "")
        if isinstance(gaps, str) and gaps.startswith("["):
            gaps = ", ".join(json.loads(gaps))

        rows.append({
            "Score": job.get("match_score", 0),
            "Status": job.get("status", ""),
            "Title": job.get("title", ""),
            "Company": job.get("company", ""),
            "Location": job.get("location", ""),
            "Region": job.get("region", ""),
            "Is Remote": bool(job.get("is_remote", False)),
            "Req Sponsorship": bool(job.get("requires_sponsorship", False)),
            "Req Exp Years": job.get("required_experience_years", ""),
            "Platform": job.get("platform", ""),
            "AI Provider": job.get("ai_provider", ""),
            "Matching Skills": matching,
            "Skill Gaps": gaps,
            "URL": job.get("url", ""),
            "Easy Apply": "Yes" if job.get("easy_apply") else "",
            "Date Posted": job.get("date_posted", ""),
            "Discovered": job.get("discovered_at", ""),
            "Applied": "",
        })

    # Sort globally by Score (highest first)
    rows.sort(key=lambda x: -x["Score"])

    df = pd.DataFrame(rows)
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    filename = f"jobs_export_{timestamp}.xlsx"
    filepath = os.path.join(output_dir, filename)
    df.to_excel(filepath, index=False, engine="openpyxl")

    logger.success(f"Exported {len(rows)} jobs to {filepath}")
    return filepath
