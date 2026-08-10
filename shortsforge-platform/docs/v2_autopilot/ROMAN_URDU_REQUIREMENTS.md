# Roman Urdu (Gen-Z/Desi Mode) Implementation Guide

## Objective
To expand the ShortsForge pipeline to support Urdu audiences by translating English Reddit stories into "Roman Urdu" (Urdu written in the English alphabet) while retaining heavy English slang, Gen Z vocabulary, and a natural conversational flow. 

## 1. Architectural Decisions
* **Subtitle Engine:** We are using Roman Urdu instead of native Nastaliq script. This allows us to use the standard FFmpeg `drawtext` rendering engine without requiring Right-To-Left (RTL) text reshapers or Arabic fonts.
* **Voice Engine:** Standard American Edge-TTS voices (e.g., Christopher) cannot pronounce Roman Urdu correctly. We must dynamically swap to a Pakistani locale voice (`ur-PK-AsadNeural` for male, `ur-PK-UzmaNeural` for female) when the `roman_urdu` mode is active.

## 2. The Translation Prompt (CRITICAL)
When the channel's `meta.json` specifies `"mode": "roman_urdu"`, the `script_editor.py` must bypass the standard grammar prompt and instead use the following translation prompt:

```text
You are a bilingual Gen-Z storyteller from Pakistan. Your task is to translate the following English Reddit story into "Roman Urdu" (Urdu written with English alphabets).

CRITICAL RULES:
1. Do NOT write in formal or pure Urdu. Write exactly how a modern Pakistani college student speaks to their friends (highly informal, conversational, and dramatic).
2. HEAVY ENGLISH MIX: Keep all nouns, verbs, slang, and key phrases in English! Words like 'University', 'Crush', 'Roommate', 'Ice Prince', 'FaceTime', 'Weird', 'Awkward', 'Literally', 'Actually', 'Wait' MUST remain in English. 
   - Example Bad: "Woh Ice Prince asal mein sharma raha tha."
   - Example Good: "Woh Ice Prince actually blush kar raha tha, literally."
3. Keep the storytelling incredibly engaging, using filler words like 'Yaar', 'Kasam se', 'Matlab', 'Scene yeh tha'.
4. Output ONLY the translated story. Do not include any tags, markdown, or conversational replies.
```

## 3. Implementation Steps for Production
1. **Metadata:** Add `"mode": "roman_urdu"` capability to channel initialization config.
2. **LLM Translation:** Modify `script_editor.py` to intercept the raw text and apply the Roman Urdu prompt if the mode is active.
3. **TTS Voice Routing:** Update `voice_engine.py` to map the `urdu_male` and `urdu_female` aliases to the `ur-PK` Edge-TTS voices, and ensure the script selects them appropriately based on the new mode.
