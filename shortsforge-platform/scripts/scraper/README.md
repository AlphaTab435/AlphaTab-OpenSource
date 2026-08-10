# ShortsForge Scraper

The scraper is an independent, robust tool designed to fetch highly engaging stories and save them locally. It supports public domain sources, the SCP wiki, and fully automated AI generation.

## Configuration Guide (`configs/`)

### `scraper_config.json`
Controls the scraper's behavior and AI limits.
- `ai_fallback_chain`: A list of providers to try (e.g., `["gemini", "groq"]`). If the first one fails or hits limits, it automatically falls back!
- `enable_audit_folder`: If true, saves the text of any story the AI Filter rejects so you can debug why.
- `[provider]_generator_model`: The specific AI model used for writing stories.
- `[provider]_filter_model`: The specific AI model used for the Halal/Quality check.

### `accounts.json`
Defines your channels and what they pull.
- **Valid Sources**: `"public_domain"`, `"scp_wiki"`, `"ai"`.
- **Valid Niches**: Any exact string defined in your `niches.json` file.
- **Random Mode**: Leave a list empty `[]` to enable Random Mode! Every single story fetched will pick a random combo.
- **Multi-Source Resilience**: If one source entirely fails (e.g., the AI limits run out), the scraper will gracefully "hop" to the remaining sources without crashing!

### `niches.json`
Maps your niches (e.g., "Company Failures") to the appropriate Subreddits and AI Prompts. Add new ones here before using them in `accounts.json`.

## Zipping the Content
Because the scraper is perfectly standalone, it does not zip files itself anymore. To zip your staging folder and prepare it for ingestion, simply run:
```bash
python ../utils/zip_folder.py --source output/staging --output output/content.zip
```
