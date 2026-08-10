import asyncio
import json
import time
from loguru import logger
from core.config import get_config
from core.database import get_jobs, update_job, get_profile
from core.utils.ai_client import AIClient
from modules.ai_scorer.filters import is_job_suitable

SCORE_PROMPT = """Score how well this candidate matches this job.
Return ONLY a valid JSON object. No explanation, no markdown, no code fences.
{
  "score": 0,
  "matching_skills": [],
  "skill_gaps": [],
  "is_remote": true,
  "requires_sponsorship": false,
  "required_experience_years": 0,
  "recommendation": "apply",
  "reason": ""
}
Score 0-100: 90-100 perfect, 75-89 strong, 60-74 decent, below 60 skip.
recommendation must be exactly: "apply" | "review" | "skip"

FATAL KNOCKOUTS (Auto-Score: 0):
Immediately score 0 and set recommendation to "skip" if ANY of the following are true:
1. VISA/WORK AUTH: The job explicitly requires "US Citizen", "Green Card", "Clearance", or says "Legally authorized to work in [Country]" AND the candidate is in {candidate_location} and the job does not explicitly offer visa sponsorship. -> requires_sponsorship = true
2. FAKE REMOTE / HYBRID / GEO-BLOCKED: If the job says "Hybrid", "Onsite", or only lists a specific physical location (e.g. "Slovakia") without explicitly confirming it is 100% remote. OR if the title or description says "(USA Only)", "(UK Only)", or "US Remote". If ANY geographic restriction excludes {candidate_location}, -> is_remote = false
3. SENIORITY MISMATCH: If the job explicitly requires 5+ years, 6+ years, or 10+ years of experience, but the candidate only has a few years. You MUST strictly penalize jobs asking for 5+ years. -> required_experience_years > 3
4. HARD CERTIFICATIONS: The job requires a strict certification (e.g. CKA, CISSP) that the candidate lacks, and it is listed as "Required" not "Preferred".
5. IRRELEVANT SKILLS: If the core stack (e.g. Java/C# when candidate is Node.js) does not match, score 0. Do not hallucinate skill matches.

SCORING RULES (If no fatal knockouts exist):
- Extract explicit truth from the description. If it is 100% remote without geographic restrictions excluding {candidate_location}, set `is_remote: true`. Do not assume remote just because it is remote software development. If it specifies a physical location and no remote option, it is onsite.
- If it doesn't mention experience, set `required_experience_years: 0`.
- Score heavily on direct SKILL MATCH (languages, tools, cloud providers).

JOB TITLE: {job_title}
JOB LOCATION: {job_location}

CANDIDATE PROFILE:
{profile}

ADDITIONAL CONTEXT FROM CANDIDATE:
{additional_context}

JOB DESCRIPTION:
{description}
"""

POST_SCORE_PROMPT = """Rate how relevant this LinkedIn post is for this job seeker.
Return ONLY a valid JSON object. No explanation, no markdown, no code fences.
{
  "score": 0,
  "matching_skills": [],
  "skill_gaps": [],
  "recommendation": "apply",
  "reason": ""
}
Score 0-100: 90-100 perfect match, 75-89 strong, 60-74 maybe, below 60 not relevant.
recommendation must be exactly: "apply" | "review" | "skip"

CANDIDATE PROFILE:
{profile}

POST CONTENT:
{description}
"""


SCORE_SCHEMA = {
    "name": "job_score",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "score": {"type": "integer"},
            "matching_skills": {
                "type": "array",
                "items": {"type": "string"}
            },
            "skill_gaps": {
                "type": "array",
                "items": {"type": "string"}
            },
            "is_remote": {"type": "boolean"},
            "requires_sponsorship": {"type": "boolean"},
            "required_experience_years": {"type": "integer"},
            "recommendation": {
                "type": "string",
                "enum": ["apply", "review", "skip"]
            },
            "reason": {"type": "string"}
        },
        "required": ["score", "matching_skills", "skill_gaps", "is_remote", "requires_sponsorship", "required_experience_years", "recommendation", "reason"],
        "additionalProperties": False
    }
}

async def _score_job(ai: AIClient, profile_json: str, job: dict, candidate_location: str = "Pakistan", config: dict = None) -> dict | None:
    """Score a single job against the profile."""
    if config is None:
        config = {}
    description = job.get("description", "")
    if not description or len(description) < 20:
        return None

    is_post = job.get("platform") == "linkedin_posts"
    template = POST_SCORE_PROMPT if is_post else SCORE_PROMPT
    additional_context = config.get("additional_context", "")

    prompt = (template
        .replace("{profile}", profile_json)
        .replace("{additional_context}", additional_context)
        .replace("{description}", description[:3000])
        .replace("{candidate_location}", candidate_location)
        .replace("{job_title}", job.get("title", "Unknown"))
        .replace("{job_location}", job.get("location", "Unknown"))
    )

    result = await ai.ask_json(prompt, schema=SCORE_SCHEMA)
    return result


def score_jobs(min_description_len: int = 20, max_jobs: int = None) -> dict:
    """Score all discovered jobs against the user profile.
    
    Returns summary: {scored, skipped_no_desc, failed, by_status: {ready_to_apply: N, ...}}
    """
    config = get_config()
    profile = get_profile()

    if not profile:
        logger.error("No profile found. Run 'parse-resume' first.")
        return {"error": "no_profile"}

    # Build compact profile summary to save tokens
    skills = ", ".join(profile.get("skills", []))
    certs = ", ".join(profile.get("certifications", []))
    exp = profile.get("experience", [{}])[0] if profile.get("experience") else {}
    profile_summary = (
        f"Name: {profile.get('name', 'N/A')} | Location: {profile.get('location', 'N/A')}\n"
        f"Experience: {profile.get('total_years_experience', 0)} years — {exp.get('title', '')} @ {exp.get('company', '')}\n"
        f"Skills: {skills}\n"
        f"Certifications: {certs}"
    )

    jobs = get_jobs(status="discovered")

    if not jobs:
        logger.info("No discovered jobs to score")
        return {"scored": 0, "skipped_no_desc": 0, "failed": 0, "by_status": {}}

    logger.info(f"Scoring {len(jobs)} discovered jobs...")
    thresholds = config.get("scoring", {})
    auto_above = thresholds.get("auto_apply_above", 75)
    review_above = thresholds.get("review_above", 60)

    return asyncio.run(_score_all(config, profile_summary, jobs, auto_above, review_above, min_description_len, max_jobs))


async def _score_all(config, profile_json, jobs, auto_above, review_above, min_desc_len, max_jobs):
    ai = AIClient(config)
    stats = {"scored": 0, "skipped_no_desc": 0, "skipped_location": 0, "failed": 0, "by_status": {}}

    # Get candidate location from profile
    profile = get_profile()
    candidate_location = profile.get("location", "Pakistan") if profile else "Pakistan"

    for i, job in enumerate(jobs, 1):
        if max_jobs and stats["scored"] >= max_jobs:
            logger.info(f"Reached max_jobs limit ({max_jobs}). Stopping scoring.")
            break
            
        desc = job.get("description", "") or ""
        
        # Lazy load description if missing
        if len(desc) < min_desc_len and job.get("platform") == "linkedin":
            from modules.scrapers.linkedin_jobs import LinkedInJobs
            url = job.get("url", "")
            logger.info(f"  [{i}/{len(jobs)}] Fetching description for {job['title']} @ {job['company']}...")
            desc = LinkedInJobs.fetch_single_description(url, retry_delay=10)
            if len(desc) > min_desc_len:
                update_job(job["id"], description=desc)
                job["description"] = desc
            time.sleep(1)  # Throttle to avoid LinkedIn 429

        if len(desc) < min_desc_len:
            logger.debug(f"  [{i}/{len(jobs)}] {job['title']} @ {job['company']} — skipped (no description)")
            stats["skipped_no_desc"] += 1
            continue

        # Pre-filter: skip international onsite jobs without sponsorship before wasting AI tokens
        if not is_job_suitable(job.get("location", ""), job.get("title", ""), desc):
            logger.debug(f"  [{i}/{len(jobs)}] {job['title']} @ {job['company']} — skipped (international onsite, no sponsorship)")
            update_job(job["id"], status="skipped", match_score=0)
            stats["skipped_location"] += 1
            continue

        result = await _score_job(ai, profile_json, job, candidate_location, config)

        if result and result.get("error") == "ALL_QUOTAS_EXHAUSTED":
            logger.error("All AI quotas exhausted for today. Stopping scoring process.")
            break

        if not result or "score" not in result:
            logger.warning(f"  [{i}/{len(jobs)}] {job['title']} @ {job['company']} — AI scoring failed")
            stats["failed"] += 1
            continue

        score = int(result.get("score", 0))
        score = max(0, min(100, score))  # Clamp between 0-100 to prevent hallucinations
        matching = result.get("matching_skills", [])
        gaps = result.get("skill_gaps", [])
        is_remote = result.get("is_remote", False)
        requires_sponsorship = result.get("requires_sponsorship", False)
        req_exp_years = result.get("required_experience_years", 0)
        recommendation = result.get("recommendation", "skip")
        reason = result.get("reason", "")
        provider = result.get("ai_provider", "")

        # Determine status from score
        if score >= auto_above:
            status = "ready_to_apply"
        elif score >= review_above:
            status = "needs_review"
        else:
            status = "skipped"

        update_job(
            job["id"],
            match_score=score,
            matching_skills=matching,
            skill_gaps=gaps,
            is_remote=int(is_remote) if isinstance(is_remote, bool) else is_remote,
            requires_sponsorship=int(requires_sponsorship) if isinstance(requires_sponsorship, bool) else requires_sponsorship,
            required_experience_years=req_exp_years,
            status=status,
            ai_provider=provider,
        )

        stats["scored"] += 1
        stats["by_status"][status] = stats["by_status"].get(status, 0) + 1

        icon = "✅" if status == "ready_to_apply" else "🔍" if status == "needs_review" else "⏭️"
        logger.info(f"  [{i}/{len(jobs)}] {icon} {score}/100 — {job['title']} @ {job['company']} → {status}")
        if reason:
            logger.debug(f"    Reason: {reason}")

    return stats
