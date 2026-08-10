import os
import json
from typing import Dict, Any

CONFIG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "configs")

def load_json(filename: str) -> Dict[str, Any]:
    path = os.path.join(CONFIG_DIR, filename)
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing required config file: {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

class Config:
    _scraper_config = None
    _accounts = None
    _niches = None
    
    @classmethod
    def get_scraper_config(cls) -> Dict[str, Any]:
        if cls._scraper_config is None:
            cls._scraper_config = load_json("scraper_config.json")
        return cls._scraper_config

    @classmethod
    def get_accounts(cls) -> Dict[str, Any]:
        if cls._accounts is None:
            cls._accounts = load_json("accounts.json")
        return cls._accounts

    @classmethod
    def get_niches(cls) -> Dict[str, Any]:
        if cls._niches is None:
            cls._niches = load_json("niches.json")
        return cls._niches
