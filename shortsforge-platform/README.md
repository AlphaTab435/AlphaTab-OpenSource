# ShortsForge (V2 Autopilot)

**A Fully Automated, Headless YouTube Shorts Factory**

ShortsForge is an autonomous video generation pipeline. It scrapes content, rewrites and translates it using AI, generates audio, builds dynamic visual scenes (or Playwright-rendered infographics), and uploads directly to YouTube via OAuth—all without human intervention.

## 🚀 What it does
- **Infographic Engine**: Reads JSON layouts from the LLM, maps icons and speech bubbles to screen slots, and syncs Anime.js animations to exact `.srt` audio timestamps using Playwright.
- **Dynamic Scene Visuals**: Chops scripts into discrete scenes and generates custom AI imagery for each sentence.
- **Dual-Language & Dynamic Gender**: Native support for English and Roman Urdu. The AI evaluates the narrative POV and dynamically routes to Male/Female Edge-TTS voices.
- **Quota Hierarchy**: A robust SQLite database manages global, channel, and story limits to ensure rate-limited YouTube uploading.
- **Headless Automation**: Designed to run seamlessly on a headless Linux box via a cron job, including automated Google Drive zip backups.

---

## 🛠 Quick Start (Local Setup)

1. **Install Dependencies**
   Since this pipeline is designed for strict headless deployments, the requirements file is dynamically generated to ensure no legacy bloat.
   ```bash
   git clone <your-repository-url>
   cd <project-folder>
   python3.13 -m venv .venv
   source .venv/bin/activate
   
   # Generate the pure V2 requirements file
   python scripts/utils/build_v2_autopilot_deployment.py
   pip install -r temp_deploy_build/deploy_requirements.txt
   
   playwright install chromium
   ```

2. **Configure Environment**
   Rename the included `autopilot_credentials.env.example` file to `.env` and fill in your API keys (Gemini, SMTP, etc).

3. **Set Up Google Cloud OAuth (Required)**
   Before running the pipeline, you must configure YouTube and Google Drive API access:
   - Go to the Google Cloud Console and enable **YouTube Data API v3** and **Google Drive API**.
   - Create an **OAuth Client ID** (Desktop App).
   - Download the JSON file, rename it to exactly `client_secret.json`.
   - Place it in the project like this: `data/credentials/client_secret.json` (Create the folders if they do not exist).
   - *Note: On first run of the backup script, it will pop up a browser to save a `drive_token.json` next to your client secret.*

4. **Authenticate & Scaffold a Channel**
   ```bash
   python scripts/add_channel.py
   ```
   Follow the interactive CLI to set the channel's target language, voice preferences, and visual modes.

5. **Run the Autopilot**
   ```bash
   python scripts/autopilot.py
   ```
   *This single command will scrape, ingest, generate videos in the background, upload to YouTube, and email you a daily report.*

---

## 📚 Documentation

The core of ShortsForge lies in its detailed pipeline rules. Please consult the official documentation files included in this repository:

- **System Guide & Architecture**: Look for `STORY_PIPELINE_GUIDE.md` for a deep dive into the Quota System, `meta.json` passthroughs, the Infographic Engine, and AI prompts.
- **Deployment Guide**: Look for `DEPLOYMENT_GUIDE.md` for step-by-step instructions on deploying the headless pipeline to an Oracle Cloud VM or any Linux server.

## License
Open Source
