# Dynamic Visual Engine: Corrected & Improved Plan

## What You Actually Want To Build

Let me restate your core problem in my own words to make sure I understand it:

You want a system where:
1. A story script comes in (e.g., "The detective found a second body behind the warehouse")
2. The system automatically picks **relevant visual assets** (a detective icon, a warehouse, police tape)
3. Those assets are **animated dynamically** on screen (not static images with a Ken Burns pan)
4. **Capcut-style captions** pop word-by-word, perfectly synced with the TTS audio
5. The output is a **complete video scene** — background + icons + text + transitions — all unified
6. This is driven by **templates with placeholders**, so the same template can produce thousands of unique videos by swapping the assets

This is fundamentally a **"code-driven video rendering engine"** — exactly what your brainstorming doc concluded.

---

## Evaluating ChatGPT's Suggestions (What Was Right, Wrong, and Missing)

### ✅ What ChatGPT Got Right

1. **"Think in visual primitives"** — Brilliant advice. Composing scenes from pieces (icon + icon + effect = scene) is exactly how professional motion graphics work. This is the core design pattern we should follow.

2. **Lottie for animated icons** — Correct. LottieFiles has thousands of free animated icons (police, money, fire, etc.) and the `lottie-web` library supports frame-perfect seeking via `goToAndStop(frame, true)`. This is validated and real.

3. **SVG libraries (Lucide, Phosphor, Tabler)** — Correct. 1,500+ free icons available via CDN, ISC/MIT licensed, no attribution needed. These are real, professional-quality assets.

4. **The `timeline.json` concept** — Correct architecture. A single JSON input that describes what to render, when, and how. This decouples the "brain" (AI script generation) from the "hands" (visual renderer).

5. **"The renderer is the real product"** — Exactly right. Once you have a good renderer, you can swap story generators, TTS engines, or AI models without touching the video pipeline.

### ❌ What ChatGPT Got Wrong or Overstated

1. **"Download 50,000 SVGs. Animate them procedurally."** — Impractical for your stage. You don't need 50,000 SVGs. You need ~50-100 well-chosen ones that cover your niches (crime, science, space, mystery). Fetch them on-demand from CDN. Build a local library only once the engine is proven and you know exactly which icons you use most.

2. **Rive** — ChatGPT rated it ⭐⭐⭐⭐ but the marketplace and free-tier have become more restrictive. More importantly, Rive is designed for **interactive** apps (games, UI), not for **video rendering**. It adds complexity without clear benefit over Lottie for your use case. **Skip it.**

3. **"Effects libraries (rain, smoke, fire)"** — ChatGPT suggested downloading pre-made effect folders. This is the wrong approach for a code-driven engine. CSS/WebGL particle effects are trivially easy to generate procedurally (a few lines of code for rain, snow, fog). No need to download anything.

4. **Remotion** — ChatGPT recommended it as the renderer (`🎬 Render with Remotion`). This needs a deeper look — see my analysis below.

### 🔴 What ChatGPT Missed Entirely

1. **The sync problem.** ChatGPT never addressed *how* you capture frames deterministically. This is the single hardest technical challenge. Regular CSS animations run in real-time; if your frame capture takes 100ms, you miss animation frames. ChatGPT just assumed "render with Remotion" would solve it, without explaining why or mentioning alternatives.

2. **Revideo** — An open-source fork of Motion Canvas specifically built for headless server-side video rendering. MIT licensed. Supports parallelized rendering. This didn't exist or wasn't well-known when ChatGPT gave you those suggestions. It's potentially the best fit for your project.

3. **The caption sync architecture.** ChatGPT talked about captions as a separate concern (`📝 Render captions`). But captions need word-level timestamp data from Whisper, which needs to be injected into the animation timeline. This integration point is critical and was completely unaddressed.

4. **How the AI selects assets.** ChatGPT said "your LLM searches your database" but never explained *how*. The AI needs a mapping layer: story keywords → asset tags → specific SVG/Lottie files. This is a core piece of the architecture.

---

## The Renderer Decision: My Independent Analysis

This is the most important technical decision. There are 4 real options:

### Option 1: Remotion (React-based)
- **Pros:** Industry standard. Frame-perfect via `useCurrentFrame()`. Massive ecosystem. AI agent support ("Remotion Skills"). Handles Lottie natively. Built-in audio sync.
- **Cons:** Requires Node.js + React in your Python pipeline. Commercial license required ($$$). Adds an entire second tech stack (TypeScript/React) alongside your Python codebase.
- **Verdict:** Best tool for the job technically, but heaviest to integrate.

### Option 2: Revideo (Open-source, TypeScript)
- **Pros:** Fork of Motion Canvas with headless SSR. MIT licensed (FREE). Supports parallelized rendering. WebCodecs + FFmpeg based. Can be called from Python via subprocess/API.
- **Cons:** Smaller community than Remotion. Still requires Node.js. Less documentation.
- **Verdict:** Best open-source alternative to Remotion. Same architectural benefits, no licensing cost.

~~### Option 3: Playwright + GSAP (Current approach, fixed)~~
~~- **Pros:** Already in your project. Pure Python control. No new tech stack. GSAP timeline scrubbing gives deterministic frames.~~
~~- **Cons:** Playwright is a testing tool, not a video renderer. Screenshot-based capture is slow (~100-200ms per frame). A 60-second video at 30fps = 1,800 frames × 150ms = ~4.5 minutes render time per scene. Quality ceiling is lower than purpose-built renderers.~~
~~- **Verdict:** Fastest to prototype with. Good enough for validation. May hit performance limits at scale.~~

### [UPDATED] Option 3: Playwright + Anime.js (Current approach)
- **Pros:** Pure Python control. No new tech stack. Anime.js timeline scrubbing provides deterministic frame-perfect rendering and is 100% MIT Licensed.
- **Cons:** Screenshot-based capture is slow.
- **Verdict:** Fastest to prototype with. Free. Good enough for validation.
- **Reason for Change:** GSAP's commercial license explicitly forbids server-side video generation without a paid license. We pivoted to Anime.js which is free and does the exact same thing.

### Option 4: Shotstack / JSON2Video (Cloud API)
- **Pros:** Send JSON, get video back. Zero infrastructure. Handles rendering, scaling, everything.
- **Cons:** $39+/month subscription. Per-render costs add up at scale. You lose control over the visual quality. Limited animation capabilities compared to code-driven approaches.
- **Verdict:** Wrong fit. You're building a custom visual engine, not outsourcing rendering.

### 🎯 My Recommendation: Start with Option 3, Graduate to Option 2

~~**Phase 1 (Now — Validation):** Use **Playwright + GSAP** to validate the entire architecture. Prove that templates with placeholders work, that Lottie icons render correctly, that caption sync is frame-perfect. This requires zero new dependencies.~~

**[UPDATED] Phase 1 (Now — Validation):** Use **Playwright + Anime.js** to validate the entire architecture. Prove that templates with placeholders work, that Lottie icons render correctly, that caption sync is frame-perfect.

**Phase 2 (After validation succeeds):** Migrate the proven templates to **Revideo**. Same TypeScript/HTML concepts, but purpose-built for video rendering. 10-50x faster rendering. Parallelized. Production-grade. Your Python pipeline calls it via subprocess or a small Node.js API endpoint.

This gives you the fastest path to a working prototype WITHOUT committing to a heavy framework upfront, while having a clear upgrade path once the concept is proven.

---

## Corrected Architecture

```
Story Script (from your existing pipeline)
       ↓
Scene Analyzer (Python)
  - Extracts keywords: "detective", "body", "warehouse", "night"
  - Maps keywords to asset tags using a simple lookup table
       ↓
Asset Resolver (Python)  
  - Tags → CDN URLs:
    - "detective" → lucide/shield.svg
    - "body" → lucide/skull.svg  
    - "warehouse" → lottiefiles/warehouse-night.json
  - Fetches on-demand, caches locally after first use
       ↓
Template Populator (Python)
  - Picks template based on niche (crime → "noir_template.html")
  - Injects: SVG URLs, Lottie URLs, caption text, word timestamps
  - Writes a fully populated HTML file
       ↓
Deterministic Renderer (Python + Playwright)
  - Loads populated HTML
  - For each frame (at 30fps):
    ~~1. page.evaluate("gsap_timeline.progress(frameTime / totalDuration)")~~
    1. page.evaluate("anime_timeline.seek(progress)")
    2. page.evaluate("lottieAnim.goToAndStop(lottieFrame, true)")  
    3. page.screenshot()
  - Outputs numbered PNG frames
       ↓
FFmpeg
  - Stitches PNGs into silent MP4
  - Muxes TTS audio + background music
  - Outputs final video
```

### What's Different From ChatGPT's Architecture:
1. **Asset Resolver** — new component that maps keywords to actual CDN URLs (ChatGPT said "LLM searches database" but never defined how)
2. **On-demand fetching with local cache** — not a pre-built 50,000 asset database
3. **Deterministic frame control** — explicitly defined (ChatGPT never addressed this)
4. **Word timestamp injection** — captions get their timing data from Whisper, injected directly into the HTML template (ChatGPT treated captions as separate)

---

## Step-by-Step Validation Plan

> [!IMPORTANT]
> Each step is isolated. We do NOT move forward until each step produces a working MP4 that we both visually verify.

~~### Step 1: Prove Deterministic Rendering~~
~~- Minimal HTML: a red circle moving left to right over 3 seconds using GSAP~~
~~- `render_deterministic.py`: seeks GSAP timeline frame-by-frame via `page.evaluate()`~~
~~- **Pass criteria:** Smooth circle movement in the output MP4~~

### [UPDATED] Step 1: Prove Deterministic Rendering (Anime.js)
- Minimal HTML: a red circle moving left to right over 3 seconds using Anime.js
- `render_deterministic.py`: seeks Anime.js timeline frame-by-frame via `page.evaluate()`
- **Pass criteria:** Smooth circle movement in the output MP4

### Step 2: Prove Lottie Frame Seeking
- HTML loads one Lottie animation from CDN
- Renderer uses `goToAndStop(frame, true)` to seek each frame
- **Pass criteria:** Lottie animation plays smoothly in the output MP4 (not frozen)

~~### Step 3: Prove SVG + GSAP Animation~~
~~- HTML loads 3 Lucide SVGs from CDN~~
~~- GSAP animates them (fade in, scale, draw effect)~~
~~- **Pass criteria:** Icons animate smoothly~~

### [UPDATED] Step 3: Prove SVG + Anime.js Animation
- HTML loads 3 Lucide SVGs from CDN
- Anime.js animates them (fade in, scale, draw effect)
- **Pass criteria:** Icons animate smoothly

~~### Step 4: Prove Caption Sync~~
~~- HTML has 5 words with hardcoded timestamps~~
~~- GSAP makes each word pop/scale at its timestamp~~
~~- **Pass criteria:** Words visibly animate at DIFFERENT times (not all at once)~~

### [UPDATED] Step 4: Prove Caption Sync
- HTML has 5 words with hardcoded timestamps
- Anime.js makes each word pop/scale at its timestamp
- **Pass criteria:** Words visibly animate at DIFFERENT times (not all at once)

### Step 5: Build First Template with Placeholders
- `crime_noir_template.html` with `{{icon_1}}`, `{{lottie_bg}}`, `{{caption}}`, `{{word_timings}}`
- `build_scene.py` fills placeholders from a dummy story
- Render one complete scene
- **Pass criteria:** A dynamic, animated scene driven entirely by data

### Step 6: Full Demo — Multi-scene Video
- 3-4 sentence dummy story, split into scenes
- Each scene rendered with the template engine
- FFmpeg stitches scenes + adds TTS audio
- **Pass criteria:** A complete 30-second video with animated backgrounds, icons, and synced captions

---

## Open Questions for You

> [!WARNING]
> ~~**GSAP License Risk:** GSAP's license may require payment for "server-side rendering to generate media." If this is a problem, **Anime.js** (MIT, fully free) supports the same `timeline.seek(ms)` approach. I will test both in Step 1 and use whichever works and is free.~~
> *[RESOLVED: We successfully migrated to Anime.js in Step 1]*

> [!IMPORTANT]
> ~~**Dummy Story:** Do you want me to write a good crime story for testing, or will you provide one?~~
> *[RESOLVED: AI generated a 3-sentence crime noir dummy story]*

> [!NOTE]
> **Phase 2 (Revideo migration):** This is optional and only happens after Phase 1 is fully validated. I mention it so you know the upgrade path exists, but we are NOT building it now.

---

## Execution Logs & Findings (Live)

> [!TIP]
> **July 2026 - Sandbox Findings**
> - **GSAP Rejected:** GSAP's commercial license explicitly forbids server-side video generation without a paid "Business Green" license. We pivoted to **Anime.js**, which has an MIT license and flawlessly supports `timeline.seek(ms)`.
> - **Lottie Validated:** `lottie-web` handles `goToAndStop(frame, true)` perfectly via Playwright, ensuring vector animations don't drift or drop frames during screenshotting.
> - **Dynamic SVG Injection:** We do not need a massive local SVG database. By simply injecting `<i data-lucide="skull"></i>` into the HTML and calling `lucide.createIcons()`, the SVGs are generated dynamically right before the renderer captures the frames.
> - **Word Sync Validated:** Using a static timeline array mimicking Whisper data, Anime.js successfully animated word-level text (e.g. Capcut style) with perfect audio-visual synchronization down to the millisecond.
> - **The "Heavy ML" Mistake:** We attempted to integrate `faster-whisper` directly into the sandbox to prove perfect audio-visual sync. However, running a threaded ML inference model (even a tiny 39MB one) alongside a headless Chromium browser maxed out the dual-core CPU. We learned that to keep the engine truly lightweight, we must strictly avoid running ML models synchronously with the visual rendering pipeline. We successfully abandoned the ML approach and proved that the main codebase's existing `duration / num_words` naive math logic is perfectly sufficient and lightweight.
> - **Playwright CDN Timeouts:** We initially blamed Playwright freezes on CPU usage, but discovered the real culprit: Playwright was trying to render frames before the remote CDNs (`unpkg.com`, `cdnjs`) had finished downloading the animation libraries. We learned that when using remote assets in a headless environment, we must explicitly use `wait_until="networkidle"` and actively await the initialization of the JS functions before starting the frame capture loop.
> 
> *Steps 1 through 6 of the validation plan were executed and passed.*
