# Implement Background Music Layer

This plan outlines how we will add subtle, royalty-free background music to the generated videos, addressing requirements for channel-level toggles and stable audio looping.

## Proposed Changes

### Database & Configuration (Channel-Level Toggle)

We will utilize the existing JSON column (`voice_config`) and treat it as a general audio configuration. 

#### [MODIFY] `add_channel.py`
- When creating a channel, add a prompt: `Enable Background Music? (y/n) [Default: y]`.
- Store this in the `voice_config` column as `{"voice": "male_narrator", "music": true}`.
- Create the `data/backgrounds/{channel_id}/music/` folder automatically.

#### [MODIFY] `run_pipeline.py`
- Extract both `voice_key` and `music_enabled` from the JSON config.
- If a channel has no config, default to `music_enabled = True`.
- Pass `music_enabled` as a new parameter down into `assembler.build_part()` and `build_short_story()`.

---

### Media Handling & Stable Looping

#### [MODIFY] `media_picker.py`
- Add `get_background_music(channel_name: str)`.
- Searches `data/backgrounds/{channel_name}/music/` for `.mp3`/`.wav`.
- Falls back to `data/backgrounds/global_music/`.
- Returns `None` if neither has files.

#### [MODIFY] `assembler.py`
To avoid the unstable `-stream_loop -1` flag, we will build a dedicated "Audio Handler" step before video assembly. 

1. **Calculate Loops**: Get the duration of the TTS audio (`target_duration`) and the chosen music track. Calculate exact loops needed.
2. **Stable Concat File**: Dynamically write a temporary `concat.txt` file listing the music file the exact number of times needed.
3. **Pre-mix Audio**: Run a fast, audio-only FFmpeg command to combine the TTS and the looped music file using the `concat` demuxer and `amix` filter, cutting off exactly at the `target_duration`.
4. **Final Assembly**: Pass this perfectly pre-mixed, single `.mp3` file into the existing video generation command as the sole audio input, avoiding complex video/audio sync bugs.
