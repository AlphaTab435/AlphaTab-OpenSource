# YouTube Copyright Pre-Detection Guide

When downloading music from "royalty-free" sites (like Pixabay, Epidemic Sound, etc.), the artists or third-party distributors may still register the tracks in YouTube's Content ID system. To prevent your automated videos from being blocked globally on upload, you must verify all new music tracks *before* putting them into the ShortsForge `data/music/` folders.

## The Burner Channel Method (100% Safe)

YouTube checks for copyright during the **Processing** phase of an upload. You do not need to publish a video to know if it's safe!

### Step-by-Step Instructions:

1. **Create a Burner Channel**
   - Do not use your main channels (e.g., `stunnersgaming46`). 
   - Create a brand new, empty YouTube channel attached to a random Google account specifically for testing.

2. **Prepare a Test Video**
   - Take all the new `.mp3` files you want to test.
   - Use a simple video editor (or FFmpeg) to combine all the `.mp3` files into a single, long video (just put a black screen as the visual). 

3. **Upload as Private or Unlisted**
   - Upload this test video to your Burner Channel.
   - **CRITICAL:** Set the visibility to **Private** or **Unlisted**. Do not publish it publicly.

4. **Wait for Processing & Checks**
   - YouTube will begin the "Checks" phase (the blue loading bar in YouTube Studio).
   - Once it finishes (usually within 10-15 minutes), check the **Restrictions** column on the Videos page.

5. **Read the Results**
   - **If it says "None":** Every single track in that video is 100% safe. You can move those `.mp3` files into your ShortsForge server.
   - **If it says "Copyright Claim":** Click "See Details." YouTube will tell you exactly which track triggered the claim and at what timestamp. Delete that specific `.mp3` file from your collection immediately.

---

### Why Not Just Use The YouTube Audio Library?

The Burner Channel method is only required if you are downloading music from third-party sites like **[Pixabay](https://pixabay.com/music/)** (which is where the currently flagged tracks came from). Even though Pixabay claims tracks are "royalty-free," they cannot stop artists from registering them in Content ID elsewhere.

If you download your background music directly from the **[YouTube Studio Audio Library](https://studio.youtube.com/)**, you can skip this entire guide. Music downloaded from the official library is pre-whitelisted by YouTube and will **never** trigger a Content ID block, even on Shorts longer than 60 seconds.

---

## How to Generate & Register Your Own Music into Content ID

If you want to become the copyright owner (just like the companies that claimed your videos) and control exactly who can use your music, you can generate your own music and register it into YouTube's Content ID system yourself. 

By doing this, you can **Whitelist (Allow)** your own ShortsForge channels so they never get blocked, and **Restrict (Claim/Block)** anyone else on YouTube who tries to steal your music.

### Step 1: Generate Original Music
You cannot register someone else's royalty-free music. You must create 100% original music.
1. Use an AI Music Generator like [Suno.com](https://suno.com/) or [Udio.com](https://www.udio.com/) (You must use their paid tiers to own the commercial rights).
2. Generate dark/cinematic ambient tracks and download the `.mp3` or `.wav` files.

### Step 2: Register via a Music Distributor
YouTube does not let regular users directly upload to Content ID. You must use a "Distributor".
1. Sign up for a music distributor that offers YouTube Content ID services (e.g., **DistroKid**, **TuneCore**, or **RouteNote**).
2. Upload your AI-generated tracks to the distributor as a new "Album" or "Single".
3. Check the box to opt-in to **"YouTube Content ID"** (some distributors call it YouTube Money or YouTube Monetization).
4. The distributor will submit your audio fingerprint to YouTube. Within a few days, your music is officially protected by Content ID.

### Step 3: Allow (Whitelist) Your Own Channels
Because your music is now in Content ID, YouTube will automatically claim **your own videos** too! To prevent this:
1. Log into your Distributor's dashboard (e.g., DistroKid).
2. Find the "YouTube Content ID / Whitelist" section.
3. Enter the exact URLs of your 4 ShortsForge YouTube channels (e.g., `youtube.com/@stunnersgaming46`).
4. **Result:** YouTube will ignore the Content ID match on your channels. Your automated videos will process perfectly with no blocks.

### Step 4: Restrict (Claim) Everyone Else
You don't have to do anything for this step! If any other creator on YouTube downloads your video and tries to reuse your music, YouTube's automated system will instantly catch them. 
Depending on your distributor settings, you can either **block** their video entirely, or **claim their ad revenue** and route it straight to your bank account.
