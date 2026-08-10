import os
import asyncio
import edge_tts
from gtts import gTTS
from pathlib import Path

# Recommended high-quality free Edge TTS voices for stories
EDGE_VOICES = {
    "male_narrator": "en-US-ChristopherNeural",
    "female_narrator": "en-US-AriaNeural",
    "dramatic_male": "en-US-GuyNeural",
    "casual_male": "en-US-EricNeural",
    "british_male": "en-GB-RyanNeural",
    "authoritative_male": "en-US-SteffanNeural",
    "british_female": "en-GB-SoniaNeural",
    "australian_female": "en-AU-NatashaNeural",
    "hindi_male": "hi-IN-MadhurNeural",
    "hindi_female": "hi-IN-SwaraNeural"
}

OUTPUT_DIR = Path("data/audio_temp")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

class VoiceEngine:
    """Generates TTS using Edge TTS with a fallback to gTTS to ensure zero downtime."""
    
    def __init__(self, default_voice="male_narrator"):
        self.voice = EDGE_VOICES.get(default_voice, EDGE_VOICES["male_narrator"])
        
    async def _generate_edge_tts(self, text, output_path, subtitle_path, target_voice, subtitle_style="classic"):
        """Generates audio and perfectly synced 4-word chunk subtitles using Edge TTS."""
        import os
        import re
        
        # Split text into safe chunks (max ~800 chars) to prevent Edge TTS websocket drops
        MAX_CHARS = 800
        raw_paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
        
        safe_chunks = []
        for p in raw_paragraphs:
            if len(p) <= MAX_CHARS:
                safe_chunks.append(p)
            else:
                # Split massive paragraphs by sentence
                sentences_raw = re.split(r'(?<=[.!?])\s+', p)
                current_chunk = ""
                for s in sentences_raw:
                    if len(current_chunk) + len(s) > MAX_CHARS and current_chunk:
                        safe_chunks.append(current_chunk.strip())
                        current_chunk = s
                    else:
                        current_chunk += (" " + s) if current_chunk else s
                if current_chunk:
                    safe_chunks.append(current_chunk.strip())
                    
        if not safe_chunks:
            safe_chunks = [text]
            
        sentences = []
        cumulative_offset_ms = 0.0
        
        with open(output_path, "wb") as outfile:
            for c_idx, chunk_text in enumerate(safe_chunks):
                # Hard-chunking ensures 100% reliability.
                temp_path = str(output_path) + f".temp_{c_idx}.mp3"
                # Speed up by 15% to increase retention pacing for Shorts
                communicate = edge_tts.Communicate(chunk_text, target_voice, rate='+15%')
                
                chunk_sentences = []
                with open(temp_path, "wb") as temp_file:
                    async for chunk in communicate.stream():
                        if chunk["type"] == "audio":
                            temp_file.write(chunk["data"])
                        elif chunk["type"] == "SentenceBoundary":
                            chunk_sentences.append({
                                "text": chunk["text"],
                                "start_ms": chunk["offset"] / 10000.0,
                                "duration_ms": chunk["duration"] / 10000.0
                            })
                
                if not os.path.exists(temp_path) or os.path.getsize(temp_path) == 0:
                    continue
                    
                # Append raw MP3 bytes to main file
                with open(temp_path, "rb") as temp_file:
                    outfile.write(temp_file.read())
                    
                # Shift timestamps and add to main list
                for sent in chunk_sentences:
                    sent["start_ms"] += cumulative_offset_ms
                    sentences.append(sent)
                    
                # Get exact duration of this MP3 chunk to prevent subtitle drift
                exact_duration_s = self.get_audio_duration(temp_path)
                cumulative_offset_ms += exact_duration_s * 1000.0
                
                os.remove(temp_path)
                
        # Group sentence-level timestamps into 3-4 word Shorts-style chunks to bound drift
        # Group sentence-level timestamps into 3-4 word Shorts-style chunks
        srt_chunks = []
        
        from scripts.story_maker.constants import ANIMATED_SUBTITLE_STYLES, SUBTITLE_HTML_COLORS
        
        if subtitle_style in ANIMATED_SUBTITLE_STYLES:
            active_color = SUBTITLE_HTML_COLORS.get(subtitle_style, "#FFFF00")
            
            for sent in sentences:
                words = sent["text"].split()
                if not words: continue
                
                sub_chunks = []
                curr = []
                for w in words:
                    curr.append(w)
                    if len(curr) >= 4 or w[-1] in '.?!':
                        sub_chunks.append(curr) # List of words
                        curr = []
                if curr: sub_chunks.append(curr)
                
                total_chars = sum(len(" ".join(c)) for c in sub_chunks)
                if total_chars == 0: total_chars = 1
                
                current_time = sent["start_ms"]
                for sub_words in sub_chunks:
                    sub_text = " ".join(sub_words)
                    char_ratio = len(sub_text) / total_chars
                    chunk_duration = sent["duration_ms"] * char_ratio
                    
                    word_time = current_time
                    sub_total_chars = sum(len(w) for w in sub_words)
                    if sub_total_chars == 0: sub_total_chars = 1
                    
                    for i, target_word in enumerate(sub_words):
                        w_ratio = len(target_word) / sub_total_chars
                        w_duration = chunk_duration * w_ratio
                        
                        highlighted_words = []
                        for j, w in enumerate(sub_words):
                            if i == j:
                                highlighted_words.append(f'<font color="{active_color}">{w}</font>')
                            else:
                                highlighted_words.append(w)
                                
                        srt_chunks.append({
                            "start": word_time,
                            "end": word_time + w_duration,
                            "text": " ".join(highlighted_words)
                        })
                        word_time += w_duration
                        
                    current_time += chunk_duration
        else:
            for sent in sentences:
                words = sent["text"].split()
                if not words: continue
                
                sub_chunks = []
                curr = []
                for w in words:
                    curr.append(w)
                    if len(curr) >= 4 or w[-1] in '.?!':
                        sub_chunks.append(" ".join(curr))
                        curr = []
                if curr: sub_chunks.append(" ".join(curr))
                
                total_chars = sum(len(c) for c in sub_chunks)
                if total_chars == 0: total_chars = 1
                
                current_time = sent["start_ms"]
                for sub_text in sub_chunks:
                    char_ratio = len(sub_text) / total_chars
                    chunk_duration = sent["duration_ms"] * char_ratio
                    
                    srt_chunks.append({
                        "start": current_time,
                        "end": current_time + chunk_duration,
                        "text": sub_text
                    })
                    current_time += chunk_duration
            
        def format_time(ms):
            seconds = ms / 1000.0
            hrs, mins, secs, msecs = int(seconds // 3600), int((seconds % 3600) // 60), int(seconds % 60), int((seconds % 1) * 1000)
            return f"{hrs:02d}:{mins:02d}:{secs:02d},{msecs:03d}"
            
        with open(subtitle_path, "w", encoding="utf-8") as file:
            for i, cue in enumerate(srt_chunks):
                file.write(f"{i+1}\n{format_time(cue['start'])} --> {format_time(cue['end'])}\n{cue['text']}\n\n")
        
    def _generate_gtts_fallback(self, text, output_path):
        """Generates audio using gTTS as a reliable fallback."""
        tts = gTTS(text=text, lang='en', slow=False)
        tts.save(output_path)

    def _generate_fallback_srt(self, text, duration, output_path):
        """Generates a naive SRT if we are forced to use gTTS."""
        words = text.split()
        if not words: return
        chunks = []
        current_chunk = []
        for word in words:
            current_chunk.append(word)
            if len(current_chunk) >= 4 or word[-1] in '.?!':
                chunks.append(" ".join(current_chunk))
                current_chunk = []
        if current_chunk: chunks.append(" ".join(current_chunk))
            
        total_chars = sum(len(c) for c in chunks)
        if total_chars == 0: total_chars = 1
            
        with open(output_path, 'w', encoding='utf-8') as f:
            current_time = 0.0
            for i, chunk in enumerate(chunks):
                char_ratio = len(chunk) / total_chars
                chunk_duration = duration * char_ratio
                start_time, end_time = current_time, current_time + chunk_duration
                current_time = end_time
                
                def format_time(seconds):
                    hrs, mins, secs, msecs = int(seconds // 3600), int((seconds % 3600) // 60), int(seconds % 60), int((seconds % 1) * 1000)
                    return f"{hrs:02d}:{mins:02d}:{secs:02d},{msecs:03d}"
                    
                f.write(f"{i+1}\n{format_time(start_time)} --> {format_time(end_time)}\n{chunk}\n\n")

    def get_audio_duration(self, filepath):
        import subprocess
        cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1', str(filepath)]
        try:
            return float(subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout.strip())
        except: return 0.0

    def generate_audio(self, text, output_filename, use_fallback=False, sub_dir: str = "", voice_override: str = None, subtitle_style: str = "classic"):
        """
        Attempts to generate high-quality audio and a perfectly synced subtitle file.
        Returns a tuple: (audio_path, subtitle_path).
        """
        text = text.strip()
        if not text:
            print("Warning: Empty text provided to VoiceEngine.")
            return None, None
        
        import threading
        
        if not output_filename.endswith('.mp3'):
            output_filename += '.mp3'
            
        target_dir = OUTPUT_DIR / sub_dir if sub_dir else OUTPUT_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        
        audio_path = target_dir / output_filename
        subtitle_path = target_dir / output_filename.replace('.mp3', '.srt')
        
        if audio_path.exists() and subtitle_path.exists():
            if audio_path.stat().st_size > 1024 and subtitle_path.stat().st_size > 10:
                print(f"[TEMP] Using cached audio: {audio_path}")
                return str(audio_path), str(subtitle_path)
            else:
                print(f"[TEMP] Ignoring corrupted cached audio/srt for {output_filename}")
                audio_path.unlink(missing_ok=True)
                subtitle_path.unlink(missing_ok=True)
        
        target_voice = EDGE_VOICES.get(voice_override, self.voice) if voice_override else self.voice
        print(f"Generating Edge TTS ({target_voice}) for {output_filename}...")
        try:
            error_container = []
            
            def run_edge_tts_in_thread():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    loop.run_until_complete(self._generate_edge_tts(text, audio_path, subtitle_path, target_voice, subtitle_style))
                except Exception as e:
                    error_container.append(e)
                finally:
                    loop.close()
                    
            thread = threading.Thread(target=run_edge_tts_in_thread)
            thread.start()
            thread.join()
            
            if error_container:
                raise error_container[0]
                
            print(f"[TEMP] Successfully generated audio: {audio_path}")
            return str(audio_path), str(subtitle_path)
            
        except Exception as e:
            print(f"FALLBACK: Edge TTS failed ({e}). Falling back to gTTS...")
            try:
                self._generate_gtts_fallback(text, audio_path)
                self._generate_fallback_srt(text, self.get_audio_duration(audio_path), subtitle_path)
                print(f"[TEMP] Successfully generated fallback audio: {audio_path}")
                return str(audio_path), str(subtitle_path)
            except Exception as fallback_err:
                print(f"CRITICAL ERROR: All TTS engines failed: {fallback_err}")
                return None, None

if __name__ == "__main__":
    # Quick test
    engine = VoiceEngine()
    test_text = "I thought my husband was dead for five years. Then I saw him at the grocery store. Follow for Part 2."
    result = engine.generate_audio(test_text, "test_hook.mp3")
    if result[0]:
        print("Voice Engine test passed.")
