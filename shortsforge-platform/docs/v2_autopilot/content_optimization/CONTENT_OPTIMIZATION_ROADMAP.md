# Content Optimization Roadmap

> **Purpose:** This document records every insight, audit finding, and improvement idea discovered during the June 2026 deep-dive sessions. Items are meant to be worked on **one at a time** to avoid breaking changes.
>
> **Last Updated:** 2026-06-28

---

## Current State of the Pipeline

### How Content Is Currently Generated
1. **Scraper** (`scripts/scraper/main.py`) loops through channels in `accounts.json`
2. Picks a **random niche** from the channel's niche list (e.g., "Horror", "Company Failures")
3. Picks a **random source** (`ai` or `scp_wiki`) — Reddit source is dropped
4. AI source (`ai_generator.py`) tells the LLM: *"Write a dramatic story about [random niche]"*
5. Content passes through `filter.py` (Islamic compliance + quality gate)
6. SCP/Public Domain content goes through `polisher.py` (rewrites dry text into YouTube scripts)
7. Saved to staging → zipped → ingested into DB → video generated → uploaded

### How Videos Are Currently Built
1. **Voice:** Edge TTS (`en-US-ChristopherNeural`) — free Microsoft neural voice
2. **Visuals:** Either `gameplay.mp4` video loop OR a DuckDuckGo image searched with `"anime illustration digital art"` style bias
3. **Subtitles:** 4-word SRT chunks burned via FFmpeg (white text, `Fontsize=16`, dark outline)
4. **Thumbnails:** FFmpeg-generated — plain white text overlaid on a darkened background image
5. **Format:** 1080x1920 vertical Shorts + Long Videos from mathematical chunking
6. **Upload:** YouTube API with native scheduling, playlist auto-grouping, trailer-to-playlist linking

### Current Channel Config Problem
All 4 channels in `accounts.json` share:
- The exact same 10 niches
- The exact same 2 sources (`scp_wiki`, `ai`)
- The exact same TTS voice
- The exact same visual style

---

## Improvement Items (Priority Order)

### 🔴 Critical (Directly Blocks Monetization)

#### 1. ~~Trend-Driven Content Generation~~ ✅ COMPLETED
> [!NOTE]
> **Implementation Details & Documentation:**
> 🔗 [trends_implementation_plan.md](./trends_implementation_plan.md)

**Problem:** The AI generates random fictional stories nobody is searching for. Zero algorithmic reach.
**Solution:** Build a `trends.py` source plugin that fetches real trending topics (Google Trends, YouTube Autocomplete, Wikipedia Most Viewed) and feeds them to the AI generator so content matches actual search demand.
**Files to change:**
- `[NEW] scripts/scraper/sources/trends.py` — new BaseSource plugin
- `[MODIFY] scripts/scraper/main.py` — register new source in SOURCES dict
- `[MODIFY] scripts/scraper/configs/accounts.json` — add "trends" to channel source lists

**Open Decision (Path A vs Path B):**
- **Path A ("Faceless Explainer"):** Cover real news/drama. Must also update `media_picker.py` to search for real photographs instead of anime art. Drops atmospheric aesthetic.
- **Path B ("Niche Trends Only"):** Only ride trends within existing niches (trending True Crime cases, Space discoveries, etc.). Keeps current aesthetic. Ignores mainstream news.
- **Hybrid:** Path B by default, specific channels opt into Path A via config.

**Trend Sources to Consider:**

| Source | What It Gives | Difficulty | Free? | Best For | Amount of Data | Presorted By |
|---|---|---|---|---|---|---|
| Google Trends RSS | Top daily trending searches globally | Easy | Yes | Catching massive real-world events. | Up to 20 daily trends per country. | Search Volume Spike (Highest momentum first). |
| YouTube Autocomplete | What people type into YouTube search right now | Easy | Yes, no API key | Fine-tuning video titles and tags to match exactly what viewers want. | Exactly 10 keyword suggestions per seed query. | YouTube's Search Algorithm (Volume + Momentum). |
| Wikipedia Most Viewed | Top 10 articles today (great for lore/documentary) | Easy | Yes | Finding deep topics for educational/mystery scripts. | Top 1000 most-read articles daily. | Total Page Views (Highest to lowest). |
| TikTok Creative Center | Trending hashtags driving Shorts algorithm | Medium (scraping) | Yes but fragile | *Skipped (Too fragile)* | *Variable* | *Platform Algorithm* |
| X (Twitter) Trending | Fastest for internet drama/gaming news | Medium | No (paid API) | *Skipped (Paid API)* | *N/A* | *Real-time Volume* |

**Recommendation:** Start with Google Trends + YouTube Autocomplete + Wikipedia. All free, no API keys.

**Implemented Solution:** Created a modular `trends.py` scraper that fetches from Wikipedia (Most Viewed), Google Trends, and YouTube Autocomplete. Integrated it into `main.py` and configurable via `accounts.json` with fallback logic to ensure stable generation.

---

#### 2. Channel Identity Split
**Problem:** All 4 channels produce identical content. YouTube may flag as spam/duplicate.
**Solution:** Assign unique, focused niches per channel in `accounts.json`.
**Files to change:**
- `[MODIFY] scripts/scraper/configs/accounts.json` — unique niches per channel

**Example split:**
- Channel 1: True Crime + Unsolved Mysteries
- Channel 2: Science and Space + Company Failures  
- Channel 3: Horror + Sci-Fi Mystery
- Channel 4: History + Psychology

**Complexity:** Config-only change. Zero code changes needed.

---

### 🟡 Important (Affects Viewer Retention & Watch Time)

#### 3. ~~Voice Variety Per Channel~~ ✅ COMPLETED
> [!NOTE]
> **Implementation Details & Documentation:**
> 🔗 [voice_variety_plan.md](./voice_variety_plan.md)

**Problem:** All 4 channels use the exact same `en-US-ChristopherNeural` voice. Sounds like the same channel.
**Solution:** Assign a different voice from the existing `EDGE_VOICES` dict per channel. The voices are already defined in `voice_engine.py`:
```python
EDGE_VOICES = {
    "male_narrator": "en-US-ChristopherNeural",
    "female_narrator": "en-US-AriaNeural",
    "dramatic_male": "en-US-GuyNeural",
    "casual_male": "en-US-EricNeural",
    "british_male": "en-GB-RyanNeural"
}
```
**Files to change:**
- `[MODIFY] scripts/story_maker/voice_engine.py` — accept voice selection parameter
- `[MODIFY] scripts/story_maker/run_pipeline.py` — pass channel's voice preference
- Possibly add `voice_style` column to `channels` DB table, or use `accounts.json`

**Implemented Solution:** Modified `add_channel.py` to prompt for voice selection and store it as JSON in the `channels.voice_config` column. Updated `voice_engine.py` to support dynamic voice overrides and `run_pipeline.py` to seamlessly extract and pass the channel's preferred voice, defaulting gracefully to `male_narrator` if missing.

---

#### 4. ~~Background Music Layer~~ ✅ COMPLETED
> [!NOTE]
> **Implementation Details & Documentation:**
> 🔗 [background_music_plan.md](./background_music_plan.md)

**Problem:** Videos have dead silence behind the TTS voice. Feels unnatural and amateur. Every successful story channel uses subtle background music.
**Solution:** Add a royalty-free ambient track mixed at ~15% volume behind the TTS audio.
**Files to change:**
- `[MODIFY] scripts/story_maker/assembler.py` — add FFmpeg audio mixing for background track
- `[NEW] data/backgrounds/{channel}/music/` — store royalty-free ambient tracks per channel
- Add channel-level config for music selection

**Implemented Solution:** Added a robust audio pre-mixing layer. It reads a `music` toggle from the DB, dynamically fetches tracks from `data/backgrounds/{channel}/music/` (or `global_music`), calculates exact loops using FFmpeg concat to avoid `-stream_loop` bugs, and applies `amix` to duck the music behind the TTS voice.

---

#### 5. ~~Subtitle Styling Upgrade~~ ✅ COMPLETED
> [!NOTE]
> **Implementation Details & Documentation:**
> 🔗 [subtitle_styling_plan.md](./subtitle_styling_plan.md)

**Problem:** Current subtitles are tiny white text (`Fontsize=16`) with minimal outline. Viral Shorts use bold, large, word-by-word colored subtitles (CapCut style).
**Solution:** Increase font size, add colored keyword highlighting, improve positioning.
**Files to change:**
- `[MODIFY] scripts/story_maker/assembler.py` — update FFmpeg subtitle filter parameters
- Current style: `Fontsize=16,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=1.2`
- Target: Larger font, bolder outline, potentially ASS format for word-level color control

**Implemented Solution:** Engineered a dynamic Subtitle Failsafe system. In `add_channel.py`, users can select `classic` (safe default) or `capcut_yellow` (viral styling). 
*Correction Note:* We actively decided against using `.ass` formatting (as originally suggested) because Edge-TTS does not consistently support exact word boundaries, and FFmpeg `libass` rendering can be buggy on Windows. Instead, `voice_engine.py` was rewritten to generate word-by-word active yellow HTML highlights natively inside standard `.srt` files. `assembler.py` upgrades the global FFmpeg rendering to use a massive, bold font with drop shadows, achieving the exact CapCut effect with zero risk.

---

### 🟢 Nice-to-Have (Polish & CTR Optimization)

#### 6. ~~Thumbnail Quality Upgrade~~ ✅ COMPLETED
> [!NOTE]
> **Implementation Details & Documentation:**
> 🔗 [polish_and_ctr_plan.md](./polish_and_ctr_plan.md)

**Problem:** FFmpeg-generated thumbnails with plain white text on darkened images have low click-through rate compared to properly designed thumbnails.
**Solution:** Improve text rendering (larger, multi-line wrapping is already implemented), consider adding emoji or icons, improve contrast ratios.
**Files to change:**
- `[MODIFY] scripts/story_maker/thumbnail_maker.py` — enhance FFmpeg filter chain

**Implemented Solution:** Removed the cheap-looking semi-transparent black box (`box=1`) and replaced it with a thick, solid black border (`borderw=6`). Upgraded the main hook text color to CapCut Yellow (`#FFFF00`) and increased drop shadow depth to maximize CTR on mobile devices.

---

#### 7. ~~AI Prompt Optimization~~ ✅ COMPLETED
> [!NOTE]
> **Implementation Details & Documentation:**
> 🔗 [polish_and_ctr_plan.md](./polish_and_ctr_plan.md)

**Problem:** The current `ai_generator.py` system prompt is generic. The `GRAMMAR_PROMPT` in `script_editor.py` rewrites to "6th-grade reading level" which is good but could be more engaging.
**Solution:** A/B test different AI prompts to find which style gets the best audience retention. Track which prompt styles produce the highest watch-time videos.
**Files to change:**
- `[MODIFY] scripts/scraper/sources/ai_generator.py` — refine system prompts
- `[MODIFY] scripts/scraper/configs/niches.json` — refine per-niche ai_prompts
- `[MODIFY] scripts/story_maker/script_editor.py` — refine GRAMMAR_PROMPT, SHORTS_PROMPT

**Implemented Solution:** Injected proven psychological retention hacks directly into the system prompts (`ai_generator.py` and `SHORTS_PROMPT`). Forced the AI to maintain a "Curiosity Gap" by hiding the twist until the final paragraph, and mandated the use of visceral, sensory language over generic adjectives to maintain fast pacing.

---

#### 8. Background Image Strategy (Static vs Video)
**Problem:** Channels currently default to `gameplay.mp4` with DuckDuckGo anime art as fallback. No data on which performs better for viewer retention.
**Solution:** Compare channels using gameplay video backgrounds vs context-aware static images to determine which produces better audience retention metrics.
**Files affected:**
- `scripts/story_maker/media_picker.py` — the 5-tier fallback system already supports both
- `channels` DB table — `is_shorts_only` and `image_search_style` fields already exist

---

## How News Should Be Handled

> **Key Insight (from user feedback):** The previous AI's "Lore Pivot" idea was flawed. If someone searches for "OceanGate submarine" and we give them "The Physics of Water Pressure," that's bait-and-switch. Audience retention tanks to 0%.

**The Rule:** We must deliver exactly what people are searching for. Never pivot away from the actual trending topic.

**If covering news (Path A):**
- AI writes a factual, direct breakdown of the actual news event
- `media_picker.py` searches for real photographs of the event (not anime art)
- Example: CrowdStrike outage → AI writes about the CrowdStrike outage specifically

**If ignoring news (Path B):**
- Only hunt trends within storytelling niches (True Crime, Space, Horror, etc.)
- When "Black Hole discovered" trends, make a video about that specific Black Hole
- Content matches both the search intent AND the atmospheric pipeline aesthetic

---

## Dependency & Deployment Audit Results

### Verified Dependency Tree
The complete V2 dependency tree was programmatically mapped using AST analysis. The definitive list is stored in the artifact `v2_dependency_tree.md` and can be regenerated using `scratch/final_dep_check.py`.

### Deployment Script Fix Applied
- `scripts/delete_story.py` was missing from `build_v2_autopilot_deployment.py` INCLUDES — **now patched**
- `add_channel.py`, `core/channels.py`, `core/logging_config.py` correctly excluded (require local browser)

### Timeout/Sleep Audit Results
All active pauses in the V2 pipeline:
- `ai_generator.py:106` — `asyncio.sleep(1)` between AI story generations (rate limit protection)
- `script_editor.py:250` — `asyncio.sleep(2)` between AI grammar scenes (rate limit protection)
- `public_domain.py:24` — `httpx.AsyncClient(timeout=15.0)` for Gutenberg API
- `scp_wiki.py:21` — `httpx.AsyncClient(timeout=15.0)` for SCP Wiki scraping
- `media_picker.py:117,259,296` — `requests.get(timeout=10)` for image downloads
- `database.py:46` — `PRAGMA busy_timeout = 5000` for SQLite concurrency
- `core/security.py` — Contains a 45s exponential backoff in `call_with_retry()` but this function is **dead code** in V2 (never called)

### Server Status (As of June 26)
- Cron job fires at `0 3 * * *` (3:00 AM UTC daily)
- Confirmed actively running via `systemctl status cron`
- Pipeline was observed actively rendering videos with FFmpeg at time of check

---

## Reference Files
| File | Purpose |
|---|---|
| `docs/v2_autopilot/STORY_PIPELINE_GUIDE.md` | Exhaustive operational manual for the V2 system |
| `scripts/utils/build_v2_autopilot_deployment.py` | Deployment package builder |
| `scratch/final_dep_check.py` | Reusable dependency tree analyzer |
| `.state/AGENT_INSTRUCTIONS.md` | Agent rules (V2 boundaries documented here) |

---

## 🔮 Future Advanced Enhancements (Phase 2)
The following advanced optimizations were discussed and parked for future implementation to keep the current pipeline simple and focused:

- [x] **Multi-Model Fallback within Providers:** 
  - *Status:* Skipped. `ai_router.py` handles fallbacks well enough.
- [x] **Implement OpenRouter:** 
  - *Status:* Skipped for now.
- [x] **Address RPM Limits in Scraper:** 
  - *Status:* Handled! `ai_router.py` already possesses a native backoff strategy that successfully caught the 429 errors during testing.

---

## 🚀 AutoPilot V3 Expansion (Post-Roadmap)

> **Note:** The following item was not part of the original V2 optimization plan, but was added based on the critical need to break the YouTube/Facebook monetization algorithms and avoid "Reused Content" penalties.

#### 9. ~~Dynamic Scene-by-Scene Visuals (New Parallel Mode)~~ ✅ COMPLETED
> [!NOTE]
> **Implementation Details & Documentation:**
> 🔗 [dynamic_visuals_plan.md](./dynamic_visuals_plan.md)

**Problem:** Using a single static image or looping a 60-second `gameplay.mp4` video across 100 uploads is easily detected by YouTube/FB's automated "Low Effort Content" filters. It also leads to poor audience retention.
**Solution:** Build a parallel "Dynamic" visual mode. The AI breaks the script into 10-15 second scenes, fetches a unique DuckDuckGo image for *every single scene*, and uses FFmpeg to stitch them together with a Ken Burns effect.
**Files to change:**
- `[MODIFY] scripts/add_channel.py` — add `visual_mode` and `dynamic_media_type` to DB setup
- `[MODIFY] scripts/story_maker/script_editor.py` — add scene-splitting and keyword extraction
- `[MODIFY] scripts/story_maker/assembler.py` — create `build_dynamic_part()`
- `[MODIFY] scripts/story_maker/run_pipeline.py` — route to the new mode based on DB flag

**Implemented Solution:** Successfully added the parallel dynamic mode. Updated `core/database.py` and `shortsforge.db` schema. `script_editor.py` chunks scripts and uses LLM to extract DuckDuckGo image keywords. `assembler.py` generates scene audio individually, fetches the images, applies a subtle Ken Burns zoom via FFmpeg, stitches the scenes together, mixes the audio, and aggressively cleans up all temp assets to prevent storage bloat.

---

## 📡 Distribution & Measurement (Post-Launch)

> **Note:** The roadmap above covered the *production* side (making good videos). The items below cover the *distribution and measurement* side (getting those videos seen and learning what works). These were identified during the final audit and should be tackled after the initial production launch.

#### 10. YouTube AI Content Disclosure
**Problem:** Since 2024, YouTube mandates creators disclose AI-generated content. Channels that don't disclose risk monetization application rejection when a human reviewer watches the videos.
**Priority:** Not urgent for launch, but **must be done before applying for the YouTube Partner Program** (before hitting 1,000 subs).
**Files to change:**
- `[MODIFY] scripts/story_maker/yt_uploader.py` (or equivalent) — set the AI disclosure flag in the YouTube API upload request

---

#### 11. Upload Volume & Scheduling Optimization
**Problem:** New channels need algorithmic traction. Shorts channels that break through post 3-5 shorts per day, not 1. Upload timing also matters.
**Current state:** Cron runs at `0 3 * * *` (3 AM UTC). Scheduling exists but volume may be low.
**Action items:**
- Bump `channel_gen_quota` to produce 3-5 shorts per channel per day
- Schedule uploads to publish around **22:00 - 02:00 UTC** (6-10 PM US Eastern / 3-7 AM PKT) to hit US peak hours
- No audience data needed yet — default to US timezone, adjust later based on analytics

---

#### 12. Analytics Feedback Loop
**Problem:** Currently flying blind. No way to know which topics retain viewers, which thumbnails get clicks, or at what second viewers drop off. Without data, you can't iterate.
**Solution:** Build a script that pulls YouTube Analytics API data and logs retention/CTR per video. Even a simple CSV dump would be transformative.
**Priority:** After first batch of videos has been live for 1-2 weeks (need data to accumulate).
**Files to change:**
- `[NEW] scripts/analytics/yt_analytics.py` — pull retention, CTR, and watch time data per video

