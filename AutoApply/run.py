"""
AutoApply CLI — Multi-Platform Job Search + Score + Export

Usage:
    python run.py parse-resume "path/to/cv.pdf"   Parse resume, save profile
    python run.py search-jobs                      Search ALL platforms
    python run.py search-jobs --platform linkedin  Search LinkedIn
    python run.py score                            Score all discovered jobs via AI
    python run.py export                           Export scored jobs to CSV
    python run.py all                              search-jobs -> score -> export
    python run.py status                           Show DB stats by platform/status

Platforms: linkedin
"""

import argparse
import sys
import json
import os
from loguru import logger
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# Configure loguru — clean terminal output
logger.remove()
logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | <level>{level: <8}</level> | {message}", level="INFO")
logger.add("logs/autoapply.log", rotation="1 MB", retention="7 days", level="DEBUG")


def cmd_parse_resume(args):
    from modules.resume_parser.parser import parse_resume
    profile = parse_resume(args.path)
    if profile:
        print("\n" + json.dumps(profile, indent=2))
    else:
        logger.error("Failed to parse resume")
        sys.exit(1)


def cmd_search_jobs(args):
    from core.config import get_config

    config = get_config()
    titles = config["search"]["titles"]
    regions = config["search"]["regions"]

    # --limit: restrict to N random title×region combos (for testing)
    limit = getattr(args, "limit", None)
    if limit:
        import random
        combos = [(t, r) for t in titles for r in regions]
        chosen = random.sample(combos, min(limit, len(combos)))
        titles = list(dict.fromkeys(t for t, r in chosen))   # unique, order preserved
        regions = list(dict.fromkeys(r for t, r in chosen))
        logger.info(f"--limit {limit}: using {len(titles)} title(s) x {len(regions)} region(s) = {len(titles)*len(regions)} combos")

    # Determine which platforms to run
    requested = getattr(args, "platform", None) or ["all"]

    platform_map = _get_platform_map()
    
    if "all" in requested:
        to_run = list(platform_map.keys())
    else:
        to_run = [p for p in requested if p in platform_map]
        unknown = [p for p in requested if p not in platform_map]
        if unknown:
            logger.warning(f"Unknown platforms (skipped): {unknown}")

    if not to_run:
        logger.error(f"No valid platforms. Available: {list(platform_map.keys())}")
        sys.exit(1)

    logger.info(f"Searching {len(to_run)} platform(s): {', '.join(to_run)}")
    total = 0
    for name in to_run:
        try:
            platform_cls = platform_map[name]()
            count = platform_cls.search(titles, regions, config)
            total += count
        except Exception as e:
            logger.error(f"Platform '{name}' failed: {e}")

    logger.info(f"Done — {total} new jobs saved across all platforms")
    return total


def _get_platform_map():
    """Lazy-load platform classes to avoid import errors in unused platforms."""
    mapping = {}
    try:
        from modules.scrapers.linkedin_jobs import LinkedInJobs
        mapping["linkedin"] = LinkedInJobs
    except ImportError as e:
        logger.debug(f"LinkedIn not available: {e}")
    return mapping



def cmd_score(args):
    from modules.ai_scorer.scorer import score_jobs
    max_jobs = getattr(args, "max_jobs", None)
    stats = score_jobs(max_jobs=max_jobs)

    if "error" in stats:
        logger.error(f"Scoring failed: {stats['error']}")
        sys.exit(1)

    logger.info(f"Scoring complete: {stats['scored']} scored, {stats['skipped_no_desc']} skipped (no desc), {stats.get('skipped_location', 0)} skipped (location), {stats['failed']} failed")
    if stats.get("by_status"):
        for status, n in stats["by_status"].items():
            logger.info(f"  {status}: {n}")


def cmd_export(args):
    from modules.exporter.export import export_jobs
    path = export_jobs(min_score=args.min_score, days=getattr(args, 'days', None))
    if path:
        print(f"\n-> Open in Excel: {path}")
    else:
        logger.info("Nothing to export")


def cmd_all(args):
    cmd_search_jobs(args)
    cmd_score(args)
    cmd_export(args)


def cmd_status(args):
    """Quick status check — shows job counts by status."""
    from core.database import get_jobs
    from core.database import get_profile

    all_jobs = get_jobs()
    profile = get_profile()

    if profile:
        logger.info(f"Profile: {profile.get('name', 'Unknown')} — {len(profile.get('skills', []))} skills")
    else:
        logger.warning("No profile found. Run: python run.py parse-resume <path>")

    if not all_jobs:
        logger.info("No jobs in database")
        return

    by_status = {}
    by_platform = {}
    for job in all_jobs:
        s = job.get("status", "unknown")
        p = job.get("platform", "unknown")
        by_status[s] = by_status.get(s, 0) + 1
        by_platform[p] = by_platform.get(p, 0) + 1

    logger.info(f"Total jobs: {len(all_jobs)}")
    for status, count in sorted(by_status.items()):
        logger.info(f"  {status}: {count}")
    logger.info("By platform:")
    for platform, count in sorted(by_platform.items()):
        logger.info(f"  {platform}: {count}")


def cmd_mark_applied(args):
    """Mark jobs as 'applied' by their URLs."""
    from core.database import mark_jobs_applied

    urls = args.urls
    if not urls:
        logger.error("No URLs provided")
        sys.exit(1)

    updated = mark_jobs_applied(urls)
    logger.info(f"Marked {updated} job(s) as applied")
    if updated < len(urls):
        logger.warning(f"{len(urls) - updated} URL(s) not found or already applied")


def cmd_import_applied(args):
    """Read a CSV file, find rows where 'Applied' column is yes/no, mark them in DB."""
    import csv
    from core.database import mark_jobs_applied, mark_jobs_skipped

    path = args.file
    if not os.path.isfile(path):
        logger.error(f"File not found: {path}")
        sys.exit(1)

    applied_urls = []
    skipped_urls = []
    
    with open(path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if "Applied" not in (reader.fieldnames or []):
            logger.error("CSV has no 'Applied' column")
            sys.exit(1)
        for row in reader:
            val = (row.get("Applied") or "").strip().lower()
            url = row.get("URL", "").strip()
            if not url:
                continue
                
            if val in ("yes", "y"):
                applied_urls.append(url)
            elif val in ("no", "n"):
                skipped_urls.append(url)

    if not applied_urls and not skipped_urls:
        logger.info("No jobs marked as applied or skipped in the CSV")
        return

    if applied_urls:
        updated_applied = mark_jobs_applied(applied_urls)
        logger.success(f"Imported {updated_applied} applied job(s)")
        
    if skipped_urls:
        updated_skipped = mark_jobs_skipped(skipped_urls)
        logger.info(f"Marked {updated_skipped} job(s) as skipped/useless")


def main():
    parser = argparse.ArgumentParser(
        description="AutoApply — LinkedIn Job Search + Score + Export",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    sub = parser.add_subparsers(dest="command", help="Command to run")

    # parse-resume
    p_resume = sub.add_parser("parse-resume", help="Parse resume PDF and save profile")
    p_resume.add_argument("path", help="Path to resume PDF file")
    p_resume.set_defaults(func=cmd_parse_resume)

    # search-jobs
    p_sj = sub.add_parser("search-jobs", help="Search jobs across platforms")
    p_sj.add_argument("--platform", nargs="+", default=["all"],
                       help="Platforms to search: linkedin (default: all)")
    p_sj.add_argument("--limit", type=int, default=None,
                       help="Limit to N random title×region combos (for testing). E.g. --limit 3")
    p_sj.set_defaults(func=cmd_search_jobs)


    # score
    p_sc = sub.add_parser("score", help="Score all discovered jobs via AI")
    p_sc.add_argument("--max-jobs", type=int, default=None, help="Maximum number of jobs to score (for testing)")
    p_sc.set_defaults(func=cmd_score)

    # export
    p_ex = sub.add_parser("export", help="Export scored jobs to CSV")
    p_ex.add_argument("--min-score", type=int, default=0, help="Minimum score to include (default: 0 = all scored)")
    p_ex.add_argument("--days", type=int, default=None, help="Only include jobs from last N days (1=24h, 3=3days, 7=week)")
    p_ex.set_defaults(func=cmd_export)

    # all
    p_all = sub.add_parser("all", help="search -> score -> export (full pipeline)")
    p_all.add_argument("--platform", nargs="+", default=["all"],
                        help="Platforms to search (default: all)")
    p_all.add_argument("--limit", type=int, default=None,
                        help="Limit to N random title×region combos (for testing)")
    p_all.add_argument("--max-jobs", type=int, default=None, help="Maximum number of jobs to score (for testing)")

    p_all.add_argument("--min-score", type=int, default=0, help="Minimum score for export")
    p_all.set_defaults(func=cmd_all)

    # status
    p_st = sub.add_parser("status", help="Show current DB status")
    p_st.set_defaults(func=cmd_status)

    # mark-applied
    p_ma = sub.add_parser("mark-applied", help="Mark jobs as applied by URL")
    p_ma.add_argument("urls", nargs="+", help="One or more job URLs to mark as applied")
    p_ma.set_defaults(func=cmd_mark_applied)

    # import-applied
    p_ia = sub.add_parser("import-applied", help="Import applied jobs from a CSV file")
    p_ia.add_argument("file", help="Path to CSV file with 'Applied' column filled in")
    p_ia.set_defaults(func=cmd_import_applied)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
