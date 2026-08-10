# Production Deployment & Testing Guide (V1.2.0)

This document outlines the official testing matrix for the V3 Dynamic Visuals engine and the steps required to transition the pipeline from "Testing" to "Full Production" on a headless server.

---

## 1. The Ultimate Test Matrix (4 Channels)
When setting up the server, use `scripts/add_channel.py` to input these exact configurations. This matrix guarantees that **every single feature** (Dynamic vs Classic, Subtitle variations, Voices, Music toggles, and Short vs Long logic) is executed and verified.

### Channel 1: `Tabish6482` (The True Crime Test)
*Tests Classic Mode with a Gameplay Video + CapCut Subtitles.*
- **Niche:** `True Crime`
- **Image Search Style:** `dark gritty true crime photo`
- **Is this channel EXCLUSIVELY for Shorts? (y/n):** `y`
- **Select a voice:** `3` *(dramatic_male)*
- **Enable Background Music?:** `y`
- **Select Subtitle Style:** `2` *(capcut_yellow)*
- **Select Visual Mode:** `1` *(classic)*
- **Server Action:** Upload a `gameplay.mp4` to `data/backgrounds/Tabish6482/` to force video backgrounds.

### Channel 2: `tabish7280` (The Science/Space Test)
*Tests Dynamic Scene-by-Scene Engine on Long-form content.*
- **Niche:** `Science and Space`
- **Image Search Style:** `cinematic deep space photography`
- **Is this channel EXCLUSIVELY for Shorts? (y/n):** `n`
- **Select a voice:** `1` *(male_narrator)*
- **Enable Background Music?:** `y`
- **Select Subtitle Style:** `1` *(classic)*
- **Select Visual Mode:** `2` *(dynamic)*

### Channel 3: `officeusesep` (The Horror Test)
*Tests Dynamic Engine with Music disabled to verify audio mixing failsafes.*
- **Niche:** `Horror`
- **Image Search Style:** `terrifying horror digital art`
- **Is this channel EXCLUSIVELY for Shorts? (y/n):** `y`
- **Select a voice:** `2` *(female_narrator)*
- **Enable Background Music?:** `n`
- **Select Subtitle Style:** `2` *(capcut_yellow)*
- **Select Visual Mode:** `2` *(dynamic)*

### Channel 4: `stunnersgaming46` (The History Test)
*Tests Classic Mode falling back to Image Zoom (no gameplay video provided).*
- **Niche:** `History`
- **Image Search Style:** `historical oil painting dramatic`
- **Is this channel EXCLUSIVELY for Shorts? (y/n):** `n`
- **Select a voice:** `5` *(british_male)*
- **Enable Background Music?:** `y`
- **Select Subtitle Style:** `1` *(classic)*
- **Select Visual Mode:** `1` *(classic)*
- **Server Action:** Do NOT upload a gameplay video. Let the system naturally download a historical painting via DuckDuckGo.

---

## 2. Background Selection Logic (The Fallback Tiers)
In **Classic Mode**, the pipeline decides whether to use a video or an image purely based on what files you place on the server.

1. **Tier 1 (Channel Video):** If `data/backgrounds/{channel_name}/gameplay.mp4` exists, it uses it.
2. **Tier 2 (DuckDuckGo Image):** If no video exists, it searches DuckDuckGo using the story title, downloads a highly relevant image, and uses it for the entire video with a slow Ken Burns zoom.
3. **Tier 3 (Static Channel Image):** If the internet fails, it uses a generic `.jpg` placed in the channel folder.
4. **Tier 4 (Global Fallbacks):** Checks global gameplay videos or global generic images if all else fails.

*Dynamic Mode bypasses this entirely and always generates 10-15 second scene chunks via LLM prompts.*

---

## 3. Transitioning to Full Production
Once the testing matrix runs successfully and 4 videos are successfully uploaded to YouTube without errors, execute the following to move to Full Production:

### Step 1: Scale Up Volume
Testing is done at low volume (1 video per channel). For algorithm traction:
- Run a SQLite query on the server to bump production volume:
  ```sql
  UPDATE channels SET channel_gen_quota = 3;
  ```
- This will generate 3 Shorts per channel per day.

### Step 2: Establish the Cron Schedule
Set the master `autopilot.py` to run during peak US hours (11 PM - 2 AM PKT).
- Open crontab: `crontab -e`
- Add: `0 20 * * * cd /path/to/shortsforge && /path/to/venv/bin/python scripts/autopilot.py` (Runs at 8 PM UTC / 1 AM PKT).

### Step 3: Shift Database to "Monetization Mode"
The test matrix above intentionally varied settings to prove the code works. But for **maximum virality and monetization**, YouTube rewards high-retention, fast-paced content. 
Once testing is done, you should use an SQLite editor (or run `add_channel.py` again) to standardize **ALL** channels to this proven algorithmic setup:
- **Visual Mode:** `dynamic` *(Scene-by-scene jumping every 12s retains viewers WAY better than static zooming)*
- **Subtitle Style:** `capcut_yellow` *(The bold yellow highlights hack viewer attention)*
- **Enable Background Music?:** `y` *(Subtle music fills dead air)*
- **Is this channel EXCLUSIVELY for Shorts?:** `y` *(Unless you specifically want long-form, 100% Shorts volume grows new channels faster)*

*(Note: `accounts.json` does not need to change because the niches and `trends` source are already optimized for production).*

### Step 4: Monitor & Iterate
- Let the system run completely untouched for **7 to 14 days**.
- Review YouTube Analytics for Retention and Click-Through Rate (CTR).
- If the "Dynamic" channels perform drastically better than "Classic" channels, update the database to switch all channels to `dynamic` visual mode.
- Update `accounts.json` niches if certain topics are flatlining while others go viral.

### Step 4: Monetization Compliance
- Once a channel nears **1,000 subscribers**, update the `yt_uploader.py` script to flag the videos as "Altered Content" (AI Disclosure) to pass the human review for the YouTube Partner Program.

---

## 5. Background Music Setup Guide

### Where to Download Free, Safe Music
Do not use random MP3s from the internet, or YouTube will immediately hit you with "Copyright Claims" and destroy your monetization. Use these two safe sources:
1. **YouTube Audio Library (Safest):** Go to your YouTube Studio → Left Menu → "Audio Library". Everything here is 100% free and copyright-safe forever.
2. **Pixabay Music (Easiest):** Go to [pixabay.com/music/](https://pixabay.com/music/). You can search by "mood" (like creepy, epic, ambient) and download instantly without logging in.

### Global vs Channel-Specific (Recommended)
Because the niches are so wildly different (Horror vs Space vs History), **Channel-Specific Music is highly recommended.** If you use "Global Music", the system might accidentally play a happy, bouncy Lo-Fi beat behind a terrifying Horror story, which will completely ruin the vibe and kill viewer retention.

Here is exactly what you should search for on Pixabay/YouTube and where to put it on your server:

#### 📁 Channel 1: `Tabish6482` (True Crime)
- **What to search for:** "Suspense", "Dark Ambient", "Tension"
- **Where to put the .mp3s:** `data/backgrounds/Tabish6482/music/`

#### 📁 Channel 2: `tabish7280` (Science and Space)
- **What to search for:** "Sci-Fi", "Synthesizer", "Ethereal", "Deep Space"
- **Where to put the .mp3s:** `data/backgrounds/tabish7280/music/`

#### 📁 Channel 3: `officeusesep` (Horror)
- **What to search for:** "Creepy", "Horror Drone", "Scary Piano"
- **Where to put the .mp3s:** `data/backgrounds/officeusesep/music/`

#### 📁 Channel 4: `stunnersgaming46` (History)
- **What to search for:** "Epic Orchestral", "Cinematic", "Historical"
- **Where to put the .mp3s:** `data/backgrounds/stunnersgaming46/music/`

### The "Lazy" Alternative (Global Music)
If you don't want to manage 4 different folders right now, there is a cheat code. Since True Crime, Horror, Space, and History all share a "serious/mysterious" vibe, you can:
1. Go to Pixabay.
2. Download 10 **"Dark Ambient / Mysterious Drone"** tracks. *(No drums, no happy melodies, just deep mysterious sounds).*
3. Put them all in `data/backgrounds/global_music/`.
4. It will sound perfectly fine across all 4 channels!
