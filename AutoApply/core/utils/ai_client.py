import asyncio
import json
import os
from groq import AsyncGroq
from openai import AsyncOpenAI
import google.generativeai as genai
from loguru import logger

class AIClient:
    def __init__(self, config: dict):
        self.config = config
        self._groq_exhausted = False  # Set True when daily token limit (TPD) is hit
        self._gemini_exhausted = False
        self._openrouter_exhausted = False
        
        groq_key = os.getenv("GROQ_API_KEY")
        openrouter_key = os.getenv("OPENROUTER_API_KEY")
        gemini_key = os.getenv("GEMINI_API_KEY")
        
        if not groq_key:
            logger.warning("GROQ_API_KEY missing from .env")
        if not openrouter_key:
            logger.warning("OPENROUTER_API_KEY missing from .env")
        if not gemini_key and self.config.get("ai", {}).get("enable_gemini"):
            logger.warning("GEMINI_API_KEY missing from .env")
            
        self._groq = AsyncGroq(api_key=groq_key or "DUMMY")
        self._openrouter = AsyncOpenAI(
            api_key=openrouter_key or "DUMMY",
            base_url="https://openrouter.ai/api/v1"
        )
        if gemini_key:
            genai.configure(api_key=gemini_key)
            self._gemini = genai.GenerativeModel(self.config.get("ai", {}).get("gemini_model", "gemini-1.5-flash"))
        else:
            self._gemini = None


    async def ask(self, prompt: str, html_chunk: str = None, schema: dict = None) -> tuple[str | None, str]:
        if self._groq_exhausted and self._gemini_exhausted and self._openrouter_exhausted:
            return "ALL_QUOTAS_EXHAUSTED", "none"
            
        full = prompt + (f"\n\nHTML:\n{html_chunk[:8000]}" if html_chunk else "")
        
        # 1. Groq (Primary)
        result = await self._ask_groq(full, schema=schema)
        if result:
            return result, "groq"
            
        # 2. Gemini (Secondary)
        if self.config.get("ai", {}).get("enable_gemini", False) and not self._gemini_exhausted:
            logger.warning("Groq failed/exhausted — trying Gemini")
            result = await self._ask_gemini(full, schema=schema)
            if result:
                return result, "gemini"
                
        # 3. OpenRouter (Tertiary)
        if self.config.get("ai", {}).get("enable_openrouter", False) and not self._openrouter_exhausted:
            logger.warning("Gemini/Groq failed — trying OpenRouter")
            result = await self._ask_openrouter(full, schema=schema)
            if result:
                return result, "openrouter"

        if self._groq_exhausted and self._gemini_exhausted and not self.config.get("ai", {}).get("enable_openrouter", False):
            logger.warning("All enabled AI providers exhausted. Stopping.")
            return "ALL_QUOTAS_EXHAUSTED", "none"

        return None, "none"

    async def ask_json(self, prompt: str, html_chunk: str = None, schema: dict = None) -> dict | None:
        raw, provider = await self.ask(prompt, html_chunk, schema=schema)
        if raw == "ALL_QUOTAS_EXHAUSTED":
            return {"error": "ALL_QUOTAS_EXHAUSTED", "ai_provider": "none"}
        if not raw:
            return None
        try:
            text = raw.strip()
            if "```" in text:
                text = text.split("```")[1]
                if text.startswith("json"):
                    text = text[4:]
            parsed = json.loads(text.strip())
            parsed["ai_provider"] = provider
            return parsed
        except json.JSONDecodeError as e:
            # Fallback: try to extract JSON block using regex if model included extra text
            import re
            match = re.search(r'(\{.*\})', raw, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group(1))
                    parsed["ai_provider"] = provider
                    return parsed
                except json.JSONDecodeError:
                    pass
            logger.error(f"JSON parse failed: {e} | Raw: {raw[:200]}")
            return None

    async def _ask_groq(self, prompt: str, schema: dict = None) -> str | None:
        # Skip Groq entirely if daily token limit was already hit this session
        if self._groq_exhausted:
            return None

        kwargs = {
            "model": self.config["ai"]["groq_model"],
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2000
        }
        if schema:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            r = await self._groq.chat.completions.create(**kwargs)
            return r.choices[0].message.content
        except Exception as e:
            err_str = str(e)

            # Check if this is a daily token limit (TPD) exhaustion
            if "tokens per day" in err_str.lower() or "tpd" in err_str.lower():
                self._groq_exhausted = True
                logger.warning("Groq daily token limit hit — routing all remaining jobs directly to OpenRouter")
                return None

            if "429" in err_str:
                logger.warning("Groq rate limited — waiting 70s")
                await asyncio.sleep(70)
                try:
                    r = await self._groq.chat.completions.create(**kwargs)
                    return r.choices[0].message.content
                except Exception as e2:
                    self._groq_exhausted = True
                    logger.warning(f"Groq retry failed after 70s ({e2}). Marking exhausted for rest of run.")
                    return None
            logger.error(f"Groq error: {e}")
            return None

    async def _ask_gemini(self, prompt: str, schema: dict = None) -> str | None:
        if self._gemini_exhausted or not self._gemini:
            return None
            
        generation_config = genai.GenerationConfig(
            response_mime_type="application/json" if schema else "text/plain",
        )
        
        gemini_prompt = prompt
        if schema:
            gemini_prompt += f"\n\nYou MUST return ONLY valid JSON matching this schema:\n{json.dumps(schema, indent=2)}"

        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                # 15 RPM = 4s per request
                await asyncio.sleep(4.1) 
                
                response = await self._gemini.generate_content_async(
                    gemini_prompt,
                    generation_config=generation_config
                )
                return response.text
            except Exception as e:
                err_str = str(e).lower()
                if "429" in err_str or "quota" in err_str:
                    if "quota" in err_str and "exceeded" in err_str:
                        self._gemini_exhausted = True
                        logger.warning("Gemini daily limit hit. Marking exhausted.")
                        return None
                    
                    delay = 70
                    logger.warning(f"Gemini rate limited — waiting {delay}s")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"Gemini error: {e}")
                    return None
        return None

    async def _ask_openrouter(self, prompt: str, schema: dict = None) -> str | None:
        if self._openrouter_exhausted:
            return None
            
        kwargs = {
            "model": self.config["ai"]["openrouter_model"],
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 2000
        }
        if schema:
            kwargs["response_format"] = {"type": "json_schema", "json_schema": schema}
            
        max_retries = 2
        for attempt in range(max_retries + 1):
            try:
                r = await self._openrouter.chat.completions.create(**kwargs)
                return r.choices[0].message.content
            except Exception as e:
                err_str = str(e)
                if "free-models-per-day" in err_str.lower():
                    self._openrouter_exhausted = True
                    logger.warning("OpenRouter daily limit hit. Marking exhausted for rest of run.")
                    return None
                
                if "429" in err_str and attempt < max_retries:
                    delay = 10 * (attempt + 1)
                    logger.warning(f"OpenRouter rate limited — waiting {delay}s")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"OpenRouter error: {e}")
                    return None
        return None
