# Implement Voice Variety Per Channel

This plan outlines how we will allow each channel to have its own unique Text-to-Speech voice, pulling from the database instead of hardcoding a single global voice.

## Changes Overview

We will use the existing `voice_config` JSON column in the `channels` SQLite table. We will maintain the master list of available voices centrally in `voice_engine.py` to keep a single source of truth. We will implement robust fallbacks to `male_narrator` across the stack to ensure zero downtime.

---

### Database & Configuration

#### [MODIFY] `add_channel.py`
- Import `EDGE_VOICES` from `voice_engine.py`.
- During the interactive channel creation flow, print the available voice options and prompt the user to select one (e.g., `1. male_narrator`, `2. dramatic_male`).
- **Resiliency Update**: If the user inputs nothing, enters invalid data, or skips it, the script will silently fall back to storing `{"voice": "male_narrator"}` to prevent database null crashes.
- Save the selection into the `channels` table under the `voice_config` column as a JSON string.

---

### Core Pipeline

#### [MODIFY] `run_pipeline.py`
- In `get_active_channels_with_stories()`, include the `voice_config` column in the SQL query.
- Parse the JSON to extract the voice key.
- **Resiliency Update**: If the channel is an older legacy channel with a missing or null `voice_config`, gracefully fall back to `"male_narrator"`.
- Pass the extracted voice key down into `process_series()`.
- When generating the upfront Shorts (around line 191), pass the voice key to `voice.generate_audio(..., voice_override=voice_key)`.

#### [MODIFY] `voice_engine.py`
- Add new recommended neural voices to the `EDGE_VOICES` dictionary (e.g. `authoritative_male`, `british_female`).
- Update `generate_audio()` to accept a new `voice_override` parameter.
- Update `_generate_edge_tts()` to accept a `target_voice` parameter instead of strictly relying on `self.voice`.
- If `voice_override` is provided, look it up in `EDGE_VOICES` (with a safe `.get()` fallback) and use it for that specific audio generation call.
