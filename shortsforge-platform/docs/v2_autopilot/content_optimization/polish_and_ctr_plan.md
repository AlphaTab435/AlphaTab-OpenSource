# Polish & CTR Optimization Plan (Thumbnails + AI)

This plan tackles the final "Nice-to-Have" optimizations to maximize your Click-Through Rate (CTR) and Audience Retention (Watch Time).

## Part 1: Thumbnail Quality Upgrade (#6)
**Problem:** The current thumbnails use a semi-transparent black box behind white text. It looks auto-generated and has a lower CTR than viral aesthetics.
**Solution:** We will upgrade the FFmpeg visual filters to match the viral CapCut style of your new subtitles.

### [MODIFY] `scripts/story_maker/thumbnail_maker.py`
We will rewrite the `drawtext` filter chain:
1. **Remove the Black Box:** Delete the `box=1:boxcolor=black@0.5` parameters.
2. **Add a Thick Outline:** Inject a thick, solid black border directly around the text (`borderw=6:bordercolor=black`).
3. **Viral Yellow Text:** Change `fontcolor=white` to `fontcolor='#FFFF00'` for the main hook text. Yellow text on darkened backgrounds is scientifically proven to grab the eye better on mobile devices.
4. **Enhance Shadow:** Increase the shadow (`shadowx=8:shadowy=8`) to make the text pop off the screen.

---

## Part 2: AI Prompt Optimization (#7)
**Problem:** The AI stories have a good hook, but the pacing can drag if the AI reveals the "twist" too early or uses boring adjectives. 
**Solution:** Inject proven psychological retention hacks into the system prompts.

### [MODIFY] `scripts/scraper/sources/ai_generator.py`
Add the following rules to the core `system_prompt`:
- *"Maintain a strong curiosity gap: do not reveal the twist or the core mystery until the final paragraph."*
- *"Use visceral, sensory words instead of generic adjectives to keep the pacing fast and engaging."*

### [MODIFY] `scripts/story_maker/script_editor.py`
Add the exact same rules to the `SHORTS_PROMPT` so that the standalone 60-second shorts maintain the same high-retention pacing as the long videos.
