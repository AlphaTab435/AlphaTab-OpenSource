import yaml
import os

CONFIG_PATH = os.path.join("data", "config.yaml")

DEFAULT_CONFIG = {
    "search": {
        "titles": [
            "Junior DevOps Engineer",
            "DevOps Engineer",
            "Backend Developer",
            "Junior Backend Developer"
        ],
        "regions": [
            "Lahore, Pakistan",
            "Pakistan",
            "Remote",
            "Canada",
            "Germany",
            "Netherlands",
            "United Kingdom",
            "United States",
            "Australia",
            "United Arab Emirates",
            "Saudi Arabia"
        ],
        "platforms": [
            "linkedin"
        ],
        "time_filters": [
            "24h",
            "week"
        ]
    },
    "scoring": {
        "review_above": 60,
        "skip_below": 60
    },
    "cv_mapping": {
        "default": "Muhammad_Tabish_CV.pdf"
    },
    "ai": {
        "groq_model": "openai/gpt-oss-120b",
        "gemini_model": "gemini-3.1-flash-lite",
        "enable_gemini": True,
        "enable_openrouter": False,
        "openrouter_model": "openrouter/free"
    },
    "notice_period": "1 month",
    "work_authorization": {
        "pakistan": True,
        "usa": False,
        "uk": False,
        "eu": False
    },
    "willing_to_relocate": True,
    "preferred_remote": True,
    "additional_context": "I have 2 years DevOps AWS and 1 year backend Node.js experience. Also have Docker and Kubernetes practice projects only (no production experience)."
}

def _init_config():
    if not os.path.exists(CONFIG_PATH):
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, "w") as f:
            yaml.dump(DEFAULT_CONFIG, f, default_flow_style=False, sort_keys=False)

_init_config()

def get_config() -> dict:
    with open(CONFIG_PATH, "r") as f:
        return yaml.safe_load(f)

def save_config(data: dict) -> None:
    with open(CONFIG_PATH, "w") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)
