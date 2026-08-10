# Changelog

All notable changes to this project will be documented in this file.

## [1.3.0] - 2026-08-10

### Added
- **Lazy Fetching Architecture**: The Scraper now only fetches titles and URLs. The heavy job descriptions are fetched on-demand by the AI scorer, speeding up initial scraping by 95%.
- **Gemini Fallback**: Added Google Gemini as a secondary fallback layer between Groq and OpenRouter.
- **Strict Deduplication**: Added `is_duplicate_job` checks to prevent the database from filling with duplicate postings from the same company.
- **Quota Exhaustion Safety**: The pipeline now gracefully halts and saves unscored jobs if all AI APIs throw `ALL_QUOTAS_EXHAUSTED`.
- **Test Mode CLI Flags**: Added `--limit 1` (limits scraping regions) and `--max-jobs 1` (limits AI scoring) for fast pipeline testing without burning quota.
- **Excel Export**: Exporter now outputs `.xlsx` files with proper data formatting instead of `.csv`.

### Changed
- **Scoring Prompt Hardened**: Introduced strict "Fatal Knockouts" to instantly score `0/100` for jobs demanding 5+ years experience, fake remote, or requiring US/EU Visa sponsorship.

## [1.2.0] - 2026-07-02

### Added
- **Structured Outputs**: Implemented strict JSON Schema (`response_format: {"type": "json_schema"}`) to guarantee perfect parsing and eliminate hallucinated conversational output.
- **AI Provider Tracking**: The system now tracks exactly which API (Groq vs OpenRouter) scored a job, saving the provider name to the database and exposing it as a new "AI Provider" column in the exported CSV.
- **Score Clamping**: Built-in protection that clamps all AI scores between 0 and 100 to prevent database corruption from wildly hallucinated scores.
- **Documentation**: Added `docs/KNOWN_ISSUES.md` to document the specific flaws and hallucination patterns of `openrouter/free`.

### Changed
- **Groq Model Migration**: Switched the primary AI scoring engine from the deprecated LLaMA 3.3 to `openai/gpt-oss-120b` for significantly higher accuracy and stricter grading.
- **API Setup Docs**: Updated `docs/API_SETUP.md` with warnings about OpenRouter's free tier quality.

## [1.1.0] - 2026-06-21


### Added
- **AI Resume Parser**: Added `python run.py parse-resume` to extract structured profile data from PDFs, saving thousands of AI tokens during the scoring phase.
- **Auto-Routing AI Fallback**: Implemented seamless API failover. If Groq hits a rate limit or 503 error, the system automatically falls back to OpenRouter.
- **Intelligent Model Selection**: Configured OpenRouter to use `openrouter/free` to automatically route requests to the fastest, most capable free text model available, bypassing image/video models.
- **Detailed Terminal Logging**: Added `loguru` timestamps to all console outputs and added explicit "Resuming search..." messages after rate-limit pauses.
- **Project Documentation**: Added comprehensive `docs/SYSTEM_DESIGN.md` and `docs/API_SETUP.md` guides.
- **CSV Application Tracking**: Added support for marking jobs as "no" or "useless" in the exported CSV. Running `python run.py import-applied` now marks them as "skipped" permanently.

### Changed
- **Architecture Refactor**: Reorganized the codebase from a flat structure into modular `core/` and `modules/` directories for better maintainability.
- **Config Template**: Updated `DEFAULT_CONFIG` regions to replace bugged "Worldwide" search with high-value explicit countries (Australia, UAE, Saudi Arabia).
- **Security Improvements**: Migrated from hardcoded API keys to a secure `.env` file implementation using `python-dotenv`.
- **Git Tracking**: Updated `.gitignore` to securely ignore `data/jobs.db`, `data/config.yaml`, personal PDFs, and exported CSVs.

### Fixed
- **JobSpy Worldwide Bug**: Added a strict guard in `linkedin_jobs.py` to intercept and skip the "Worldwide" region search, preventing a known JobSpy crash caused by invalid country strings (e.g., 'benin').
- **JSON Parsing Resilience**: Added error catching for when AI models return safety warnings or malformed JSON, preventing the scoring loop from crashing.
