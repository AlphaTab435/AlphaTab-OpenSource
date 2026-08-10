import os
import re
import json
import logging
import asyncio
import random
from typing import Dict, Any, List
from google import genai
from core.config import get_env
from openai import AsyncOpenAI
from core.content.ai_config import AI_PROVIDERS, FALLBACK_CHAIN

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Constants based on roughly 150 words per minute of speaking
WORDS_PER_MINUTE = 150
WORDS_PER_AI_SCENE = 1000  # AI processing window to avoid context/output limits

HOOK_PROMPT = """
You are an expert storytelling editor. 
Extract the most shocking or interesting revelation from this story intro and make it a short, punchy, and attention-capturing HOOK (Max 15 words).
CRITICAL: ONLY output the hook string. Do not use quotes or introductory text.
The final hook MUST be written in {target_language}. If the input text is in a different language, translate it accurately to {target_language}.

Raw Story Intro:
{text}
"""

GRAMMAR_PROMPT = """
You are an expert copyeditor and translator. Clean up the grammar and pacing of this text so it is easy to read aloud by a Text-to-Speech narrator.
CRITICAL INSTRUCTIONS:
1. Do NOT summarize or shorten the plot. Keep the exact same narrative and story beats.
2. The final output MUST be written in {target_language}. If the input text is in a different language, translate it accurately to {target_language}.
3. Simplify complex vocabulary and remove all idioms, metaphors, and colloquialisms. Rewrite difficult sentences so they are extremely literal and easy to understand.
4. NEVER output stage directions, bracketed text, or audio cues (e.g., [Ominous music plays]). Output ONLY the spoken narrative.
5. Return ONLY the edited/translated text. Do not include markdown or conversational replies.

Text:
{text}
"""

SANITIZATION_PROMPT = """
You are a text sanitizer. Clean up this text so it can be safely read by a Text-to-Speech engine without crashing.
CRITICAL INSTRUCTIONS:
1. Do NOT change the vocabulary, idioms, perspective, or sentence structure. Keep the exact words.
2. Fix obvious spelling typos, but preserve the author's voice and tone completely.
3. Strip out ALL markdown formatting (like asterisks, bold, italics, hashtags, or HTML tags) so the TTS engine doesn't read them aloud.
4. Remove weird symbols, bracketed text, stage directions, or emojis.
5. Return ONLY the sanitized spoken narrative text. Do not include markdown or conversational replies.

Text:
{text}
"""

DESC_PROMPT = """
You are an expert YouTube SEO specialist. Write a gripping 2 to 3 paragraph YouTube description summarizing this story.
CRITICAL INSTRUCTIONS:
1. Make it suspenseful and compelling, but DO NOT spoil the ending.
2. Include highly searched, relevant SEO keywords naturally within the text.
3. The total length MUST be between 1000 and 1500 characters.
4. Include 3 to 5 highly relevant hashtags at the very bottom of the description.
5. Return ONLY the description text. Do not include markdown or conversational replies.
6. The description MUST be completely written in English, regardless of the input text language.

Raw Story Intro:
{text}
"""

SHORTS_PROMPT = """
You are an expert YouTube Shorts creator. Turn this interesting scene into a punchy teaser script for a YouTube Short.
CRITICAL RULES:
1. Cut all slow exposition. Start "in media res" (in the middle of the action).
2. The script MUST NOT exceed 350 words. You have the freedom to make it anywhere from 30 seconds to 2.5 minutes long.
3. The final output MUST be written in {target_language}. If the input text is in a different language, translate it accurately to {target_language}.
4. Do NOT use the phrase "to be continued".
5. NEVER output stage directions, bracketed text, or audio cues. Output ONLY the spoken narrative.
6. Maintain a strong curiosity gap. Use visceral, sensory words to maximize engagement.

Scene:
{text}
"""

IMAGE_PROMPT = """
You are an expert image researcher. Your job is to read a short scene from a video script and provide a generic, completely safe, and non-explicit background search query (e.g., 'cinematic dark server room interior' or 'abandoned warehouse') to find the perfect background image for this scene on DuckDuckGo.
CRITICAL: The search query MUST be completely safe for work (SFW). Do not include any violent, graphic, or explicit terms, even if the scene is dark.
CRITICAL: The search query MUST be completely written in English, regardless of the input text language.
DO NOT use quotes, just output the raw query. Do not write anything else.
Focus on the main physical noun/subject and the atmosphere. 

Scene:
{text}
"""

SAFE_BG_PROMPT = """
You are an expert image researcher. Read the following story intro and extract a generic, completely safe, and non-explicit background search query (e.g., 'cinematic dark server room interior' or 'abandoned warehouse') that captures the atmosphere of the story.
CRITICAL: The search query MUST be completely safe for work (SFW). Do not include any violent, graphic, or explicit terms.
CRITICAL: The search query MUST be completely written in English, regardless of the input text language.
DO NOT use quotes, just output the raw query. Do not write anything else.

Story Intro:
{text}
"""

GENDER_PROMPT = """
You are an expert linguistics analyzer. Read this story intro and determine if the protagonist or narrator is best represented by a male or female voice.
CRITICAL INSTRUCTIONS:
1. Output ONLY the English word "male" or "female". 
2. Do not include quotes, punctuation, or explanations.
3. If it is ambiguous, guess based on context or default to "male".
4. Even if the text is in another language (like Russian or Urdu), your output MUST be the English word "male" or "female".

Story Intro:
{text}
"""

ROMAN_URDU_PROMPT = """
Translate the following short hook into Roman Urdu (Urdu written in English alphabets, exactly how modern Pakistani college students speak and type).
CRITICAL: Output ONLY the translated string. No quotes, no intro text.
If the text contains English words, preserve them naturally in the Roman Urdu flow.

Hook:
{text}
"""

URDU_HOOK_PROMPT = """
You are an expert storytelling editor. 
Extract the most shocking or interesting revelation from this story intro and make it a short, punchy, and attention-capturing HOOK (Max 15 words).
CRITICAL RULES:
1. ONLY output the hook string. Do not use quotes or introductory text.
2. The hook MUST be translated into "Roman Urdu" (Urdu written in the English alphabet).
3. Do NOT write in formal or pure Urdu. Write exactly how a modern Pakistani college student speaks to their friends.
4. HEAVY ENGLISH MIX: Keep all nouns, verbs, slang, and key phrases in English!
5. Keep it highly informal, conversational, and dramatic.

Raw Story Intro:
{text}
"""

URDU_GRAMMAR_PROMPT = """
You are an expert bilingual Gen-Z storyteller from Pakistan. Your job is to take a raw text chunk and rewrite/translate it to be extremely captivating, fast-paced, and engaging.
CRITICAL INSTRUCTIONS:
1. Do NOT summarize or shorten the plot. Keep the exact same narrative and story beats.
2. Translate the text into "Roman Urdu" (Urdu written with English alphabets).
3. Do NOT write in formal or pure Urdu. Write exactly how a modern Pakistani college student speaks to their friends (highly informal, conversational, and dramatic).
4. HEAVY ENGLISH MIX: Keep all nouns, verbs, slang, and key phrases in English! Words like 'University', 'Crush', 'Roommate', 'Ice Prince', 'FaceTime', 'Weird', 'Awkward', 'Literally', 'Actually', 'Wait' MUST remain in English.
5. Keep the storytelling incredibly engaging, using filler words like 'Yaar', 'Kasam se', 'Matlab', 'Scene yeh tha'.
6. NEVER output stage directions, bracketed text, or audio cues. Output ONLY the translated story. Do not include markdown or conversational replies.

Text:
{text}
"""

URDU_SHORTS_PROMPT = """
You are an expert bilingual Gen-Z YouTube Shorts creator from Pakistan. Turn this interesting scene into a punchy teaser script for a YouTube Short.
CRITICAL RULES:
1. Cut all slow exposition. Start "in media res" (in the middle of the action).
2. The script MUST NOT exceed 350 words. You have the freedom to make it anywhere from 30 seconds to 2.5 minutes long.
3. Translate the text into "Roman Urdu" (Urdu written with English alphabets).
4. Do NOT write in formal or pure Urdu. Write exactly how a modern Pakistani college student speaks to their friends (highly informal, conversational, and dramatic).
5. HEAVY ENGLISH MIX: Keep all nouns, verbs, slang, and key phrases in English!
6. Keep the storytelling incredibly engaging, using filler words like 'Yaar', 'Kasam se', 'Matlab', 'Scene yeh tha'.
7. Do NOT use the phrase "to be continued".
8. NEVER output stage directions, bracketed text, or audio cues. Output ONLY the spoken narrative.
9. Maintain a strong curiosity gap. Use visceral, sensory words to maximize engagement.

Scene:
{text}
"""

INFOGRAPHIC_PROMPT = """
You are an expert video producer and infographic designer. Convert the following narrative into a JSON data structure for an automated infographic animation engine.
CRITICAL INSTRUCTIONS:
1. Scene Layout: Break the narrative into 2 to 4 distinct scenes. Each scene clears the screen with a fresh `bg_color` and `accent_color`.
2. For each scene, pick a dark `bg_color` (e.g. #0d0d0d) and a vibrant `accent_color` (e.g. #ff0055). Vary colors across scenes!
3. Visual node types:
   - `icon`: MUST be one of these EXACT valid keywords: [zap, shield, trending-up, trending-down, heart, star, cloud, cloud-lightning, eye, key, brain, lock, unlock, check-circle, alert-triangle, flame, rocket, crosshair, target, wifi, server, database, globe, smartphone, laptop, users, user, activity, mic, camera, video, music, tv, film, image, map, compass, bell, message-circle, send, mail, clock, pie-chart, bar-chart, dollar-sign, shopping-cart, award, briefcase, folder, file, link, scissors, copy, trash, edit, box, package, truck, anchor, map-pin, cpu, hard-drive, monitor, printer, mouse, keyboard, speaker, bluetooth, cast, power, moon, sun, wind, droplet, umbrella, thumbs-up, thumbs-down, smile, settings, tool, wrench, hammer, search, download, upload, check, plus, minus, x, cctv, shield-alert]. (Reference: https://lucide.dev/icons).
     CRITICAL: Icons MUST perfectly match the semantic meaning of the text. For example, if text mentions 'surveillance', use `camera` or `eye`. Do NOT choose loose or unrelated metaphors.
   - `bubble`: A speech bubble with short text. Use sparingly for HIGH-IMPACT quotes only. Do NOT use it for random words.
   - `arrow`: A dashed line with pointed arrowhead connecting two populated slots.
   - `line`: A dashed line with circular dots at both ends connecting two populated slots.
   - `slot`: MUST be one of: 'top', 'bottom', 'left', 'right', 'center'.
4. VARIETY IS CRITICAL: Each scene MUST feel visually different. Mix these patterns across scenes:
   - Scene with 2 icons on left and right (showing contrast or relationship)
   - Scene with 1 centered icon and a bubble
   - Scene with 2 icons connected by a line or arrow
   - Scene with just 1 bold centered icon (dramatic moment)
   Do NOT repeat the same pattern in consecutive scenes. Arrows and lines are STRICTLY OPTIONAL. ONLY use an arrow if there is a literal transfer or movement from one object to another (e.g. data moving from server to user). NEVER connect unrelated icons just for the sake of it.
5. 5-Word Window Rule: The viewer reads about 5 words on screen at a time. Pace visual nodes so that each icon, arrow, or bubble appears only when its `sync_word` is currently visible. Do NOT cluster multiple icons at the same timestamp. Space them out so each one gets its moment on screen. This makes visuals feel alive and engaging.
6. Balance: Spread icons logically across the 5 slots (center, left, right, top, bottom). If there is only one visual, put it in `center`. If the text mentions multiple visual concepts within the same scene, assign them to DIFFERENT slots and stagger their `sync_word` timing.
7. Timing: Nodes MUST appear sequentially as their `sync_word` is spoken. Arrows must appear AFTER both icons exist.
8. `thumbnail_icon`: A metaphorical icon representing the whole video.
9. Return ONLY valid, minified JSON. Do NOT include markdown blocks. You MUST use the EXACT text from the narrative. Do NOT summarize or change the text.

JSON SCHEMA (showing 3 diverse scene patterns):
{{
  "template": "infographic",
  "thumbnail_icon": "zap",
  "scenes": [
    {{
      "id": "scene1",
      "text": "Exact text from the narrative for this scene.",
      "duration_sec": 5.0,
      "bg_color": "#0d0d0d",
      "accent_color": "#ff0055",
      "visual_nodes": [
        {{ "type": "icon", "keyword": "server", "slot": "left", "animation": "pop", "sync_word": "server" }},
        {{ "type": "icon", "keyword": "shield", "slot": "right", "animation": "pop", "sync_word": "security" }},
        {{ "type": "line", "from_slot": "left", "to_slot": "right", "animation": "draw", "sync_word": "protects" }}
      ]
    }},
    {{
      "id": "scene2",
      "text": "Exact text from the narrative for this scene.",
      "duration_sec": 6.0,
      "bg_color": "#0d0d0d",
      "accent_color": "#00ffcc",
      "visual_nodes": [
        {{ "type": "icon", "keyword": "rocket", "slot": "center", "animation": "pop", "sync_word": "launch" }},
        {{ "type": "bubble", "text": "Go!", "slot": "top", "animation": "fade", "sync_word": "go" }}
      ]
    }},
    {{
      "id": "scene3",
      "text": "Exact text from the narrative for this scene.",
      "duration_sec": 5.0,
      "bg_color": "#0d0d0d",
      "accent_color": "#ffcc00",
      "visual_nodes": [
        {{ "type": "icon", "keyword": "flame", "slot": "center", "animation": "pop", "sync_word": "fire" }}
      ]
    }}
  ]
}}

Narrative:
{text}
"""


class StoryEditor:
    """Handles Mathematical Chunking and JIT AI Processing."""
    
    def __init__(self, custom_fallback_chain=None, custom_models=None):
        self.fallback_chain = custom_fallback_chain or FALLBACK_CHAIN
        self.custom_models = custom_models or {}
        
        # Setup AI Clients
        self.clients = {}
        for provider in self.fallback_chain:
            api_key_name = f"{provider.upper()}_API_KEY"
            api_key = get_env(api_key_name, required=False)
            if api_key:
                if provider == "gemini":
                    self.clients[provider] = genai.Client(api_key=api_key)
                else:
                    api_base = AI_PROVIDERS[provider].get("api_base")
                    self.clients[provider] = AsyncOpenAI(api_key=api_key, base_url=api_base)

    async def _call_llm(self, prompt: str) -> str:
        """Calls LLM with graceful fallback. Throws exception if all fail."""
        for provider in self.fallback_chain:
            if provider not in self.clients:
                continue
            client = self.clients[provider]
            model = self.custom_models.get(provider, AI_PROVIDERS.get(provider, {}).get("default_model"))
            try:
                if provider == "gemini":
                    response = await client.aio.models.generate_content(model=model, contents=prompt)
                    logger.info(f"AI SUCCESS: Successfully generated content using {provider} ({model})")
                    return response.text.strip()
                else:
                    response = await client.chat.completions.create(
                        model=model,
                        messages=[{"role": "user", "content": prompt}],
                        temperature=0.7,
                    )
                    logger.info(f"AI SUCCESS: Successfully generated content using {provider} ({model})")
                    return response.choices[0].message.content.strip()
            except Exception as e:
                logger.warning(f"AI FALLBACK TRIGGERED: Provider '{provider}' failed ({e}). Moving to next fallback.")
            finally:
                try:
                    await client.aclose()
                except Exception:
                    pass
        raise ValueError("All AI providers in the fallback chain failed.")

    async def extract_global_hook(self, raw_text: str, fallback_topic: str = "Story", target_language: str = "English") -> str:
        """Extracts a global hook from the first 1000 words."""
        words = raw_text.split()
        intro_text = " ".join(words[:1000])
        try:
            if target_language == "ur":
                hook = await self._call_llm(URDU_HOOK_PROMPT.format(text=intro_text))
            else:
                hook = await self._call_llm(HOOK_PROMPT.format(text=intro_text, target_language=target_language))
            return hook
        except Exception as e:
            logger.error(f"FALLBACK: Global hook extraction failed ({e}). Using story title as hook.")
            return fallback_topic

    async def extract_description(self, raw_text: str) -> str:
        """Extracts a 1000-1500 char YouTube description using AI, with a fallback."""
        words = raw_text.split()
        intro_text = " ".join(words[:2000]) # Give AI plenty of context to summarize
        try:
            desc = await self._call_llm(DESC_PROMPT.format(text=intro_text))
            if len(desc) > 2000:
                desc = desc[:1997] + "..."
            return desc.strip()
        except Exception as e:
            logger.error(f"FALLBACK: Description extraction failed ({e}). Generating standard description.")
            fallback_text = " ".join(words[:60])
            fallback_text = fallback_text.strip() + "...\n\nWatch the full story to find out! Make sure to like, comment, and subscribe for more."
            return fallback_text

    async def extract_safe_background_query(self, raw_text: str, fallback_topic: str) -> str:
        """Extracts a safe search query for global backgrounds."""
        words = raw_text.split()
        intro_text = " ".join(words[:500])
        try:
            query = await self._call_llm(SAFE_BG_PROMPT.format(text=intro_text))
            return query.strip()
        except Exception as e:
            logger.error(f"FALLBACK: Safe BG extraction failed ({e}). Using fallback topic.")
            return fallback_topic

    def pre_chunk_mathematically(self, raw_text: str, target_mins: int = 60, min_mins: int = 30, balanced: bool = False) -> List[Dict[str, Any]]:
        """
        Mathematically chops text into target_duration blocks.
        
        When balanced=False (Long Videos): Uses hard cutoff + Orphan Chunk Merger.
        When balanced=True (Shorts-Only): Calculates ideal number of chunks, then divides
            text evenly across all parts so no chunk is too large or too small.
        
        Both modes always cut at sentence boundaries (never mid-sentence).
        """
        # Clean weird formatting
        clean_text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', raw_text)
        clean_text = clean_text.replace('*', '').replace('_', '').replace('~', '')
        
        words = clean_text.split()
        target_words = target_mins * WORDS_PER_MINUTE
        min_words = min_mins * WORDS_PER_MINUTE
        
        if balanced:
            # Smart Balancer: divide text evenly across N parts
            import math
            total_words = len(words)
            
            if total_words <= target_words:
                # Fits in a single chunk, no splitting needed
                num_chunks = 1
            else:
                num_chunks = math.ceil(total_words / target_words)
            
            # Balanced per-chunk target (evenly divided)
            balanced_target = total_words / num_chunks
            logger.info(f"Smart Balancer: {total_words} words -> {num_chunks} chunks @ ~{int(balanced_target)} words each")
            
            chunks = []
            current_chunk = []
            
            for word in words:
                current_chunk.append(word)
                # Cut at sentence boundary once we reach or exceed the balanced target
                if len(current_chunk) >= balanced_target and word.endswith(('.', '?', '!', '"', "'")):
                    chunks.append(" ".join(current_chunk))
                    current_chunk = []
                    
            # Append any remaining words
            if current_chunk:
                # If leftovers are very small (< 20% of balanced target) and we already have chunks,
                # merge them into the last chunk to avoid a tiny trailing part
                if chunks and len(current_chunk) < balanced_target * 0.2:
                    logger.info(f"Smart Balancer: Merging tiny remainder ({len(current_chunk)} words) into previous chunk.")
                    chunks[-1] = chunks[-1] + " " + " ".join(current_chunk)
                else:
                    chunks.append(" ".join(current_chunk))
        else:
            # Original Long Video chunking (unchanged)
            chunks = []
            current_chunk = []
            
            for word in words:
                current_chunk.append(word)
                # Cut cleanly at sentences if we hit the target word limit
                if len(current_chunk) >= target_words and word.endswith(('.', '?', '!', '"', "'")):
                    chunks.append(" ".join(current_chunk))
                    current_chunk = []
                    
            if current_chunk:
                chunks.append(" ".join(current_chunk))
                
            # Orphan Chunk Merger Math
            if len(chunks) > 1:
                last_chunk_words = len(chunks[-1].split())
                if last_chunk_words < min_words:
                    logger.info(f"Orphan Chunk Merger triggered! Merging final {last_chunk_words} words into previous chunk.")
                    orphaned_text = chunks.pop()
                    chunks[-1] = chunks[-1] + " " + orphaned_text
                
        # Format for JSON Cache
        formatted_chunks = []
        for idx, text in enumerate(chunks, 1):
            formatted_chunks.append({
                "chunk_id": idx,
                "status": "pending",
                "raw_text": text,
                "ai_text": None
            })
            
        return formatted_chunks

    async def process_ai_grammar(self, raw_text: str, bypass_grammar: bool = False, target_language: str = "English") -> str:
        """
        JIT AI Processing with Graceful Degradation.
        Chops raw_text into 1000-word scenes to prevent context crashes, edits them, and stitches them.
        If bypass_grammar is True, it uses the SANITIZATION_PROMPT to preserve exact wording.
        """
        words = raw_text.split()
        scenes = []
        current_scene = []
        
        # Split into 1000-word scenes at sentence boundaries
        for word in words:
            current_scene.append(word)
            if len(current_scene) >= WORDS_PER_AI_SCENE and word.endswith(('.', '?', '!', '"', "'")):
                scenes.append(" ".join(current_scene))
                current_scene = []
        if current_scene:
            scenes.append(" ".join(current_scene))
            
        processed_scenes = []
        for i, scene in enumerate(scenes):
            try:
                # Add delay to prevent rate limits
                if i > 0:
                    await asyncio.sleep(2)
                if bypass_grammar:
                    ai_edited = await self._call_llm(SANITIZATION_PROMPT.format(text=scene))
                else:
                    if target_language == "ur":
                        ai_edited = await self._call_llm(URDU_GRAMMAR_PROMPT.format(text=scene))
                    else:
                        ai_edited = await self._call_llm(GRAMMAR_PROMPT.format(text=scene, target_language=target_language))
                processed_scenes.append(ai_edited)
            except Exception as e:
                logger.error(f"CRITICAL AI FAILURE for scene {i} ({e}).")
                logger.error("GRACEFUL DEGRADATION: Bypassing AI entirely and falling back to RAW TEXT for this scene to prevent pipeline stoppage.")
                processed_scenes.append(scene)
                
        return " ".join(processed_scenes)

    async def extract_shorts(self, raw_text: str, count: int = 3, target_language: str = "English") -> List[str]:
        """Mathematically grabs random 200-word scenes and formats them as Trailers."""
        words = raw_text.split()
        
        # Standalone Short Logic
        if len(words) < 375:
            logger.info("Story is < 375 words. Polishing entire story as 1 Standalone Short.")
            try:
                # Use SHORTS_PROMPT to ensure aggressive pacing and sensory language
                if target_language == "ur":
                    trailer_script = await self._call_llm(URDU_SHORTS_PROMPT.format(text=raw_text))
                else:
                    trailer_script = await self._call_llm(SHORTS_PROMPT.format(text=raw_text, target_language=target_language))
                return [trailer_script]
            except Exception as e:
                logger.error(f"FALLBACK: Standalone AI polish failed ({e}). Returning raw text.")
                return [raw_text]
            
        # Dynamic Trailer Scaling
        if len(words) < 700:
            count = min(count, 1)
        elif len(words) < 1000:
            count = min(count, 2)
            
        trailers = []
        scene_length = 350
        
        for _ in range(count):
            # Pick a random starting point in the middle/end of the story
            start_idx = random.randint(len(words) // 4, max(len(words) // 4, len(words) - scene_length - 1))
            # Find the nearest sentence start
            while start_idx > 0 and not words[start_idx-1].endswith(('.', '?', '!')):
                start_idx -= 1
                
            original_end = min(start_idx + scene_length, len(words))
            end_idx = original_end
            
            # Find the nearest sentence end safely (walk backwards to stay under duration cap)
            while end_idx > start_idx and not words[end_idx-1].endswith(('.', '?', '!')):
                end_idx -= 1
                
            # Fallback if no punctuation found in the entire chunk
            if end_idx == start_idx:
                end_idx = original_end
                
            scene_words = words[start_idx:end_idx]
            scene_text = " ".join(scene_words)
            
            try:
                if target_language == "ur":
                    trailer_script = await self._call_llm(URDU_SHORTS_PROMPT.format(text=scene_text))
                else:
                    trailer_script = await self._call_llm(SHORTS_PROMPT.format(text=scene_text, target_language=target_language))
                trailers.append(trailer_script)
            except Exception as e:
                logger.error(f"FALLBACK: Short extraction failed ({e}). Using raw 350-word excerpt as trailer.")
                trailers.append(scene_text)
                
        return trailers

    async def split_into_dynamic_scenes(self, text: str) -> List[dict]:
        """
        Splits a text chunk into 10-15 second scenes and extracts an image search query for each.
        Returns a list of dicts: [{"text": "scene text...", "image_query": "search terms"}, ...]
        """
        words = text.split()
        target_words = 35 # ~12 seconds
        
        scenes = []
        current_scene = []
        
        for word in words:
            current_scene.append(word)
            if len(current_scene) >= target_words and word.endswith(('.', '?', '!', '"', "'")):
                scenes.append(" ".join(current_scene))
                current_scene = []
                
        if current_scene:
            # Merge tiny orphans
            if scenes and len(current_scene) < 15:
                scenes[-1] += " " + " ".join(current_scene)
            else:
                scenes.append(" ".join(current_scene))
                
        # Now extract keywords for each scene
        dynamic_scenes = []
        for i, scene_text in enumerate(scenes):
            try:
                # Add delay to prevent rate limits since we might run this 10+ times per video
                if i > 0:
                    await asyncio.sleep(1.5)
                query = await self._call_llm(IMAGE_PROMPT.format(text=scene_text))
                query = query.strip('"\' \n').lower()
                # Fallback if AI hallucinates a long paragraph
                if len(query.split()) > 6:
                    query = " ".join(query.split()[:4])
            except Exception as e:
                logger.error(f"Image prompt failed: {e}")
                # Fallback: grab some nouns from the text
                clean_text = re.sub(r'[^\w\s]', '', scene_text)
                query = " ".join(clean_text.split()[:3])
                
            dynamic_scenes.append({
                "text": scene_text,
                "image_query": query
            })
            
        return dynamic_scenes

    async def split_into_infographic_scenes(self, text: str, video_format: str = "vertical") -> dict:
        """
        Dynamically generates an Infographic Layout JSON using the LLM.
        """
        try:
            # Prevent excessive context windows by safely chunking if needed, but since
            # infographic layout generator uses JSON, we assume the text passed is a single trailer or chunk.
            prompt = INFOGRAPHIC_PROMPT.format(video_format=video_format, text=text)
            response_text = await self._call_llm(prompt)
            
            # Clean potential markdown if LLM misbehaves
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
                
            response_text = response_text.strip()
            print(f"RAW LLM RESPONSE FOR INFOGRAPHIC:\n{response_text}\n---END RAW---")
            data = json.loads(response_text)
            return data
        except Exception as e:
            logger.error(f"FALLBACK: Infographic layout extraction failed ({e}). Returning safe default.")
            # Fallback to a single safe scene
            return {
                "video_format": video_format,
                "template": "infographic",
                "scenes": [
                    {
                        "id": "scene1",
                        "text": text,
                        "duration_sec": 10.0,
                        "bg_color": "#0d0d0d",
                        "accent_color": "#ffaa00",
                        "visual_nodes": [
                            { "type": "icon", "keyword": "brain", "slot": "center", "animation": "fade", "sync_word": text.split()[0] }
                        ]
                    }
                ]
            }

    async def detect_gender(self, raw_text: str) -> str:
        """Language-agnostic gender detection (always returns English 'male' or 'female')."""
        words = raw_text.split()
        intro_text = " ".join(words[:1000])
        try:
            gender = await self._call_llm(GENDER_PROMPT.format(text=intro_text))
            gender = gender.strip().lower()
            if "female" in gender:
                return "female"
            return "male"
        except Exception as e:
            logger.error(f"FALLBACK: Gender detection failed ({e}). Defaulting to male.")
            return "male"

    async def translate_hook_to_roman_urdu(self, hook: str) -> str:
        """Translates a manual meta.json hook into Roman Urdu."""
        try:
            translation = await self._call_llm(ROMAN_URDU_PROMPT.format(text=hook))
            return translation.strip()
        except Exception as e:
            logger.error(f"FALLBACK: Hook translation failed ({e}). Returning original hook.")
            return hook
