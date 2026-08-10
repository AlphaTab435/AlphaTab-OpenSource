# System Design & Architecture

This document explains the internal architecture of the Automated AI Job Assistant.

---

## The 5-Step Pipeline (Lazy Loading Architecture)

Here is exactly how the pipeline flows and where it uses hardcoded logic versus artificial intelligence:

#### Step 1: Setup & Resume Parsing (Logic + AI)
*   **What it does:** The program looks at `data/config.yaml` for your preferences and parses your PDF resume.
*   **Logic vs AI:** The parser uses AI. It reads your PDF and extracts your skills, experience, and certifications into a highly-optimized JSON "cheat sheet" to save thousands of tokens during scoring.

#### Step 2: The Fast Scraper (Logic)
*   **What it does:** It runs a lightning-fast scan on LinkedIn to find job Titles, Companies, and Links. Crucially, it **does not** download the heavy job descriptions yet (this is our Lazy Loading architecture).
*   **Logic vs AI:** 100% Logic. It uses `jobspy`. It checks the database to ensure strict **deduplication**—if you've already discovered a job (same Title + Company), it ignores it so your database stays clean.

#### Step 3: The Pre-Filter (Logic)
*   **What it does:** A basic logic pass to check if international onsite jobs can be instantly skipped without burning AI quota.
*   **Logic vs AI:** 100% Logic.

#### Step 4: The Scoring Engine & Lazy Fetcher (AI)
*   **What it does:** This is the brain. For each job in the queue, it reaches out to LinkedIn to grab the full description *on-demand*, with throttle delays to prevent getting banned. It then feeds the job and your resume to the AI. The AI acts as a strict recruiter, applying **Fatal Knockouts** (e.g. Visa requirements, Fake Remote, Seniority mismatches).
*   **Logic vs AI:** **100% AI**. If the AI is happy, it gives a score from 0 to 100. If the AI hits an API quota limit, it immediately pauses the pipeline so no jobs are wasted.

#### Step 5: The Export (Logic)
*   **What it does:** Generates a clean Excel `.xlsx` file containing the Job Title, Company, Match Score, AI Reason, and a direct link to apply.
*   **Logic vs AI:** 100% Logic.

---

## Fault Tolerance & Fallbacks

The system is highly resilient against API failures, rate limits, and internet drops.

### The 3-Tier API Fallback System
We utilize a cascading fallback system to guarantee uptime and save money:
1. **Groq (Primary):** Blazing fast and free, but strict rate limits.
2. **Gemini (Secondary):** Used when Groq runs out of tokens. Extremely capable, but has its own daily limits.
3. **OpenRouter (Backup):** Used as a final safety net utilizing their free LLM routing tier.

### What happens if ALL APIs exhaust their quotas?
If you hit the hard limits for Groq, Gemini, and OpenRouter in a single day:
1. The script receives an `ALL_QUOTAS_EXHAUSTED` signal.
2. The Scoring Engine safely powers down and stops processing instantly.
3. **CRITICAL:** Your unscored jobs remain perfectly safe in the database with the `"discovered"` status.
4. Tomorrow, when your API quotas reset, you simply run `python run.py score` and it will resume scoring exactly where it left off, eating through your backlog of scraped jobs!

### What if LinkedIn blocks the Scraper?
If LinkedIn issues an HTTP 429 (Too Many Requests), the scraper does not crash. It catches the error, automatically sleeps for 10 minutes to cool down the IP address, and then safely resumes scraping the remaining regions.
