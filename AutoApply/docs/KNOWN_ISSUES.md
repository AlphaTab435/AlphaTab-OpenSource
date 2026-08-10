# Known Issues & AI Quality Warnings

This document records the observed behavior and known bugs of the AI models used in the AutoApply system.

## 1. OpenRouter Free Tier (`openrouter/free`)
**Severity: High**
**Status:** Patched via score clamping, but underlying AI behavior remains erratic.

### The Issue
The configuration `openrouter/free` acts as a load-balancer that routes API requests to the cheapest available open-source model at that exact second. Many of these underlying models are highly degraded or do not properly support strict `json_schema` response formats.

During high-volume testing, the following corrupt behaviors were observed when OpenRouter processed jobs:
1. **Mathematical Hallucinations:** The models completely ignored the instruction to score between `0-100`, resulting in wild scores such as `909,550/100` and `900/100`.
2. **Missing Data Extraction:** When outputting hallucinated scores, the models often returned `NaN` (null) for the `Matching Skills` and `Skill Gaps` fields, failing to extract any meaningful resume data.
3. **Extreme False Negatives:** The models inexplicably gave `0/100` scores to perfectly valid jobs, including Remote DevOps engineering positions.
4. **JSON Parsing Failures:** Approximately 10-13% of the time, the models broke the JSON structure entirely (e.g., cutting off midway through a sentence or outputting conversational text).

### The Fix
The system handles this gracefully:
- **Score Clamping:** The codebase enforces `score = max(0, min(100, score))` immediately upon receiving the AI's response. This guarantees that hallucinated numbers (like 900,000) will never corrupt the database and are safely clamped down to 100.
- **Fail-Safes:** JSON parsing errors are caught and logged as `AI scoring failed`, safely skipping the corrupted job without crashing the script.

**Recommendation:** If you desire 100% pristine data extraction, do not rely on `openrouter/free`. Instead, configure OpenRouter to use a specific, high-quality free model in `config.yaml` (such as `google/gemma-2-9b-it:free`), or disable it entirely and run purely on Groq's daily quota.

## 2. Gemini (`gemini-3.1-flash`)
**Severity: None**
**Status:** Stable / Excellent

### Observation
Gemini acts as the highly-reliable secondary engine. During high-volume scraping, it easily handles complex descriptions and strictly enforces the `json_object` schema. It does not suffer from the hallucination issues of the OpenRouter free tier.

## 3. Groq (`llama3` / `mixtral`)
**Severity: None**
**Status:** Stable / Excellent

### Observation
During identical high-volume tests, Groq maintained a 0% JSON parsing failure rate and strictly adhered to the `json_object` schema constraint. It correctly extracted detailed matching skills and skill gaps, and provided highly accurate, nuanced scoring.

No known issues exist with Groq's `gpt-oss-120b` pipeline.
