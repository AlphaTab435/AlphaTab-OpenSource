import os
import random
import uuid
import logging
import asyncio
from openai import AsyncOpenAI
from typing import List, Dict, Any
from scripts.scraper.sources.base import BaseSource
from scripts.scraper.core.config_loader import Config
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from core.config import get_env
from core.content.ai_config import AI_PROVIDERS

logger = logging.getLogger(__name__)

class AIGeneratorSource(BaseSource):
    @property
    def source_type(self) -> str:
        return "ai"
        
    async def fetch(self, niche_name: str, niche_config: Dict[str, Any], count: int) -> List[Dict[str, str]]:
        config = Config.get_scraper_config()
        fallback_chain = config.get("ai_fallback_chain", ["gemini", "groq"])
        base_prompt = niche_config.get("ai_prompt", f"Write a dramatic story about {niche_name}.")
        
        results = []
        for i in range(count):
            if niche_config.get("_is_shorts_only", False):
                target_length = "extremely short (100 to 140 words max) for a fast-paced YouTube Short. DO NOT EXCEED 140 WORDS!"
            else:
                lengths = [
                    "short (200 to 400 words) for a fast-paced YouTube Short",
                    "medium (600 to 900 words) for a standard YouTube video",
                    "long (1200 to 1800 words) for an extended deep-dive video"
                ]
                target_length = random.choice(lengths)
                
            system_prompt = (
                "You are an expert, creative storyteller writing engaging content for YouTube.\n"
                "CRITICAL RULES:\n"
                "1. Output ONLY the story text and a title. The first line MUST be the title (e.g. 'Title: My crazy story').\n"
                "2. NEVER output stage directions, bracketed text, or audio cues (e.g., [Ominous music plays]). Output ONLY the spoken narrative.\n"
                f"3. The story should be roughly {target_length}.\n"
                "4. Maintain a strong curiosity gap: do not reveal the twist or the core mystery until the final paragraph.\n"
                "5. Use visceral, sensory words instead of generic adjectives to keep the pacing fast and engaging."
            )
            user_prompt = f"{base_prompt}\nMake this one completely unique and different from typical stories. Add a shocking twist."
            
            try:
                from scripts.scraper.core.ai_router import call_llm
                text, used_model, used_provider = await call_llm(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt}
                    ],
                    model_type="generator_model",
                    temperature=0.9
                )
                
                lines = text.split("\n")
                title = lines[0].replace("Title:", "").strip()
                body = "\n".join(lines[1:]).strip()
                
                source_id = f"ai_{uuid.uuid4().hex[:8]}"
                results.append({
                    "source_id": source_id,
                    "title": title,
                    "text": body
                })
                logger.info(f"[AI Generator] Successfully generated story using {used_model} (Provider: {used_provider})")
            except Exception as e:
                logger.error(f"All AI providers failed or hit fatal limit for story {i+1}: {e}")
                break # Stop AI generation for this niche run
                
            # Sleep slightly to avoid blasting rate limits
            await asyncio.sleep(1)
                
        return results
