import os
import asyncio
import logging
from openai import AsyncOpenAI
from typing import Tuple
import re
from scripts.scraper.core.config_loader import Config
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from core.config import get_env
from core.content.ai_config import AI_PROVIDERS

logger = logging.getLogger(__name__)

FILTER_PROMPT = """
You are an automated content moderator. Your job is to filter out explicitly inappropriate content, while allowing creative fiction and drama to pass.
You must output ONLY "YES" or "NO", followed by a brief 1-sentence reason. Do not output anything else.

CRITICAL RULES:
1. ALLOW sci-fi, horror, crime, mystery, and fantasy themes (e.g., aliens, matrix, simulation, magic, murder, suicide in a plot context).
2. ALLOW relationship drama, revenge stories, and mentions of boyfriends/girlfriends/fiances, as long as they do not contain explicit intimacy.
3. REJECT any story that contains explicitly sexual content, sexually suggestive jokes, extreme vulgarity, or active mockery of religion.

If the story violates Rule 3, output NO.
Otherwise, output YES.

Story to evaluate:
{text}
"""

async def evaluate_content(title: str, text: str) -> Tuple[bool, str]:
    """
    Evaluates the content using the 8B model.
    Returns (True/False, "Reasoning").
    """
    config = Config.get_scraper_config()
    max_words = config.get("max_input_words_for_filter", 1500)
    
    # Truncate text strictly to prevent context limit explosion
    words = text.split()
    if len(words) > max_words:
        truncated_text = " ".join(words[:max_words])
    else:
        truncated_text = text
        
    prompt = FILTER_PROMPT.format(text=truncated_text)
    fallback_chain = config.get("ai_fallback_chain", ["gemini", "groq"])
    
    try:
        from scripts.scraper.core.ai_router import call_llm
        result, used_model, used_provider = await call_llm(
            messages=[{"role": "user", "content": prompt}],
            model_type="filter_model",
            temperature=0.0
        )
        
        # Log raw result to monitor future models/changes
        logger.debug(f"[AI Filter] Raw API response from {used_model}:\n{result}")
        
        # Parse YES or NO, stripping any <think> tags (e.g. from Qwen models)
        clean_result = re.sub(r'<think>.*?</think>', '', result, flags=re.DOTALL).strip()
        
        logger.debug(f"[AI Filter] Parsed clean response:\n{clean_result}")
        
        if clean_result.upper().startswith("NO"):
            reason = clean_result[2:].strip(" \n-:")
            logger.info(f"[AI Filter] Evaluated NO using {used_model} (Provider: {used_provider})")
            return False, reason
        elif clean_result.upper().startswith("YES"):
            reason = clean_result[3:].strip(" \n-:")
            logger.info(f"[AI Filter] Evaluated YES using {used_model} (Provider: {used_provider})")
            return True, reason
        else:
            logger.warning(f"Unexpected AI response format from {used_provider}: {result}")
            # If the response is garbage, we default to bypass
            return True, "Filter bypassed due to unexpected AI response."
            
    except Exception as e:
        logger.error(f"All AI providers failed the filter check: {e}. Bypassing filter to save the story.")
        return True, "Filter bypassed due to API limits."

def save_rejected_content(title: str, reason: str, text: str):
    """Saves rejected content if audit folder is enabled."""
    config = Config.get_scraper_config()
    if not config.get("enable_audit_folder", False):
        return
        
    base_dir = os.path.dirname(os.path.dirname(__file__))
    audit_dir = os.path.join(base_dir, "output", "filtered_out")
    os.makedirs(audit_dir, exist_ok=True)
    
    # Sanitize title for filename
    import re
    safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(" ", "_")[:50]
    file_path = os.path.join(audit_dir, f"{safe_title}.txt")
    
    content = f"REASON: {reason}\n\n=== ORIGINAL TEXT ===\n{text}"
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
