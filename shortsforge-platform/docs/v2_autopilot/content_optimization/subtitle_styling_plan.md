# Subtitle Styling Upgrade (With Failsafe Toggle)

**Problem:** Current subtitles are tiny white text (`Fontsize=16`) with minimal outline. Viral Shorts use bold, large, word-by-word colored subtitles (CapCut style).
**Goal:** Increase font size, add colored keyword highlighting, improve positioning, but keep it simple and safe.

## Implementation Details

### 1. Failsafe Toggle Configuration
We will add a style toggle to the existing JSON config in the database.
- **`classic`**: The exact current behavior (small white text, no word-level highlighting). **[DEFAULT]**
- **`capcut_yellow`**: The new viral style (massive font, bold outline, yellow word-by-word highlights).

#### [MODIFY] `scripts/add_channel.py`
- Add a prompt: `Select Subtitle Style (1: classic, 2: capcut_yellow) [Default: classic]`.
- Store this safely in the `voice_config` column.

#### [MODIFY] `scripts/story_maker/run_pipeline.py`
- Extract the `subtitle_style` from the JSON.
- If a channel has no config (legacy channels), we will default to `classic` to guarantee zero risk of breaking existing channels.

### 2. SRT Generation & FFmpeg Assembly
#### [MODIFY] `scripts/story_maker/voice_engine.py`
- We will modify `_generate_edge_tts` to accept the `subtitle_style` parameter.
- If the style is `classic`, it generates the exact same `.srt` file it does today.
- If the style is `capcut_yellow`, it calculates the exact millisecond duration of each word based on character length and generates sequential SRT blocks wrapping the active word in `<font color="#FFFF00">`.

#### [MODIFY] `scripts/story_maker/assembler.py`
- In `build_part()`, we will swap the `force_style` block based on the selected style.
- `classic` uses existing: `Fontsize=16, Outline=1.2`
- `capcut_yellow` uses upgraded: `Fontsize=22, Outline=3, BorderStyle=1, Bold=1, Shadow=1`
