import os
import random
import uuid
import logging
import asyncio
import httpx
import xml.etree.ElementTree as ET
import string
import json
import urllib.parse
from typing import List, Dict, Any, Optional
import sys

from scripts.scraper.sources.base import BaseSource
from scripts.scraper.core.config_loader import Config
from scripts.scraper.core.database import check_exists

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
from scripts.scraper.core.ai_router import call_llm

logger = logging.getLogger(__name__)

class TrendsSource(BaseSource):
    def __init__(self):
        # Global caches living in RAM
        self._google_trends = []  # Format: [{"title": str, "category": str|None, "used": bool}]
        self._wiki_trends = []    # Format: [{"title": str, "category": str|None, "used": bool}]
        self._wiki_chunk_offset = 0

    @property
    def source_type(self) -> str:
        return "trends"

    async def fetch(self, niche_name: str, niche_config: Dict[str, Any], count: int) -> List[Dict[str, str]]:
        config = Config.get_scraper_config()
        # Quality-First Defaults
        trends_config = config.get("trends_config", {
            "providers": ["google", "yt", "wiki"],
            "selection_mode": "sequential",
            "yt_seed_providers": ["google", "wiki"],
            "ignore_niches": False
        })

        ignore_niches = trends_config.get("ignore_niches", False)
        # Step 1: Configuration Resolution
        local_niche_name = "ANY" if ignore_niches else niche_name

        providers = trends_config.get("providers", ["google", "yt", "wiki"])
        selection_mode = trends_config.get("selection_mode", "sequential")
        
        # We need all niches for bulk AI filtering
        niches_dict = Config.get_niches()
        all_niches = list(niches_dict.keys())

        results = []

        if selection_mode == "random":
            selected_provider = random.choice(providers)
            stories = await self._execute_provider(selected_provider, local_niche_name, niche_config, all_niches, trends_config)
            if stories:
                results.extend(stories)
        else:
            # Sequential waterfall
            for provider in providers:
                stories = await self._execute_provider(provider, local_niche_name, niche_config, all_niches, trends_config)
                if stories:
                    results.extend(stories)
                    break # Break on first successful provider

        return results

    async def _execute_provider(self, provider: str, niche_name: str, niche_config: Dict[str, Any], all_niches: List[str], trends_config: Dict[str, Any]) -> List[Dict[str, str]]:
        if provider == "google":
            return await self._fetch_google(niche_name, niche_config, all_niches)
        elif provider == "wiki":
            return await self._fetch_wiki(niche_name, niche_config, all_niches)
        elif provider == "yt":
            return await self._fetch_yt(niche_name, niche_config, all_niches, trends_config)
        else:
            logger.error(f"Unknown trends provider: {provider}")
            return []

    async def _categorize_titles_with_ai(self, titles: List[str], all_niches: List[str]) -> Dict[str, str]:
        if not titles:
            return {}
        
        system_prompt = (
            "You are a categorization engine. Given a list of topic titles, categorize EACH title into exactly ONE of "
            "the provided niches. If it doesn't fit any, label it 'uncategorized'.\n"
            "Output valid JSON ONLY. Format: {\"Title 1\": \"Niche Name\", \"Title 2\": \"uncategorized\"}\n"
            f"Available niches: {json.dumps(all_niches)}"
        )
        user_prompt = f"Categorize these titles:\n{json.dumps(titles)}"
        
        try:
            response_text, _, _ = await call_llm(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                model_type="generator_model",
                temperature=0.1
            )
            # Find json boundaries if the model wraps it in markdown
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            return json.loads(response_text.strip())
        except Exception as e:
            # Fallback parsing if JSON is malformed
            cat_map = {}
            for line in response_text.split('\n'):
                if ':' in line:
                    parts = line.split(':', 1)
                    title = parts[0].strip(' ",\'{[')
                    cat = parts[1].strip(' ",\'}]')
                    if title and cat:
                        cat_map[title] = cat
            if cat_map:
                return cat_map
            logger.error(f"AI bulk categorization failed completely: {e} | Raw LLM Output: {response_text}")
            return {}

    # --- GOOGLE TRENDS ---
    
    async def _peek_google_seed(self, niche_name: str, all_niches: List[str]) -> List[str]:
        if not self._google_trends:
            # Download RSS
            try:
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get("https://trends.google.com/trending/rss?geo=US")
                    if resp.status_code == 200:
                        root = ET.fromstring(resp.text)
                        titles = []
                        for item in root.findall(".//item"):
                            title_elem = item.find("title")
                            if title_elem is not None:
                                titles.append(title_elem.text.strip())
                                if len(titles) >= 20:
                                    break
                                    
                        for t in titles:
                            self._google_trends.append({"title": t, "category": None, "used": False})
                        
                        # AI Bulk Categorize
                        cat_map = await self._categorize_titles_with_ai(titles, all_niches)
                        for item in self._google_trends:
                            item["category"] = cat_map.get(item["title"], "uncategorized")
            except Exception as e:
                logger.error(f"Failed to fetch Google Trends RSS: {e}")
                return []
                
        # Retrieval
        matches = []
        for item in self._google_trends:
            if not item["used"]:
                if niche_name == "ANY" or item["category"] == niche_name:
                    matches.append(item["title"])
        return matches

    async def _fetch_google(self, niche_name: str, niche_config: Dict[str, Any], all_niches: List[str]) -> List[Dict[str, str]]:
        matches = await self._peek_google_seed(niche_name, all_niches)
        if not matches:
            return []
            
        for title in matches:
            # Mark used in original array
            for item in self._google_trends:
                if item["title"] == title:
                    item["used"] = True
                    break
                    
            source_id = f"trends_google_{title.replace(' ', '_')}"
            if check_exists(source_id):
                continue
                
            # Text Generation
            logger.info(f"Generating Google Trends story for: {title}")
            story_dict = await self._generate_story(f"Write an engaging story about the trending topic: {title}", niche_config, source_id)
            if story_dict:
                return [story_dict]
        return []

    # --- WIKIPEDIA ---
    
    async def _peek_wiki_seed(self, niche_name: str, all_niches: List[str]) -> List[str]:
        if not self._wiki_trends:
            try:
                # Top 1000 articles of yesterday
                from datetime import datetime, timedelta
                yesterday = datetime.utcnow() - timedelta(days=1)
                date_str = yesterday.strftime("%Y/%m/%d")
                url = f"https://wikimedia.org/api/rest_v1/metrics/pageviews/top/en.wikipedia.org/all-access/{date_str}"
                
                async with httpx.AsyncClient(timeout=15.0) as client:
                    headers = {"User-Agent": "ShortsForge/1.0 (Contact: research@shortsforge.com)"}
                    resp = await client.get(url, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        articles = data.get("items", [{}])[0].get("articles", [])
                        
                        for a in articles:
                            t = a.get("article", "").replace("_", " ")
                            if not t.startswith("Wikipedia:") and not t.startswith("Special:") and t != "Main Page":
                                self._wiki_trends.append({"title": t, "category": None, "used": False})
                                if len(self._wiki_trends) >= 1000:
                                    break
            except Exception as e:
                logger.error(f"Failed to fetch Wikipedia Top 1000: {e}")
                return []

        # Advanced Pagination
        while self._wiki_chunk_offset < len(self._wiki_trends):
            # Check if we already have matches from previous chunks
            matches = []
            for item in self._wiki_trends:
                if not item["used"] and item["category"] is not None:
                    if niche_name == "ANY" or item["category"] == niche_name:
                        matches.append(item["title"])
            if matches:
                return matches

            # Fetch next chunk
            chunk = self._wiki_trends[self._wiki_chunk_offset : self._wiki_chunk_offset + 100]
            if not chunk:
                break
                
            self._wiki_chunk_offset += 100
            
            chunk_titles = [item["title"] for item in chunk]
            cat_map = await self._categorize_titles_with_ai(chunk_titles, all_niches)
            
            # Update Python references
            for item in chunk:
                item["category"] = cat_map.get(item["title"], "uncategorized")

        # Exhausted
        return []

    async def _fetch_wiki(self, niche_name: str, niche_config: Dict[str, Any], all_niches: List[str]) -> List[Dict[str, str]]:
        matches = await self._peek_wiki_seed(niche_name, all_niches)
        if not matches:
            return []
            
        for title in matches:
            for item in self._wiki_trends:
                if item["title"] == title:
                    item["used"] = True
                    break
                    
            source_id = f"trends_wiki_{title.replace(' ', '_')}"
            if check_exists(source_id):
                continue
                
            # Lazy text fetch
            try:
                url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(title.replace(' ', '_'))}"
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.get(url, follow_redirects=True)
                    if resp.status_code == 200:
                        data = resp.json()
                        raw_text = data.get("extract", "")
                        if not raw_text or len(raw_text.split()) < 30:
                            continue
                            
                        # Internal AI Rewrite
                        logger.info(f"Generating Wiki story for: {title}")
                        prompt = f"Rewrite this dry Wikipedia summary into an engaging, dramatic story:\n\n{raw_text}"
                        story_dict = await self._generate_story(prompt, niche_config, source_id)
                        if story_dict:
                            return [story_dict]
            except Exception as e:
                logger.error(f"Failed Wiki Summary API for {title}: {e}")
                
        return []

    # --- YOUTUBE AUTOCOMPLETE ---
    
    async def _fetch_yt(self, niche_name: str, niche_config: Dict[str, Any], all_niches: List[str], trends_config: Dict[str, Any]) -> List[Dict[str, str]]:
        seed_providers = trends_config.get("yt_seed_providers", ["google", "wiki"])
        
        gathered_seeds = []
        for sp in seed_providers:
            if sp == "google":
                gathered_seeds.extend(await self._peek_google_seed(niche_name, all_niches))
            elif sp == "wiki":
                gathered_seeds.extend(await self._peek_wiki_seed(niche_name, all_niches))
                
        # Remove duplicates
        gathered_seeds = list(set(gathered_seeds))
        
        # Shuffle for random variety
        random.shuffle(gathered_seeds)
        
        for seed in gathered_seeds:
            # Note: We do NOT set 'used' = True on the Google/Wiki items!
            story = await self._try_yt_seed(seed, niche_config)
            if story:
                return [story]
                
        # Final Niche Fallback
        if niche_name != "ANY":
            logger.info(f"YT exhausted all gathered seeds. Falling back to raw niche: {niche_name}")
            story = await self._try_yt_seed(niche_name, niche_config)
            if story:
                return [story]
                
        return []

    async def _try_yt_seed(self, seed: str, niche_config: Dict[str, Any]) -> Optional[Dict[str, str]]:
        # 1. Raw Seed First
        story = await self._yt_autocomplete_and_generate(seed, niche_config)
        if story:
            return story
            
        # 2. Alphabet Soup
        # Try up to 3 random letters
        letters = list(string.ascii_lowercase)
        random.shuffle(letters)
        
        for letter in letters[:3]:
            story = await self._yt_autocomplete_and_generate(f"{seed} {letter}", niche_config)
            if story:
                return story
                
        return None

    async def _yt_autocomplete_and_generate(self, query: str, niche_config: Dict[str, Any]) -> Optional[Dict[str, str]]:
        try:
            url = f"http://suggestqueries.google.com/complete/search?client=chrome&ds=yt&q={urllib.parse.quote(query)}"
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    try:
                        data = resp.json()
                    except UnicodeDecodeError:
                        import json
                        data = json.loads(resp.content.decode('latin-1'))
                        
                    suggestions = data[1] if len(data) > 1 else []
                    
                    if not suggestions:
                        return None
                        
                    # Shuffle to ensure variety
                    random.shuffle(suggestions)
                    
                    for phrase in suggestions:
                        source_id = f"trends_yt_{phrase.replace(' ', '_')}"
                        if check_exists(source_id):
                            continue
                            
                        logger.info(f"Generating YT story for phrase: {phrase}")
                        prompt = f"Write a captivating story specifically focused on the topic: '{phrase}'"
                        return await self._generate_story(prompt, niche_config, source_id)
        except Exception as e:
            logger.error(f"YT Autocomplete failed for query '{query}': {e}")
            
        return None

    # --- CENTRAL STORY GENERATOR ---
    
    async def _generate_story(self, specific_prompt: str, niche_config: Dict[str, Any], source_id: str) -> Optional[Dict[str, str]]:
        base_prompt = niche_config.get("ai_prompt", "Write a story.")
        
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
            "2. NEVER output stage directions, bracketed text, or audio cues. Output ONLY the spoken narrative.\n"
            f"3. The story should be roughly {target_length}."
        )
        
        user_prompt = f"{base_prompt}\n{specific_prompt}\nMake this one completely unique and different from typical stories. Add a shocking twist."
        
        try:
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
            
            return {
                "source_id": source_id,
                "title": title,
                "text": body
            }
        except Exception as e:
            logger.error(f"Centralized story generation failed for {source_id}: {e}")
            return None
