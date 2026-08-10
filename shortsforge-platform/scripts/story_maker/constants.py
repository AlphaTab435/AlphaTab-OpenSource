"""
Centralized Constants for the ShortsForge Platform.
Prevents duplication of styling properties across the pipeline.
"""

# Base definitions for all subtitle configurations
AVAILABLE_SUBTITLE_STYLES = {
    "classic": {
        "is_animated": False,
        "ffmpeg_color": "white"
    },
    "capcut_yellow": {
        "is_animated": True,
        "html_color": "#FFFF00",
        "ffmpeg_color": "yellow"
    },
    "neon_red": {
        "is_animated": True,
        "html_color": "#FF0000",
        "ffmpeg_color": "red"
    },
    "electric_blue": {
        "is_animated": True,
        "html_color": "#00FFFF",
        "ffmpeg_color": "cyan"
    },
    "toxic_green": {
        "is_animated": True,
        "html_color": "#00FF00",
        "ffmpeg_color": "green"
    }
}

# Expose easy lookup lists for the scripts
ANIMATED_SUBTITLE_STYLES = [k for k, v in AVAILABLE_SUBTITLE_STYLES.items() if v["is_animated"]]
SUBTITLE_HTML_COLORS = {k: v["html_color"] for k, v in AVAILABLE_SUBTITLE_STYLES.items() if "html_color" in v}
SUBTITLE_FFMPEG_COLORS = {k: v["ffmpeg_color"] for k, v in AVAILABLE_SUBTITLE_STYLES.items()}
