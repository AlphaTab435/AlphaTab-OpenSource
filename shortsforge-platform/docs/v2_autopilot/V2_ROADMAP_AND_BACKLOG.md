# V2 AutoPilot: Feature Backlog & Roadmap

This document permanently tracks upcoming features, architectural shifts, and intelligent AI upgrades requested for the ShortsForge V2 AutoPilot pipeline.

## 1. Intelligent AI Perspective Detection (Dynamic Voice Assignment)
**Research Hypothesis:** If a story is written from a female perspective but read by the channel's default `male_narrator`, will it negatively affect the channel?
**Current Stance:** **NO.** Research into faceless YouTube channels suggests audiences mentally separate the "Narrator" from the "Character." We hypothesize that maintaining a consistent channel voice (Brand Voice) is far more important.

**CONTINGENCY PLAN (If Analytics Prove Us Wrong):**
If live YouTube analytics show that viewers *are* bouncing due to gender mismatch, we will implement the following architectural upgrade:
- Do not use manual `meta.json` overrides. Instead, build an intelligent runtime system where the LLM evaluates the story text and dynamically determines the narrative perspective (male/female).
- **Database Architecture:** Add a new column to the database (e.g., `story_parts.assigned_voice` or similar) to permanently cache the AI's perspective decision. This ensures consistency across multi-part stories and prevents querying the LLM repeatedly if the pipeline restarts.

## 2. Strict AI Grammar Bypass (Reel Continuity)
**Research Hypothesis:** If the AI rewrites the story text (shifting perspective or simplifying vocabulary), will it negatively affect the channel?
**Current Stance:** **YES.** Because traffic is funneled from Facebook/TikTok Reels, continuity is everything. If the words change, viewers bounce.

**Planned Feature ("Safe AI" Route):**
- Implement a `"bypass_ai_grammar": true` flag inside `meta.json`. 
- Instead of skipping the AI entirely (which risks garbage characters crashing the TTS engine), this flag will trigger a *Sanitization Prompt*.
- The Sanitization Prompt will explicitly instruct the LLM: *"Do NOT change vocabulary, idioms, perspective, or sentence structure. Your ONLY job is to remove markdown, weird symbols, and fix typos so the text can be safely read by a TTS engine."*

**Status: COMPLETED (v1.3.2)**
- Implemented `"bypass_ai_grammar": true` flag inside `meta.json`. 
- When activated, instead of skipping the AI entirely (which risks garbage characters crashing the TTS engine), it triggers a *Sanitization Prompt*.
- The Sanitization Prompt explicitly instructs the LLM: *"Do NOT change vocabulary, idioms, perspective, or sentence structure. Your ONLY job is to remove markdown, weird symbols, and fix typos so the text can be safely read by a TTS engine."*

## 3. Observation & Verification Protocol
**CRITICAL RULE:** Do NOT build the Dynamic Voice Assignment code (Section 1) immediately. We must observe production analytics first.
Before building the voice switcher, we must verify:
1. Is the current voice assignment *actually* triggering a viewer bounce rate in YouTube analytics due to gender perspective mismatch? 
2. If analytics remain strong, no changes are needed. If retention drops, implement the intelligent voice router.

## 4. Multi-Language Support (English & Urdu)
**Problem:** The V2 pipeline is currently optimized for English generation.
**Planned Solution:**
- Expand pipeline capabilities to fully support **English**, **Urdu**, and a hybrid **English + Urdu** combination.

**Decision (Subtitles): ROMAN URDU (Easy Route)**
- We will generate subtitles using "Roman Urdu" (Urdu written in the English alphabet, e.g., "Mera naam...").
- This is highly effective for fast-paced viral shorts and saves massive engineering time because FFmpeg will render it perfectly using standard English fonts. No RTL text-reshaper hacking is required!

## 5. Automated AI Translation 
**Problem:** Ingested raw stories might be in the wrong language relative to the target channel's audience.
**Planned Solution:**
- Implement a pre-processing validation step where the AI evaluates the language of the source text.
- If the source text language does not match the channel's target language (e.g., source is English, channel is Urdu), the AI will automatically translate and adapt the story into the correct language *before* it gets sent to the audio/video rendering engines.

## 6. Known Production Pipeline Bugs to Fix
**Bug 1: Empty Video `ffmpeg -stream_loop` Server Hang**
- **Status:** FIXED (Hypothesis proven correct via strace & ffprobe)
- **Symptom:** Server CPU hits 100%, Load Average > 6, Memory Stalls. `run_pipeline.py` hangs infinitely during Phase 3 Video Generation.
- **Root Cause:** Introduced in `da15819` (Pipeline Overhaul). When a custom channel background video is provided, `media_picker.py` uses the global `gameplay.mp4` to calculate the duration, rather than the channel's actual video. This causes the slice `start_time` to fall past the end of the video, creating an empty 0-byte video slice. When `assembler.py` attempts to loop that empty video using `-stream_loop -1`, FFmpeg gets stuck in an infinite read loop, bringing down the server.
- **Immediate Mitigation:** SSH into server, kill the hung `ffmpeg` process, and delete the custom channel video from `data/backgrounds/<channel_name>/gameplay.mp4`.
- **Permanent Code Fix:** Change `total_duration = self.get_video_duration(GAMEPLAY_FILE)` to use the actual `target_file` in `media_picker.py`.
