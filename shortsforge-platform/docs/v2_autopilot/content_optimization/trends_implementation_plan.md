# Technical Specification: `trends.py` (V2 Architecture)

This document is the exhaustive technical blueprint for `trends.py`. It maps every edge case, state machine logic, and data flow to ensure perfectly seamless integration with `main.py` while introducing an advanced, globally-shared stateful caching system.

---

## 1. Core Paradigm Shift & Cache Lifecycle

`scp_wiki.py` and `ai_generator.py` are **stateless**. `trends.py` relies on **static daily data**. Therefore, `trends.py` must be a **stateful, caching engine**. 

**Cache Persistence:** The `self._google_trends` and `self._wiki_trends` caches exist in RAM. Because `main.py` instantiates `TrendsSource` globally at startup, this cache persists across **ALL channels** for the entire duration of the script run. It is completely destroyed when the terminal/script exits, guaranteeing fresh data the next day.

---

## 2. Configuration & Quality-First Defaults

To preserve `main.py`'s random weighting, `accounts.json` contains a single `"trends"` entry. Internal controls are nested in `trends_config`.

```json
"sources": ["scp_wiki", "ai", "trends"],
"trends_config": {
    "providers": ["wiki", "google", "yt"], 
    "selection_mode": "random",  // OR "sequential" (waterfall)
    "yt_seed_providers": ["google", "wiki"], 
    "ignore_niches": false 
}
```

**Quality-First Defaults:** If a channel omits `trends_config` from their config, `trends.py` will fall back to the following defaults to absolutely guarantee the highest quality, most viral output without failing:
*   `providers: ["google", "yt", "wiki"]` (Google yields immediate pop-culture virality. YT yields active search traffic virality. Wiki provides the massive safety net of deep-dive evergreen content).
*   `selection_mode: "sequential"` (The Waterfall ensures if Google is empty, it safely catches via YT/Wiki, guaranteeing a high-quality story).
*   `yt_seed_providers: ["google", "wiki"]` (Ensures YT pulls from real-world trending topics rather than generic raw niches).
*   `ignore_niches: false` (Ensures the story is strictly tailored to the channel's target audience).

---

## 3. State Management & Cache Structure (The Single Source of Truth)

To solve multiple-update synchronization bugs, we use a single flat list for each provider. 

```python
class TrendsSource(BaseSource):
    def __init__(self):
        # Format: [{"title": "Emily Blunt", "category": "uncategorized", "used": False}]
        self._google_trends = [] 
        
        # Format: [{"title": "The_Black_Death", "category": None, "used": False, "views": 150000}]
        self._wiki_trends = [] 
        self._wiki_chunk_offset = 0 
```

---

## 4. The Execution Flow & Internal Fallback (Restored)

When `main.py` calls `trends.fetch(niche_name="Horror", count=1)`:

**Step 1: Configuration Resolution (Local to `trends.py`)**
- If `"ignore_niches": true` is set in the config, `trends.py` internally overrides `niche_name` to `"ANY"`. This happens strictly locally inside `trends.py` so `main.py` remains completely unaware and untouched.

**Step 2: Sub-Provider Execution (`providers` Array)**
- **Single Provider:** If `providers: ["wiki"]`, the script only attempts Wiki. If it fails, it instantly returns `[]` to `main.py`.
- **Multiple Providers (Random):** If `["wiki", "google"]` and `selection_mode: "random"`, it picks one randomly. If it fails, it returns `[]`.
- **Multiple Providers (Sequential Waterfall):** If `["wiki", "google", "yt"]` and `selection_mode: "sequential"`, it acts as a Waterfall. It tries Wiki. If Wiki yields 0 matches, it falls back to Google. If Google yields 0, it falls back to YT. It only returns `[]` to `main.py` if ALL providers in the array fail.

---

## 5. DB Tracking (The Consistent `source_id` Prefixing)

When `trends.py` returns a story to `main.py`, it uses a strictly consistent `trends_[provider]_` naming convention so the database (`scraper.db`) can track origins properly:
*   Google Trends: `source_id = "trends_google_[Title]"`
*   Wiki Trends: `source_id = "trends_wiki_[Title]"`
*   YT Autocomplete: `source_id = "trends_yt_[Phrase]"`

---

## 6. Sub-Provider Mechanics (The Peek/Fetch Decoupling)

**Crucial Architecture Rule:** To prevent YouTube from accidentally generating Wikipedia stories when it just wants to borrow a seed, the API fetching is strictly decoupled into `_peek` methods (which only download/categorize lists) and `_fetch` methods (which hit the downstream APIs and generate final text).

### A. Google Trends (`_fetch_google`)
1. **The Peek (`_peek_google_seed`):** 
   - **API Call:** If `self._google_trends` is empty, download Top 20 from US RSS Feed.
   - **AI Bulk Filter:** Read ALL niches from `niches.json`. Pass the 20 titles + ALL niches to the AI. Assign each title to exactly ONE niche (or `"uncategorized"`). Update the `category` string for all 20 items in-place.
   - **Retrieval (`ignore_niches` Support):** Iterate through the list. If `ignore_niches: false`, find the first item where `category == niche_name` AND `used == False`. If `ignore_niches: true`, ignore the category and find the first unused item.
2. **The Fetch (`_fetch_google`):**
   - Calls `_peek_google_seed()` to get the title. Sets `used = True`.
   - Runs `check_exists("trends_google_[Title]")` DB check. If duplicate, loops back to peek.
   - **Text Generation:** Uses the Centralized AI Wrapper (`call_llm`) to generate a full script based on the trending Title. Returns the dictionary to `main.py`.

### B. Wikipedia (`_fetch_wiki`) with Advanced Pagination
1. **The Peek (`_peek_wiki_seed`):** Loops until a valid title is found or exhausted.
   - **Initialization:** If `self._wiki_trends` is empty, download Top 1000 items. Set all categories to `None`.
   - **Retrieval Check:** Scan `self._wiki_trends` for `used == False` (and `category == niche_name` if `ignore_niches: false`). *(Fails on first pass).*
   - **Pagination:** Slice the next chunk: `chunk = self._wiki_trends[offset : offset + 100]`. Increment offset.
   - **AI Bulk Filter:** Pass the 100 titles to the AI.
   - **Index Mapping (Python References):** Iterate over `chunk` and assign `"category"`. Because `chunk` is a shallow copy, the `self._wiki_trends` array natively updates in-place.
   - **Recursive Check:** Loop back to Retrieval Check. Returns the found title.
2. **The Fetch (`_fetch_wiki`):**
   - Calls `_peek_wiki_seed()` to get the title. Sets `used = True`.
   - Runs `check_exists("trends_wiki_[Title]")`. If duplicate, loops back to peek.
   - **Lazy Text Fetch:** Calls the Wikipedia Summary API to download the raw article text.
   - **Internal AI Rewrite (Mandatory):** Because `main.py` only polishes legacy providers, `trends.py` MUST use `call_llm` to rewrite the raw Wikipedia text into an engaging script *before* handing it back to `main.py`. 

### C. YouTube Autocomplete (`_fetch_yt`)
Because YT requires a "Seed" to search the autocomplete API, it safely relies exclusively on the `_peek` methods.

1. **Seed Borrowing (`yt_seed_providers` Array):**
   - **Single Provider:** If `["google"]`, it calls `_peek_google_seed()`.
   - **Multiple Providers (Sequential Waterfall):** If `["google", "wiki"]`, it acts as a Waterfall. It calls `_peek_google_seed()`. If Google has 0 matching titles for the niche today, it falls back sequentially and calls `_peek_wiki_seed()`.
   - **Selection & Gathering (`ignore_niches` Support):** Once it peeks into the correct cache, it gathers **ALL** items (filtering by `category == niche_name` if needed).
2. **The Local Exhaustion Loop (Temporary Tracking):**
   - We now have a list of valid seeds (e.g., `["Emily Blunt", "UFOs", "The Black Death"]`). 
   - We **shuffle** this list randomly: `random.shuffle(gathered_seeds)`.
   - We iterate through this list locally using a `for` loop. This guarantees we check *every single valid seed* before giving up, while the shuffle ensures random variety.
   - *Note:* We still **do not** set `"used": True` on the original Google objects, preventing cross-channel starvation.
3. **Alphabet Soup Fallback Loop (Per Seed):** 
   - **Raw Seed First:** Hit the YT API using the raw seed exactly as-is. 
   - **Alphabet Soup Fallback:** If the raw seed returns 0 results, OR if all results are duplicates, *then* append a random letter to the seed. Repeat up to 3 times. 
   - If a seed fails both raw and alphabet soup, the script `continue`s to the next seed in the shuffled list.
4. **Final Niche Fallback:**
   - If the local loop exhausted every single gathered seed and found 0 valid results, the script attempts to fall back to the raw `niche_name` string itself.
   - **Crucial Check:** It ONLY does this if `ignore_niches` is FALSE. (If it is true, the string is `"ANY"`, which would yield terrible Autocomplete results, so it safely returns `[]` instead).
   - It runs the raw/alphabet soup loop on the `niche_name`. If that **also** fails, it safely returns `[]` to the Waterfall.
5. **Text Generation & Return:** Once a valid phrase is finally found, use the Centralized AI Wrapper (`call_llm`) to generate a full script from scratch. Return it to `main.py` with `source_id="trends_yt_[Phrase]"`.

---

## 7. Exhaustion & Zero Matches (The End State)

Because we use a Unified List (Single Source of Truth), tracking "0 items found" is entirely native and requires no complex code.

*   **Google Exhaustion:** If a channel asks for "Horror", the script scans the 20 items in `self._google_trends`. If it iterates through the entire list and finds 0 matches, it safely returns `[]` to the Waterfall.
*   **Wikipedia Exhaustion:** The pagination loop continues slicing 100-item chunks. If `self._wiki_chunk_offset >= 1000`, it means we have categorized and checked every single item on Wikipedia. The script safely breaks the loop and returns `[]` to the Waterfall.
*   **YouTube Exhaustion:** If YT exhausts its shuffled list of seeds, falls back to the raw `niche_name`, tries alphabet soup on the `niche_name`, and STILL gets 0 results, it safely returns `[]` to the Waterfall.

If ALL providers in the Waterfall return `[]`, the final `[]` is handed back to `main.py`, which correctly logs *"Source returned 0 stories"* and falls back to `scp` or `ai`.
