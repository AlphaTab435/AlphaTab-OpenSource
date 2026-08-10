import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def get_env(key: str, required: bool = False, default: str = None) -> str:
    """
    Retrieves environment variable with optional requirement check.
    
    Args:
        key: The environment variable key.
        required: Whether the value is mandatory.
        default: The default value if not found.
        
    Returns:
        The environment variable value or default.
        
    Raises:
        ValueError: If required is True and the variable is missing.
    """
    value = os.environ.get(key, default)
    if required and (value is None or value.strip() == ""):
        raise ValueError(f"CRITICAL: Environment variable {key} is missing or empty.")
    return value

# ─── Global Settings ───
DEV_MODE = get_env("DEV_MODE", default="false").lower() == "true"

# ─── FFmpeg Hardware Configuration ───
# Exposes direct control over FFmpeg rendering overhead to bypass DEV_MODE hardcodes
FFMPEG_THREADS = get_env("FFMPEG_THREADS", default="2" if DEV_MODE else "0")
FFMPEG_PRESET = get_env("FFMPEG_PRESET", default="ultrafast" if DEV_MODE else "fast")
FFMPEG_TRANSITION_STYLE = get_env("FFMPEG_TRANSITION_STYLE", default="none" if DEV_MODE else "fade")

# Google AI Pro subscription flag (default: false = free tier only)
# When true, unlocks higher RPM, Gemini 2.5 Pro, etc.
GOOGLE_AI_PRO = get_env("GOOGLE_AI_PRO", default="false").lower() == "true"

# ─── API Keys (required — free tier) ───
GEMINI_API_KEY = get_env("GEMINI_API_KEY", required=False)
CEREBRAS_API_KEY = get_env("CEREBRAS_API_KEY", required=False)
GROQ_API_KEY = get_env("GROQ_API_KEY", required=False)
DEEPSEEK_API_KEY = get_env("DEEPSEEK_API_KEY", required=False)
PEXELS_API_KEY = get_env("PEXELS_API_KEY", required=False)
PIXABAY_API_KEY = get_env("PIXABAY_API_KEY", required=False)

# ─── AI Engine Configuration ───
PRIMARY_AI_PROVIDER = get_env("PRIMARY_AI_PROVIDER", default="cerebras").lower()
PRIMARY_AI_MODEL = get_env("PRIMARY_AI_MODEL", default="llama3.1-8b")

# ─── Optional Services ───
TURSO_URL = get_env("TURSO_URL", required=False)
TURSO_TOKEN = get_env("TURSO_TOKEN", required=False)
ENCRYPTION_KEY = get_env("ENCRYPTION_KEY", required=False)

# ─── Notification Credentials (optional — free tier) ───
DISCORD_WEBHOOK_URL = get_env("DISCORD_WEBHOOK_URL", required=False)
GMAIL_USER = get_env("GMAIL_USER", required=False)
GMAIL_APP_PASSWORD = get_env("GMAIL_APP_PASSWORD", required=False)

GEMINI_MODELS = {
    "text": "gemini-1.5-flash",              # Script generation, topic selection, QA
    "tts": "gemini-2.5-flash-preview-tts",   # TTS (Week 5+, optional)
    # Google AI Pro only — higher quality scripts + media generation
    "pro_text": "gemini-2.5-pro-preview-03-25" if GOOGLE_AI_PRO else "gemini-1.5-flash",
    "thinking": "gemini-2.5-pro-preview-03-25" if GOOGLE_AI_PRO else "gemini-1.5-flash",
    "veo": "veo-2.0-generate-001" if GOOGLE_AI_PRO else None,       # AI video generation
    "nano_banana": "imagen-3.0-generate-002" if GOOGLE_AI_PRO else None,  # AI image generation
}

FREE_LIMITS = {
    "gemini_rpm": 15,          # Requests per minute (free tier)
    "gemini_tpd": 1_000_000,   # Tokens per day (free tier)
    "pexels_per_hour": 200,    # Pexels API rate limit
    "google_trends": 1000,     # Unofficial limit
    "uploads_per_day": 6,      # YouTube uploads per day
    "veo_daily": 0,            # AI video clips (Pro only)
    "nano_pro_daily": 0,       # AI image generations (Pro only)
    "video_credits_monthly": 0,  # Monthly video gen credits (Pro only)
    "deep_research_daily": 0,  # Research reports (Pro only)
}

# If Google AI Pro is active, override limits
if GOOGLE_AI_PRO:
    FREE_LIMITS["gemini_rpm"] = 1000    # Pro tier
    FREE_LIMITS["gemini_tpd"] = 50_000_000
    FREE_LIMITS["uploads_per_day"] = 50
    FREE_LIMITS["veo_daily"] = 3               # 3 Veo 3.1 generations/day
    FREE_LIMITS["nano_pro_daily"] = 100         # 100 studio-quality images/day
    FREE_LIMITS["video_credits_monthly"] = 1000  # Shared pool across channels
    FREE_LIMITS["deep_research_daily"] = 20     # 20 autonomous research reports/day

# ─── Supported Niches (MASTER_PLAN Part 2) ───
SUPPORTED_NICHES = [
    "space",            # RenderMind — Space & Universe + AI Tech
    "motivation",       # MTabish — Motivational / Stoic Wisdom
    "mystery",          # Stunners — True Crime & Unsolved Mysteries
    "money",            # New Channel — Make Money with AI
    "movie_explainer",  # New Channel — Movie/Anime Explanations (Urdu)
]

# ─── Supported Languages ───
SUPPORTED_LANGUAGES = {
    "en": "English",
    "ur": "Urdu",
}

# ─── Voice Configuration (MASTER_PLAN Part 2) ───
NICHE_VOICES = {
    "space": "Charon",           # Deep, documentary narrator
    "motivation": "Fenrir",      # Calm, wise, masculine
    "mystery": "Orus",           # Tense, gripping, builds dread
    "money": "Aoede",            # Clear, trustworthy
    "movie_explainer": "Charon", # Deep (for English version)
}

# Channel config is now actively fetched from the database using core.channels.get_channels()
