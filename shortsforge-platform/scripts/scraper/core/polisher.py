import os
import sys
import logging
from typing import Tuple
from openai import AsyncOpenAI
import random

# Ensure core platform imports work
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from core.config import get_env
from core.content.ai_config import AI_PROVIDERS
from scripts.scraper.core.config_loader import Config

logger = logging.getLogger(__name__)

async def polish_content(original_title: str, text: str, source_type: str) -> Tuple[bool, str, str]:
    """
    Takes a raw, unpolished text from SCP/Public Domain, truncates it to fit AI limits,
    and uses the robust fallback chain to rewrite it into a viral 600-word YouTube script.
    
    Returns: (success_bool, new_title, polished_text)
    """
    config = Config.get_scraper_config()
    fallback_chain = config.get("ai_fallback_chain", ["gemini", "groq"])
    
    # Truncate text strictly to prevent context limit explosion (approx 2500 words)
    words = text.split()
    if len(words) > 2500:
        truncated_text = " ".join(words[:2500])
    else:
        truncated_text = text
        
    system_prompt = (
        "You are an expert, creative YouTube scriptwriter.\n"
        "Read the following raw, dry document and rewrite it into a highly creative, "
        "dramatic, and engaging spoken YouTube script.\n"
        "CRITICAL RULES:\n"
        "1. The first line MUST be a highly clickable, viral YouTube Title (e.g., 'Title: The Dark Origin of X').\n"
        "2. DO NOT include stage directions, bracketed text, or visual/audio cues (e.g., [Ominous music]). Output ONLY the spoken narrative.\n"
        "3. Focus entirely on the core narrative. Discard unrelated metadata, reference lists, or dry formatting. The length of your script should be naturally proportional to the amount of actual story substance provided—if the source has deep lore, write a detailed, lengthy script; if the source is brief, provide a shorter, highly optimized script without unnecessary filler."
    )
    
    user_prompt = f"Original Title Reference: {original_title}\n\nRaw Document:\n{truncated_text}"

    try:
        from scripts.scraper.core.ai_router import call_llm
        content, used_model, used_provider = await call_llm(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            model_type="generator_model",
            max_tokens=2000,
            temperature=0.8
        )
        
        # Parse the title from the first line
        lines = content.split('\n')
        new_title = original_title
        polished_text = content
        
        if lines:
            first_line = lines[0].strip()
            if first_line.lower().startswith("title:"):
                # Extract title and remove quotes if they exist
                raw_title = first_line[6:].strip().strip('"').strip("'").strip('*')
                if raw_title:
                    new_title = raw_title
                # The rest of the lines form the polished text
                polished_text = "\n".join(lines[1:]).strip()
        
        logger.info(f"[AI Polisher] Successfully polished story into: '{new_title}' using {used_provider}")
        return True, new_title, polished_text
        
    except Exception as e:
        logger.error(f"[AI Polisher] All AI providers failed to polish '{original_title}': {str(e)}. Discarding.")
        return False, "", ""
