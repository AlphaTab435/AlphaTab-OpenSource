import os
import time
import logging
import asyncio
from openai import AsyncOpenAI, RateLimitError
from typing import Tuple

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from core.config import get_env
from core.content.ai_config import AI_PROVIDERS
from scripts.scraper.core.config_loader import Config

logger = logging.getLogger(__name__)

# State: {"groq": {"strikes": 0, "wake_up_time": 0}, ...}
PROVIDER_STATUS = {}

def _init_status():
    config = Config.get_scraper_config()
    fallback_chain = config.get("ai_fallback_chain", ["groq", "gemini", "cerebras"])
    for provider in fallback_chain:
        if provider not in PROVIDER_STATUS:
            PROVIDER_STATUS[provider] = {"strikes": 0, "wake_up_time": 0}

async def call_llm(messages: list, model_type: str = "generator_model", **kwargs) -> Tuple[str, str, str]:
    """
    Routes the AI request through the fallback chain using the Circuit Breaker logic.
    Handles RPM (429) cooldowns via Timestamps and blocks if all are sleeping.
    Returns: (content_text, model_name, provider_name)
    """
    _init_status()
    config = Config.get_scraper_config()
    fallback_chain = config.get("ai_fallback_chain", ["groq", "gemini", "cerebras"])
    
    while True: # Keep trying until success or fatal error
        # 1. Check if ALL providers are sleeping
        all_sleeping = True
        for provider in fallback_chain:
            if time.time() >= PROVIDER_STATUS.get(provider, {}).get("wake_up_time", 0):
                all_sleeping = False
                break
                
        if all_sleeping:
            lowest_wake_up = float('inf')
            for provider in fallback_chain:
                wake_time = PROVIDER_STATUS.get(provider, {}).get("wake_up_time", 0)
                if wake_time < lowest_wake_up:
                    lowest_wake_up = wake_time
            
            if lowest_wake_up == float('inf'):
                logger.error("FATAL: All AI providers in fallback chain have hit their 3-strike daily limits!")
                raise RuntimeError("All AI providers exhausted their daily/hourly limits.")
                
            sleep_duration = lowest_wake_up - time.time()
            if sleep_duration > 0:
                logger.warning(f"[CIRCUIT BREAKER] All AI providers are in cooldown. Pausing for {sleep_duration:.1f}s...")
                await asyncio.sleep(sleep_duration)
        
        # 2. Try the Fallback Chain
        for provider in fallback_chain:
            status = PROVIDER_STATUS.get(provider, {"strikes": 0, "wake_up_time": 0})
            
            if time.time() < status["wake_up_time"]:
                continue # Skip, still sleeping
                
            provider_config = AI_PROVIDERS.get(provider)
            if not provider_config:
                continue
                
            env_key_name = f"{provider.upper()}_API_KEY"
            api_key = get_env(env_key_name)
            if not api_key:
                continue
                
            base_url = provider_config.get("api_base")
            if provider == "gemini":
                base_url = "https://generativelanguage.googleapis.com/v1beta/openai/"
                
            scraper_provider_conf = config.get("ai_providers", {}).get(provider, {})
            model_name = scraper_provider_conf.get(model_type, provider_config.get("default_model"))
            
            client = AsyncOpenAI(api_key=api_key, base_url=base_url)
            
            try:
                response = await client.chat.completions.create(
                    model=model_name,
                    messages=messages,
                    **kwargs
                )
                
                content = response.choices[0].message.content.strip()
                if not content:
                    logger.error(f"[{provider}] Returned empty content.")
                    continue
                    
                # Success! Reset strikes
                PROVIDER_STATUS[provider]["strikes"] = 0
                return content, model_name, provider
                
            except RateLimitError as e:
                logger.warning(f"[{provider}] RateLimitError (429) hit!")
                PROVIDER_STATUS[provider]["strikes"] += 1
                if PROVIDER_STATUS[provider]["strikes"] >= 3:
                    logger.error(f"[{provider}] 3rd strike! Assuming Daily Limit. Marking permanently DEAD.")
                    PROVIDER_STATUS[provider]["wake_up_time"] = float('inf')
                else:
                    logger.warning(f"[{provider}] Strike {PROVIDER_STATUS[provider]['strikes']}/3. Cooldown for 60s.")
                    PROVIDER_STATUS[provider]["wake_up_time"] = time.time() + 60
                continue
                
            except Exception as e:
                error_msg = str(e)
                if "429" in error_msg:
                    logger.warning(f"[{provider}] String 429 RateLimit hit!")
                    PROVIDER_STATUS[provider]["strikes"] += 1
                    if PROVIDER_STATUS[provider]["strikes"] >= 3:
                        logger.error(f"[{provider}] 3rd strike! Marking permanently DEAD.")
                        PROVIDER_STATUS[provider]["wake_up_time"] = float('inf')
                    else:
                        logger.warning(f"[{provider}] Strike {PROVIDER_STATUS[provider]['strikes']}/3. Cooldown for 60s.")
                        PROVIDER_STATUS[provider]["wake_up_time"] = time.time() + 60
                else:
                    logger.error(f"[{provider}] Generic API Error (Skipping for this request only): {error_msg}")
                    # Do NOT add strike, do NOT ban.
                continue
