# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to Semantic Versioning.

## [1.3.2] - 2026-08-10
### Added
- **[AutoPilot V3 - Infographics]** Launched the massive new Playwright-powered **Infographic Engine**! This feature uses HTML/JS templates, Lucide icons, Anime.js, and an advanced LLM prompt to dynamically map 5-word visual node concepts (icons, bubbles, arrows) into 5 aesthetic slots, then perfectly stitches the animations to exact `.srt` timestamps. Supports standard rendering or real-time WebM recording.
- **[Localization]** Added native `' EN'` and `' UR'` topic suffixing during `.zip` ingestion for seamless dual-language story routing.
- **[AI Generation]** Implemented intelligent language-agnostic **Dynamic Gender Detection** in `ScriptEditor`. The AI will now evaluate the story's POV and dynamically route the TTS engine to male/female voices, overriding the channel default.
- **[Audio]** Added verified Hindi neural voices to `voice_engine.py` to natively support Roman Urdu TTS.
- **[Upload]** Cleaned up YouTube SEO titles to automatically prepend `[Hindi/Urdu]` tags for localized targeting.
- **[Video Generation]** Formatted thumbnail hook labels to explicitly spell out the language for audience clarity.
- **[Video Generation]** Implemented full-screen sticky title headers for vertical layouts (using `textwrap` and drop shadows). Bypassed for horizontal videos.
- **[Ingestion]** Implemented a safe AI grammar bypass via `meta.json` to allow verbatim script rendering without AI alteration.

### Changed
- **[Video Generation]** Improved dynamic visual pacing to force a tighter 5-word maximum per visual block.
- **[Config]** Updated `autopilot.py` to explicitly pass `--video-dim` and `--thumb-dim` flags inline at runtime instead of relying solely on downstream defaults.
- **[Database]** Removed the legacy `language` column from the SQLite schema, replacing it with the new `language_pair` configuration string.

### Fixed
- **[Video Generation]** Fixed a critical pipeline crash caused by corrupt 0-byte `.srt` cache files. The pipeline now strictly validates cache file sizes (`> 1024` bytes for audio, `> 10` bytes for subtitles) and actively unlinks corrupted cache entries before FFmpeg can crash on them.
- **[Video Generation]** Added safety `try-except` wrappers around FFmpeg fallback rendering in `assembler.py` to prevent a single scene's failure from permanently crashing the entire pipeline.
- **[Video Generation]** Resolved a catastrophic 100% CPU infinite loop bug in FFmpeg background slicing.
- **[Video Generation]** Fixed a Chromium rendering crash by ensuring `playwright install-deps chromium` is properly documented, and resolved WebM Variable Frame Rate (VFR) desync issues.
- **[Video Generation]** Fixed the root cause of missing subtitle colors and styles by removing an inline `import json` that caused a silent `UnboundLocalError` crash during `voice_config` parsing.
- **[Video Generation]** Fixed the root cause of broken dynamic scene thumbnails by replacing the hardcoded 30-character slice (`[:30] + "..."`) with the full `hook` text from the input side.
- **[Styles]** Removed unused ghost aliases (`classic_white`, `highlight`) to clean up the `constants.py` architecture.


## [1.3.1] - 2026-07-23
### Added
- **[Monitoring]** Created `.agent/pipeline_fixes_log.md` to permanently track and verify pipeline edge cases, channel strikes, and quota analytics based on production logs.

### Changed
- **[Database]** Removed unused `custom_title` and `custom_description` columns from the core schema to streamline the database.
- **[Config]** Centralized all video and thumbnail style definitions (colors, alignments) into a single source of truth (`constants.py`), drastically reducing technical debt.
- **[Database]** Disabled the automatic daily reset of `channel_gen_quota` and `channel_upload_quota` to respect intentional quota exhaustion thresholds.

### Fixed
- **[Sniper]** Fixed deployment resource constraints by heavily optimizing limits to safely match the 2 OCPU and 12GB RAM free tier limits, preventing remote server exhaustion.
- **[Database]** Fixed a frustrating CLI bug where the database connection remained open and hung the terminal endlessly. Added explicit `db.close()` closures and removed redundant schema initializations.
- **[Video Generation]** Fixed a formatting bug where "Short Trailers" for Horizontal channels were mistakenly rendering horizontally. Short trailers are now mathematically enforced as Vertical formats regardless of channel settings.
- **[Video Generation]** Completely re-engineered thumbnail rendering to dynamically calculate font sizes and padding constraints based on string length, eliminating all text truncation.
- **[Video Generation]** Fixed a catastrophic `IndexError` during dynamic thumbnail generation that occurred when the DDGS image scraper hit rate limits. The pipeline now successfully uses the fallback global background.
- **[Video Generation]** Fixed a visual regression where Subtitles were pushed to the top-left of the screen. Implemented true "Middle-Center" alignment globally (`Alignment=10,MarginV=0`).
- **[Video Generation]** Re-enabled the HTML-based word highlight animations by fixing broken color mappings and properly passing style flags from `assembler.py` to the generation scripts.
- **[Video Generation]** Unsilenced all FFmpeg OS-level crashes. Errors like unescaped text semicolons will now boldly print their full traceback instead of failing silently.
- **[Scraper]** Hotfixed the AI Filter to successfully strip out `<think>` blocks emitted by the `qwen/qwen3.6-27b` model before parsing, rescuing hundreds of valid stories from being rejected.
- **[Upload]** Added critical `try/catch` safeguards around `youtube.playlistItems.insert` to guarantee that daily YouTube playlist quotas cannot crash the upload script and cause infinite duplication loops in the database.
- **[Upload]** Resolved a legacy Python 3.12+ `DeprecationWarning` regarding `datetime.utcnow()` scheduling math.

## [1.3.0] - 2026-07-19
### Added
- **[Ingestion]** Added Passthrough Metadata (`meta.json`) support. The pipeline now natively accepts custom `title`, `hook`, and `description` overrides directly from the ingested payload.
- **[Video Generation]** Added extensive pipeline toggles for dynamic thumbnail formatting (independent custom text colors, heavy shadow toggling, and gradient box toggling).
- **[Video Generation]** Explicitly enabled the dynamic scene visual mode for Shorts, including Call-To-Action (CTA) and duration support.
- **[Docs]** Added new troubleshooting guides for Google Drive Auth, YouTube Copyright tracking, and Production Deployment.
- **[Docs]** Updated `STORY_PIPELINE_GUIDE.md` to reflect all V2 AutoPilot features including UTC scheduling, dynamic visuals, and trends scraper usage.

### Changed
- **[Config]** Updated the Groq filter model from the deprecated `meta-llama/llama-4-scout-17b-16e-instruct` to `qwen/qwen3.6-27b`.
- **[Config]** Enforced a strict 140-word generation limit for all `is_shorts_only` channels via `accounts.json`.
- **[Audio]** Added explicit logging of selected background music tracks to simplify copyright claim tracking.

### Fixed
- **[Memory/Storage]** Fixed media pathing to perfectly isolate dynamic scene visuals into temporary directories while keeping classic images in persistent downloads, guaranteeing proper cleanup.
- **[Scraper]** Added a Latin-1 decoding fallback for the YouTube Autocomplete scraper to prevent crashing on international accents.
- **[Scraper]** Enforced strict SafeSearch on DuckDuckGo image searches to prevent NSFW generation.
- **[Build]** Fixed the V2 Deployment packager to mandate the transfer of `client_secret.json` for headless server authentication.

## [1.2.0] - 2026-07-04
### Added
- **[AutoPilot V3]** Fully implemented the **Dynamic Scene-by-Scene Visuals Engine**! This parallel video mode chunks the script into 12-second scenes, dynamically fetches highly targeted images per scene via DuckDuckGo, applies Ken Burns effects, and flawlessly stitches them together using FFmpeg. This drastically increases watch-time and helps prevent "Reused Content" flags.
- **[Content Optimization]** Implemented the full **Trends Module** (`trends.py`) to fetch data from Wikipedia, Google Trends, and YouTube Autocomplete with a seamless waterfall fallback.
- **[Content Optimization]** Added the **Voice Variety Engine** to allow each channel to configure its own distinct Edge-TTS voice.
- **[Content Optimization]** Added a stable **Background Music Layer** that correctly calculates lengths and precisely mixes ambient tracks behind the narration via `amix` to fix the FFmpeg stream looping bugs.
- **[Content Optimization]** Engineered a robust **Subtitle Failsafe System** which ditches buggy `.ass` formatting and successfully implements exact CapCut-style bold yellow word-by-word highlights directly inside standard `.srt` files.
- **[Content Optimization]** Enhanced FFmpeg visual templates for Thumbnails with viral CapCut styling (thicker outlines, yellow text, removed darkened boxes).
- **[Content Optimization]** Injected psychological "curiosity gap" and "visceral language" rules into the AI Prompts to maximize pacing and viewer retention.

### Changed
- **[Database]** Updated `channels` schema to include `visual_mode` (`classic` vs `dynamic`) and `dynamic_media_type`.
- **[Memory]** Implemented aggressive Auto-Cleanup protocol for Dynamic mode that instantly vaporizes temporary `part_{N}_assets` folders upon video generation, securing the pipeline against massive storage bloat.

## [1.1.6] - 2026-07-01
### Changed
- **[Config]** Migrated the Groq AI Generator from the deprecated `llama-3.3-70b-versatile` to `openai/gpt-oss-120b` in `ai_config.py` and `scraper_config.json` to prevent pipeline failures ahead of the August 16 deprecation. Also updated daily token limits to 200K based on the latest tiers.

## [1.1.5] - 2026-06-30
### Added
- **[Scraper]** Implemented a centralized Timestamp Circuit Breaker (`ai_router.py`) with a mathematically precise, non-blocking Load Balancer that dynamically tracks LLM cooldowns (`wake_up_time`). Includes a '3-Strike Rule' to permanently ban failing providers and prevent infinite loops.

### Changed
- **[Scraper]** Refactored `filter.py`, `polisher.py`, and `ai_generator.py` to eliminate redundant fallback loops by routing all LLM traffic through the new centralized `ai_router.py`.
- **[Config]** Updated `scraper_config.json` to upgrade the Groq filter model from `llama-3.1-8b-instant` to `meta-llama/llama-4-scout-17b-16e-instruct` and explicitly added `cerebras` to the `ai_providers` dictionary to support future standalone deployments.

## [1.1.4] - 2026-06-30
### Added
- **[Docs]** Explicitly defined the strict boundaries of the V2 codebase (`scripts/scraper` and `scripts/story_maker`) in `AGENT_INSTRUCTIONS.md` to prevent AI context drift and definitively deprecate legacy V1 modules.

### Changed
- **[Build]** Refined the headless server deployment package (`build_v2_autopilot_deployment.py`) by explicitly excluding V1 legacy code (`uploader.py`, `rate_limiter.py`) and local browser-based OAuth scripts (`add_channel.py`) to prevent server bloat. Included the new `delete_story.py` utility.

## [1.1.3] - 2026-06-25
### Fixed
- **[Critical]** Fixed a catastrophic 11.5 GB memory leak and infinite loop in `run_pipeline.py`.
  - **The Root Cause:** DuckDuckGo occasionally returned HTML files (like Cloudflare challenges) instead of images. Because these files were larger than 50KB, `media_picker.py` blindly saved them as `.jpg`. When `ffmpeg` was instructed to loop (`-loop 1`) this corrupt file, it entered an infinite loop, instantly spamming millions of `No JPEG data found` errors. Python's `subprocess.PIPE` dutifully captured every error into an internal string variable until the server ran out of RAM (11.5 GB) and OS OOM Killer assassinated the process.
  - **The Fix:** Implemented a strict 3-layer security sanitization in `media_picker.py` for all internet image downloads (DuckDuckGo, Pixabay, Pexels).
    1. **Content-Type Filter:** Rejects HTML or executable payloads at the HTTP header level.
    2. **Magic Bytes Verification:** Uses Pillow (`PIL.Image.verify()`) to strictly validate the file signature, immediately deleting polyglot files or scripts disguised with a `.jpg` extension.
    3. **Payload Sanitization:** Loads the verified image into memory, completely strips all EXIF metadata and hidden tracking payloads, converts it to pure sterile pixels (`RGB`), and saves the clean version to disk.
  - **Impact:** `ffmpeg` is now mathematically guaranteed to receive 100% pure, sterile image files, making the infinite loop physically impossible and protecting the server from disguised malware.

## [1.1.2] - 2026-06-25
### Fixed
- **[Minor]** Fixed an issue in `run_upload.py` where YouTube Playlists were being incorrectly created as `private` if the videos within them were scheduled. Playlists are now explicitly created as `public`, ensuring the series grouping is immediately visible on the channel while YouTube natively keeps the scheduled videos hidden until they go live.

## [1.1.1] - 2026-06-25
### Fixed
- **[Critical]** Fixed catastrophic log vaporization in `autopilot.py` during forced OS terminations (e.g., the 11.5 GB OOM `SIGKILL` crash). 
  - **The Investigation:** While investigating a massive memory leak, we discovered the logs were completely missing the context of what the script was doing immediately prior to the crash. This caused a total inability to diagnose the root cause, forcing us to rely on assumptions because the true point of failure was hidden.
  - **The Discovery:** We discovered that Python's `sys.stdout` block-buffers when piped to a background process, meaning `print()` statements are trapped in a 4KB buffer. Because `logging` uses `sys.stderr` (which is line-buffered), the `INFO:` logs bypassed the trap and wrote instantly, creating highly confusing, out-of-order logs where critical `print()` context was destroyed upon OS termination.
  - **The Decision:** Instead of making unnecessary and potentially harmful changes to the pipeline based on unproven assumptions, we decided to step back and fix the logging system first to get undeniable proof of what was happening.
  - **The Fix:** To reveal the true point of failure, we added the `-u` (unbuffered) flag to all `sys.executable` subprocess calls. This completely disables the block buffer, forcing `print()` statements to synchronize perfectly with `logging` statements in real-time.
  - **Future Impact:** This guarantees 100% log fidelity up to the exact millisecond of any future crash, providing bulletproof diagnostic evidence for hidden memory leaks or hangs.
- **[Minor]** Added `save_local_report()` to `autopilot.py` to synchronously backup all HTML email reports directly to the host disk before attempting SMTP dispatch. This ensures the daily reports are permanently preserved even if Google's SMTP rate-limits or network connectivity drops.

## [1.1.0] - 2026-06-23
### Added
- **V2 Autopilot Server Scripts**: Added deployment tools (`v2_autopilot_ubuntu_setup.sh`, `build_v2_autopilot_deployment.py`) for autonomous, headless Ubuntu server execution.
- **OCI Sniper (`oci_sniper.py`)**: Added an Oracle Cloud auto-provisioning script to continuously monitor and secure free-tier compute instances.
- **YouTube Native Scheduling (`--schedule`)**: Upgraded `run_upload.py` to utilize the `publishAt` API parameter, allowing native video scheduling on YouTube with customizable upload intervals.
- **V2 Autopilot Documentation**: Added comprehensive guides (`DEPLOYMENT_GUIDE.md`, `MONITORING_GUIDE.md`, `ORACLE_COST_ESTIMATES.md`) for the new autonomous server setup.

### Changed
- **Pipeline Volume**: Increased daily per-channel volume limits to 10 in `accounts.json` to scale up pipeline operations.
- **Headless Master Autopilot**: Refactored `autopilot.py` to better support full end-to-end execution in crontab-based environments.

### Fixed
- **[Minor]** Fixed UTF-16 encoding corruption in `.gitignore` caused by legacy Windows PowerShell append scripts.


## [1.0.1] - 2026-06-18 [BETA / UNSTABLE]
### Added
- **Shorts-Only Mode (`is_shorts_only`)**: Channels can now be explicitly configured as `is_shorts_only` in the config JSON. This bypasses upfront trailer generation and mathematically pre-chunks the *entire* raw text into sequential YouTube Shorts natively (target ~2.5 mins per part).
- **Automated Thumbnail Email Attachments**: Shorts thumbnails are now attached directly to the Daily Report email for easy downloading to mobile devices.

### Fixed
- **[Critical]** Fixed a mathematical bypass mismatch where stories between 250 and 375 words were erroneously generating both Standalone Shorts and Long Videos. Unified threshold to strictly `< 375` words.
- **[Critical]** Fixed `has_multiple_parts` initialization bug where the "(Part X)" suffix was completely dropped from the first chunk of newly-split videos.

> **Warning:** This version is currently marked as **UNSTABLE**. The mathematical chunker and automated upload pipeline are heavily reliant on highly-specific token counts and API behaviors. Monitor the daily reports carefully.

## [1.0.0] - 2026-06-18
### Added
- **Master Autopilot (`autopilot.py`)**: End-to-end orchestration of the entire platform.
- **Automated Scraper**: Fully functional scraper with AI filtering, polishing, and dynamic quota management.
- **ShortsForge Video Pipeline**: JIT (Just-In-Time) mathematical chunking, Edge TTS generation, and dynamic 9:16 FFmpeg video assembly.
- **YouTube Uploader**: Automatic OAuth2 uploads with support for private/public flags and automatic playlist assignment.
- **Local Backup Manager**: Autonomous snapshot system that compresses all data, logs, and databases into a timestamped `.zip`.
- **Google Drive Integration**: Automated cloud backup uploads using User OAuth2 to bypass Service Account limits.
- **Email Reporting System**: Automated success/crash email reports with full HTML formatting and tracebacks.

### Fixed
- Fixed critical Windows Console `cp1252` encoding crashes caused by Unicode branch characters (`└─`).
- Fixed Zip Archive root-pathing bug that prevented the Ingester from finding `1.txt` files.
- Fixed `run_upload.py` ghost error issue where the database retained old `error_log` messages after successful uploads.
