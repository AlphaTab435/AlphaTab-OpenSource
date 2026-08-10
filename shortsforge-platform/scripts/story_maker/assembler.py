import os
import subprocess
import json
import asyncio
from playwright.async_api import async_playwright
from pathlib import Path
from scripts.story_maker.voice_engine import VoiceEngine
from scripts.story_maker.media_picker import MediaPicker
from scripts.story_maker.thumbnail_maker import make_thumbnail_for_video
from scripts.story_maker.constants import ANIMATED_SUBTITLE_STYLES
import time

OUTPUT_DIR = Path("data/final_shorts")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
TEMP_DIR = Path("data/video_temp")

class StoryAssembler:
    """Assembles audio, media, and text into final Shorts."""
    
    def __init__(self):
        self.voice = VoiceEngine()
        self.media = MediaPicker()

    def get_audio_duration(self, filepath):
        cmd = [
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
            '-of', 'default=noprint_wrappers=1:nokey=1', str(filepath)
        ]
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return float(result.stdout.strip())
        except:
            return 0.0

    def _pre_mix_audio(self, tts_path: str, music_path: str, duration: float, sub_dir: str) -> str:
        """Mixes TTS with background music safely by calculating loops and using concat demuxer."""
        if not music_path or duration <= 0:
            return tts_path
            
        import math
        
        music_duration = self.get_audio_duration(music_path)
        if music_duration <= 0:
            return tts_path
            
        target_dir = OUTPUT_DIR / sub_dir if sub_dir else OUTPUT_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = int(time.time() * 1000)
        concat_file_path = target_dir / f"concat_{timestamp}.txt"
        mixed_audio_path = target_dir / f"mixed_{timestamp}.mp3"
        
        # Calculate loops needed
        loops = math.ceil(duration / music_duration) + 1
        
        with open(concat_file_path, "w", encoding="utf-8") as f:
            safe_music_path = str(Path(music_path).resolve()).replace('\\', '/')
            for _ in range(loops):
                f.write(f"file '{safe_music_path}'\n")
                
        cmd = [
            'ffmpeg', '-y',
            '-i', str(tts_path),
            '-f', 'concat', '-safe', '0', '-i', str(concat_file_path),
            '-filter_complex', '[0:a]volume=1.0[tts]; [1:a]volume=0.05[music]; [tts][music]amix=inputs=2:duration=first:dropout_transition=0[aout]',
            '-map', '[aout]',
            '-c:a', 'libmp3lame', '-q:a', '2',
            str(mixed_audio_path)
        ]
        
        print(f"[TEMP] Pre-mixing audio ({loops} loops of music)...")
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, check=True)
            try: os.remove(concat_file_path)
            except: pass
            return str(mixed_audio_path)
        except Exception as e:
            print(f"Audio pre-mix failed: {e}")
            return tts_path

    def _get_sticky_header_vf(self, title: str, subtitle_style: str, video_format: str, is_short: bool, dim_filter: str, escaped_srt: str, srt_style: str, has_cta: bool = False, cta: str = "") -> str:
        """Generates the video filter string with a letterbox sticky header for vertical videos."""
        if not is_short and video_format == "horizontal":
            vf = f"scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080"
            if dim_filter:
                vf += f",{dim_filter.rstrip(',')}"
            if has_cta and cta:
                vf += f",drawtext=text='{cta}':fontcolor=white:fontsize=60:x=(w-text_w)/2:y=h-400"
            vf += f",subtitles={escaped_srt}:force_style='{srt_style}'"
            return vf
            
        # Standard Full Screen Vertical
        vf = f"scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920"
        
        if dim_filter:
            vf += f",{dim_filter.rstrip(',')}"
            
        if has_cta and cta:
            vf += f",drawtext=text='{cta}':fontcolor=white:fontsize=60:x=(w-text_w)/2:y=h-200"
            
        vf += f",subtitles={escaped_srt}:force_style='{srt_style}'"
        
        if title:
            import textwrap
            def esc(s):
                return s.replace("'", "\u2019").replace(":", "\\:").replace(",", "\\,").replace("[", "\\[").replace("]", "\\]")
            safe_title = esc(title)
            wrapped_lines = textwrap.wrap(safe_title, width=28)
            
            from scripts.story_maker.constants import SUBTITLE_FFMPEG_COLORS
            base_color = SUBTITLE_FFMPEG_COLORS.get(subtitle_style, "white")
            
            font_size = 65
            line_spacing = 80
            total_lines = len(wrapped_lines)
            start_y = 160 - ((total_lines * line_spacing) // 2) + (line_spacing // 2)
            
            for i, line in enumerate(wrapped_lines):
                offset = start_y + (i * line_spacing)
                vf += f",drawtext=font='Impact':text='{line}':fontcolor={base_color}:fontsize={font_size}:x=(w-text_w)/2:y={offset}-(text_h/2):shadowx=3:shadowy=3:shadowcolor=black"
                
        return vf


    def build_part(self, title: str, chunk: dict, is_last: bool, total_parts: int, force_bg_type: str = "video", hook: str = "", channel_name: str = None, search_style: str = "anime illustration digital art", bg_image_path: str = None, topic: str = "UnknownTopic", has_multiple_parts: bool = True, video_dim: float = -0.15, thumb_dim: float = -0.35, is_short: bool = False, voice_override: str = None, music_enabled: bool = True, subtitle_style: str = "classic", video_format: str = "vertical", enable_heavy_shadows: bool = True, enable_dark_gradient_box: bool = True):
        """Builds a single Short video for a specific chunk/part."""
        part_num = chunk['chunk_id']
        print(f"--- Building Part {part_num} of {total_parts} ({force_bg_type} bg) ---")
        
        import re
        safe_topic = "".join([c if c.isalnum() else "_" for c in topic]).lower()
        safe_topic = re.sub(r'_+', '_', safe_topic).strip('_')[:50]
        safe_channel = channel_name if channel_name else "UnknownChannel"
        sub_dir = f"{safe_channel}/{safe_topic}"
        
        text = chunk['text']
        if not is_last:
            text += f" Subscribe for Part {part_num + 1}! Link in description."
        else:
            text += " Like, comment & subscribe for more!"
            
        # 1. Generate Audio and Perfect Subtitles
        audio_file = f"{safe_topic}_part_{part_num}_{force_bg_type}.mp3"
        audio_path, srt_path = self.voice.generate_audio(text, audio_file, sub_dir=sub_dir, voice_override=voice_override, subtitle_style=subtitle_style)
        if not audio_path or not srt_path:
            print("Failed to generate audio or subtitles. Skipping.")
            return None, None
            
        duration = self.get_audio_duration(audio_path)
        print(f"Audio duration: {duration:.2f}s")
        
        if music_enabled:
            music_path = self.media.get_background_music(channel_name)
            if music_path:
                print(f"[MUSIC] Selected background music: {music_path}")
                audio_path = self._pre_mix_audio(audio_path, music_path, duration, sub_dir)
        
        # 2. Get Background
        bg_file = f"temp_bg_part_{part_num}_{int(time.time())}.mp4"
        bg_path = None
        
        # Tier 1: Channel Video
        if force_bg_type == "video" and channel_name:
            bg_path = self.media.get_background_video(duration, bg_file, channel_name=channel_name, sub_dir=sub_dir)
            if bg_path: print("[MEDIA] Using Tier 1: Channel Video")
            
        # Tier 2: Story Downloaded Image (Cached DB Image)
        if not bg_path and bg_image_path:
            bg_path = bg_image_path
            print("[MEDIA] FALLBACK Tier 2: Story Downloaded Image")
            
        # Tier 3: Channel Static Image
        if not bg_path and channel_name:
            bg_path = self.media.get_static_image(channel_name=channel_name)
            if bg_path: print("[MEDIA] FALLBACK Tier 3: Channel Static Image")
            
        # Tier 4: Global Video
        if not bg_path:
            bg_path = self.media.get_background_video(duration, bg_file, channel_name=None, sub_dir=sub_dir)
            if bg_path: print("[MEDIA] FALLBACK Tier 4: Global Video")
            
        # Tier 5: Global Static Image
        if not bg_path:
            bg_path = self.media.get_static_image(channel_name=None)
            if bg_path: print("[MEDIA] FALLBACK Tier 5: Global Static Image")
                
        if not bg_path:
            print("CRITICAL ERROR: No media available at all! Please place a gameplay.mp4 or a static image.")
            return None
                
        is_image = bg_path.endswith(('.jpg', '.png', '.jpeg'))
        suffix = "image" if is_image else "video"

        # ALWAYS fetch a static image for the thumbnail
        thumb_image_path = bg_image_path

        escaped_srt = str(srt_path).replace('\\', '/').replace(':', '\\:').replace(' ', '\\ ')
        
        target_dir = OUTPUT_DIR / sub_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        if has_multiple_parts:
            output_file = target_dir / f"{safe_topic}_part_{part_num}_{suffix}.mp4"
        else:
            output_file = target_dir / f"{safe_topic}_{suffix}.mp4"
        
        # 4. Assemble with FFmpeg
        print(f"Assembling {output_file.name}...")
        print(f"[TEMP] Using background media: {bg_path}")
        
        dim_filter = "" if video_dim == 0 else f"eq=brightness={video_dim},"
        
        # Determine Resolution
        if not is_short and video_format == "horizontal":
            out_w, out_h = 1920, 1080
        else:
            out_w, out_h = 1080, 1920
        
        if subtitle_style in ANIMATED_SUBTITLE_STYLES:
            srt_style = "Alignment=10,MarginV=0,MarginL=20,MarginR=20,Fontsize=22,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=3,BorderStyle=1,Bold=1,Shadow=1"
        else:
            srt_style = "Alignment=10,MarginV=0,MarginL=20,MarginR=20,Fontsize=16,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=1.2,BorderStyle=1,Bold=1"
        
        if is_image:
            cmd = [
                'ffmpeg', '-y',
                '-loop', '1', '-i', bg_path,
                '-i', audio_path,
                '-vf', self._get_sticky_header_vf(title, subtitle_style, video_format, is_short, dim_filter, escaped_srt, srt_style),
                '-c:v', 'libx264', '-tune', 'stillimage', '-preset', 'fast', '-pix_fmt', 'yuv420p',
                '-c:a', 'aac', '-map', '0:v:0', '-map', '1:a:0',
                '-t', str(duration),
                str(output_file)
            ]
        else:
            cmd = [
                'ffmpeg', '-y',
                '-stream_loop', '-1', '-i', bg_path,
                '-i', audio_path,
                '-vf', self._get_sticky_header_vf(title, subtitle_style, video_format, is_short, dim_filter, escaped_srt, srt_style),
                '-c:v', 'libx264', '-preset', 'fast', '-pix_fmt', 'yuv420p',
                '-c:a', 'aac', '-map', '0:v:0', '-map', '1:a:0',
                '-t', str(duration),
                str(output_file)
            ]
            
        try:
            result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, check=True)
            print(f"[FINAL] Successfully built video: {output_file}")
            
            # Generate single thumbnail using the hook text
            thumbnail_path = None
            if hook and thumb_image_path:
                 thumb_name = f"{safe_topic}_part_{part_num}_thumbnail" if has_multiple_parts else f"{safe_topic}_thumbnail"
                 thumbnail_path = make_thumbnail_for_video(
                    video_title=thumb_name,
                    hook_text=hook,
                    image_path=thumb_image_path,
                    sub_dir=sub_dir,
                    thumb_dim=thumb_dim,
                    is_short=is_short,
                    enable_heavy_shadows=enable_heavy_shadows,
                    enable_dark_gradient_box=enable_dark_gradient_box,
                    subtitle_style=subtitle_style
                )
            return str(output_file), thumbnail_path
        except Exception as e:
            print(f"FFmpeg assembly failed: {e}")
            if hasattr(e, 'stderr') and e.stderr:
                for line in e.stderr.strip().split('\n')[-5:]:
                    print(f"  [FFmpeg] {line}")
            return None, None

    def build_dynamic_part(self, title: str, dynamic_scenes: list, part_num: int, is_last: bool, total_parts: int, channel_name: str = None, topic: str = "UnknownTopic", has_multiple_parts: bool = True, video_dim: float = -0.15, thumb_dim: float = -0.35, is_short: bool = False, voice_override: str = None, music_enabled: bool = True, subtitle_style: str = "classic", video_format: str = "vertical", enable_heavy_shadows: bool = True, enable_dark_gradient_box: bool = True, cta: str = None, max_duration: int = None, trailer_idx: int = 1, hook: str = None):
        """
        Builds a Dynamic Scene-by-Scene video.
        - Generates Audio/SRT for each scene independently.
        - Fetches a unique DuckDuckGo image for each scene.
        - Burns subtitles into each scene.
        - Uses FFmpeg concat to stitch all scenes together.
        - Overlays global background music.
        """
        print(f"\n--- Building DYNAMIC Part {part_num} of {total_parts} ({len(dynamic_scenes)} scenes) ---")
        import re
        import time
        import math
        import shutil
        safe_topic = "".join([c if c.isalnum() else "_" for c in topic]).lower()
        safe_topic = re.sub(r'_+', '_', safe_topic).strip('_')[:50]
        safe_channel = channel_name if channel_name else "UnknownChannel"
        sub_dir = f"{safe_channel}/{safe_topic}"
        
        # Temp folder for scene assets
        temp_dir_name = f"part_{part_num}_assets"
        temp_dir = OUTPUT_DIR / sub_dir / temp_dir_name
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        # Append CTA to last scene if this is a long video
        if not is_short:
            if not is_last:
                dynamic_scenes[-1]['text'] += f" Subscribe for Part {part_num + 1}! Link in description."
            else:
                dynamic_scenes[-1]['text'] += " Like, comment & subscribe for more!"
            
        scene_mp4s = []
        total_audio_duration = 0.0
        first_scene_img = None
        
        for idx, scene in enumerate(dynamic_scenes):
            scene_id = idx + 1
            print(f"  [SCENE {scene_id}/{len(dynamic_scenes)}] Keyword: '{scene['image_query']}'")
            
            # 1. Generate Scene Audio
            scene_audio_name = f"scene_{scene_id}.mp3"
            # voice_engine uses OUTPUT_DIR / sub_dir to save.
            scene_audio_path, scene_srt_path = self.voice.generate_audio(
                scene['text'], 
                scene_audio_name, 
                sub_dir=f"{sub_dir}/{temp_dir_name}", 
                voice_override=voice_override, 
                subtitle_style=subtitle_style
            )
            
            if not scene_audio_path:
                print(f"  [SCENE {scene_id}] Audio failed. Skipping scene.")
                continue
                
            scene_duration = self.get_audio_duration(scene_audio_path)
            total_audio_duration += scene_duration
            
            # 2. Fetch Scene Image (Dynamic)
            scene_img = self.media.fetch_internet_image(scene['image_query'], style="", sub_dir=f"{sub_dir}/{temp_dir_name}", is_temp=True)
            if not scene_img:
                scene_img = self.media.get_static_image(channel_name)
                if not scene_img:
                    scene_img = self.media.get_static_image(None)
                    
            if not scene_img:
                print(f"  [SCENE {scene_id}] CRITICAL: No image found!")
                continue
                
            if first_scene_img is None:
                first_scene_img = scene_img
                
            # 3. Build Scene MP4
            scene_mp4 = temp_dir / f"scene_{scene_id}_video.mp4"
            dim_filter = "" if video_dim == 0 else f"eq=brightness={video_dim},"
            escaped_srt = str(scene_srt_path).replace('\\', '/').replace(':', '\\:').replace(' ', '\\ ')
            
            # Determine Resolution
            if not is_short and video_format == "horizontal":
                out_w, out_h = 1920, 1080
            else:
                out_w, out_h = 1080, 1920
            
            if subtitle_style in ANIMATED_SUBTITLE_STYLES:
                srt_style = "Alignment=10,MarginV=0,MarginL=20,MarginR=20,Fontsize=22,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=3,BorderStyle=1,Bold=1,Shadow=1"
            else:
                srt_style = "Alignment=10,MarginV=0,MarginL=20,MarginR=20,Fontsize=16,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=1.2,BorderStyle=1,Bold=1"

            # Slow zoom effect for dynamic feeling
            zoom_dir = "min(zoom+0.001,1.5)" if idx % 2 == 0 else "max(1.5-(zoom-1.0)*0.001,1.0)"
            
            drawtext_filter = f"drawtext=text='{cta}':fontcolor=white:fontsize=60:x=(w-text_w)/2:y=h-400," if cta else ""
            
            cmd = [
                'ffmpeg', '-y',
                '-loop', '1', '-i', scene_img,
                '-i', scene_audio_path,
                '-vf', f"scale={out_w}:{out_h}:force_original_aspect_ratio=increase,crop={out_w}:{out_h},zoompan=z='{zoom_dir}':d=750:s={out_w}x{out_h},{dim_filter}{drawtext_filter}subtitles={escaped_srt}:force_style='{srt_style}'",
                '-c:v', 'libx264', '-preset', 'fast', '-pix_fmt', 'yuv420p',
                '-c:a', 'aac', '-map', '0:v:0', '-map', '1:a:0',
                '-t', str(scene_duration),
                str(scene_mp4)
            ]
            
            try:
                subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, check=True)
                scene_mp4s.append(scene_mp4)
            except Exception as e:
                print(f"  [SCENE {scene_id}] Ken Burns failed, falling back to static...")
                # Fallback to static crop if zoompan crashes on weird image dimensions
                fallback_cmd = [
                    'ffmpeg', '-y',
                    '-loop', '1', '-i', scene_img,
                    '-i', scene_audio_path,
                    '-vf', f"scale={out_w}:{out_h}:force_original_aspect_ratio=increase,crop={out_w}:{out_h},{dim_filter}{drawtext_filter}subtitles={escaped_srt}:force_style='{srt_style}'",
                    '-c:v', 'libx264', '-tune', 'stillimage', '-preset', 'fast', '-pix_fmt', 'yuv420p',
                    '-c:a', 'aac', '-map', '0:v:0', '-map', '1:a:0',
                    '-t', str(scene_duration),
                    str(scene_mp4)
                ]
                try:
                    subprocess.run(fallback_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                    scene_mp4s.append(scene_mp4)
                except Exception as fallback_err:
                    print(f"  [SCENE {scene_id}] CRITICAL: Fallback static render failed: {fallback_err}")
                    continue
                
        if not scene_mp4s:
            print("CRITICAL ERROR: No scenes were built successfully.")
            return None, None
            
        # 4. Master Concat
        target_dir = OUTPUT_DIR / sub_dir
        
        if is_short:
            if has_multiple_parts:
                final_mp4 = target_dir / f"{safe_topic}_part_{part_num}_short_{trailer_idx}_dynamic.mp4"
                thumb_name = f"{safe_topic}_part_{part_num}_short_{trailer_idx}_thumbnail"
            else:
                if trailer_idx > 1:
                    final_mp4 = target_dir / f"{safe_topic}_short_{trailer_idx}_dynamic.mp4"
                    thumb_name = f"{safe_topic}_short_{trailer_idx}_thumbnail"
                else:
                    final_mp4 = target_dir / f"{safe_topic}_short_dynamic.mp4"
                    thumb_name = f"{safe_topic}_short_thumbnail"
        else:
            final_mp4 = target_dir / (f"{safe_topic}_part_{part_num}_dynamic.mp4" if has_multiple_parts else f"{safe_topic}_dynamic.mp4")
            thumb_name = f"{safe_topic}_part_{part_num}_thumbnail" if has_multiple_parts else f"{safe_topic}_thumbnail"
        
        concat_list = temp_dir / "concat_list.txt"
        with open(concat_list, "w", encoding="utf-8") as f:
            for mp4 in scene_mp4s:
                safe_mp4 = str(mp4.resolve()).replace('\\', '/')
                f.write(f"file '{safe_mp4}'\n")
                
        concat_cmd = [
            'ffmpeg', '-y',
            '-f', 'concat', '-safe', '0', '-i', str(concat_list),
            '-c', 'copy'
        ]
        
        # Enforce max duration for Shorts at the concat level if provided
        if max_duration and max_duration > 0:
            concat_cmd.extend(['-t', str(max_duration)])
            
        concat_cmd.append(str(final_mp4))
        
        print(f"Stitching {len(scene_mp4s)} dynamic scenes together...")
        try:
            subprocess.run(concat_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            
            # 5. Add Music (if enabled)
            if music_enabled:
                music_path = self.media.get_background_music(channel_name)
                if music_path:
                    mixed_mp4 = target_dir / f"{final_mp4.stem}_mixed.mp4"
                    loops = math.ceil(total_audio_duration / self.get_audio_duration(music_path)) + 1
                    music_concat = temp_dir / "music_concat.txt"
                    with open(music_concat, "w", encoding="utf-8") as f:
                        safe_music = str(Path(music_path).resolve()).replace('\\', '/')
                        for _ in range(loops):
                            f.write(f"file '{safe_music}'\n")
                            
                    mix_cmd = [
                        'ffmpeg', '-y',
                        '-i', str(final_mp4),
                        '-f', 'concat', '-safe', '0', '-i', str(music_concat),
                        '-filter_complex', '[0:a]volume=1.0[v]; [1:a]volume=0.05[m]; [v][m]amix=inputs=2:duration=first:dropout_transition=0[aout]',
                        '-map', '0:v', '-map', '[aout]',
                        '-c:v', 'copy',
                        '-c:a', 'aac',
                        str(mixed_mp4)
                    ]
                    subprocess.run(mix_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                    import os
                    os.replace(mixed_mp4, final_mp4)
            
            print(f"[FINAL] Dynamic Video Built: {final_mp4}")
            
            # 6. Generate Thumbnail (using first scene image)
            thumbnail_path = None
            try:
                if first_scene_img:
                    thumbnail_path = make_thumbnail_for_video(
                        video_title=thumb_name,
                        hook_text=hook if hook else dynamic_scenes[0]['text'][:30] + "...",
                        image_path=str(first_scene_img),
                        sub_dir=sub_dir,
                        thumb_dim=thumb_dim,
                        is_short=is_short,
                        enable_heavy_shadows=enable_heavy_shadows,
                        enable_dark_gradient_box=enable_dark_gradient_box,
                        subtitle_style=subtitle_style
                    )
            except Exception as e:
                import traceback
                print(f"[THUMBNAIL CRASH] Dynamic thumbnail failed for {thumb_name}:")
                traceback.print_exc()
                
            # 7. Auto-Cleanup Temp Assets
            try:
                shutil.rmtree(temp_dir)
                print(f"Cleaned up {len(scene_mp4s)} temporary scene assets.")
            except Exception as e:
                print(f"Cleanup failed: {e}")
                
            return str(final_mp4), thumbnail_path
            
        except Exception as e:
            print(f"Concat failed: {e}")
            return None, None
            
    def build_short_story(self, title: str, audio_path: str, subtitle_path: str, max_duration: int, cta: str, force_bg_type: str = "video", hook: str = "", channel_name: str = None, search_style: str = "anime illustration digital art", bg_image_path: str = None, topic: str = "UnknownTopic", part_num: int = 1, trailer_idx: int = 1, has_multiple_parts: bool = True, video_dim: float = -0.15, thumb_dim: float = -0.35, music_enabled: bool = True, subtitle_style: str = "classic", video_format: str = "vertical", enable_heavy_shadows: bool = True, enable_dark_gradient_box: bool = True) -> str:
        """Build a short trailer video."""
        print(f"--- Building Short {trailer_idx} (Part {part_num}) ({force_bg_type} bg) ---")
        import re
        safe_topic = "".join([c if c.isalnum() else "_" for c in topic]).lower()
        safe_topic = re.sub(r'_+', '_', safe_topic).strip('_')[:50]
        safe_channel = channel_name if channel_name else "UnknownChannel"
        sub_dir = f"{safe_channel}/{safe_topic}"
        
        bg_file = f"temp_bg_short_{int(time.time())}.mp4"
        bg_path = None
        
        # Tier 1: Channel Video
        if force_bg_type == "video" and channel_name:
            bg_path = self.media.get_background_video(max_duration, bg_file, channel_name=channel_name, sub_dir=sub_dir)
            if bg_path: print("[MEDIA] Using Tier 1: Channel Video")
            
        # Tier 2: Story Downloaded Image (Cached DB Image)
        if not bg_path and bg_image_path:
            bg_path = bg_image_path
            print("[MEDIA] FALLBACK Tier 2: Story Downloaded Image")
            
        # Tier 3: Channel Static Image
        if not bg_path and channel_name:
            bg_path = self.media.get_static_image(channel_name=channel_name)
            if bg_path: print("[MEDIA] FALLBACK Tier 3: Channel Static Image")
            
        # Tier 4: Global Video
        if not bg_path:
            bg_path = self.media.get_background_video(max_duration, bg_file, channel_name=None, sub_dir=sub_dir)
            if bg_path: print("[MEDIA] FALLBACK Tier 4: Global Video")
            
        # Tier 5: Global Static Image
        if not bg_path:
            bg_path = self.media.get_static_image(channel_name=None)
            if bg_path: print("[MEDIA] FALLBACK Tier 5: Global Static Image")
            
        if not bg_path:
            print("No media available for short story.")
            return None
                
        audio_duration = self.get_audio_duration(audio_path)
        print(f"Audio duration: {audio_duration:.2f}s")
        
        if music_enabled:
            music_path = self.media.get_background_music(channel_name)
            if music_path:
                audio_path = self._pre_mix_audio(audio_path, music_path, min(audio_duration, max_duration), sub_dir)
        
        escaped_srt = str(subtitle_path).replace('\\', '/').replace(':', '\\:').replace(' ', '\\ ')
        is_image = bg_path.endswith(('.jpg', '.png', '.jpeg'))
        suffix = "image" if is_image else "video"
                    
        # ALWAYS fetch a static image for the thumbnail
        thumb_image_path = bg_image_path

        target_dir = OUTPUT_DIR / sub_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        if has_multiple_parts:
            output_file = target_dir / f"{safe_topic}_part_{part_num}_short_{trailer_idx}_{suffix}.mp4"
            thumb_name = f"{safe_topic}_part_{part_num}_short_{trailer_idx}_thumbnail"
        else:
            if trailer_idx > 1:
                output_file = target_dir / f"{safe_topic}_short_{trailer_idx}_{suffix}.mp4"
                thumb_name = f"{safe_topic}_short_{trailer_idx}_thumbnail"
            else:
                output_file = target_dir / f"{safe_topic}_short_{suffix}.mp4"
                thumb_name = f"{safe_topic}_short_thumbnail"
        
        # Audio duration check
        duration = self.get_audio_duration(audio_path)
        actual_duration = min(duration, max_duration) if duration > 0 else max_duration
        
        print(f"Assembling {output_file.name}...")
        print(f"[TEMP] Using background media: {bg_path}")
        
        dim_filter = "" if video_dim == 0 else f"eq=brightness={video_dim},"
        
        # Determine Resolution (Shorts MUST always be vertical)
        out_w, out_h = 1080, 1920
        
        if subtitle_style in ["capcut_yellow", "neon_red", "electric_blue", "toxic_green"]:
            srt_style = "Alignment=10,MarginV=0,MarginL=20,MarginR=20,Fontsize=22,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=3,BorderStyle=1,Bold=1,Shadow=1"
        else:
            srt_style = "Alignment=10,MarginV=0,MarginL=20,MarginR=20,Fontsize=16,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=1.2,BorderStyle=1,Bold=1"
        
        if is_image:
            cmd = [
                'ffmpeg', '-y',
                '-loop', '1', '-i', bg_path,
                '-i', audio_path,
                '-vf', self._get_sticky_header_vf(title, subtitle_style, video_format, True, dim_filter, escaped_srt, srt_style, True, cta),
                '-c:v', 'libx264', '-tune', 'stillimage', '-preset', 'fast', '-pix_fmt', 'yuv420p',
                '-c:a', 'aac', '-map', '0:v:0', '-map', '1:a:0',
                '-t', str(min(audio_duration, max_duration)),
                str(output_file)
            ]
        else:
            cmd = [
                'ffmpeg', '-y',
                '-stream_loop', '-1', '-i', bg_path,
                '-i', audio_path,
                '-vf', self._get_sticky_header_vf(title, subtitle_style, video_format, True, dim_filter, escaped_srt, srt_style, True, cta),
                '-c:v', 'libx264', '-preset', 'fast', '-pix_fmt', 'yuv420p',
                '-c:a', 'aac', '-map', '0:v:0', '-map', '1:a:0',
                '-t', str(min(audio_duration, max_duration)),
                str(output_file)
            ]
            
        try:
            result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, check=True)
            print(f"[FINAL] Successfully built short: {output_file}")
            
            # Generate thumbnail for image BG shorts using hook text
            thumbnail_path = None
            if hook and thumb_image_path:
                thumbnail_path = make_thumbnail_for_video(
                    video_title=thumb_name,
                    hook_text=hook,
                    image_path=thumb_image_path,
                    sub_dir=sub_dir,
                    thumb_dim=thumb_dim,
                    is_short=True,
                    enable_heavy_shadows=enable_heavy_shadows,
                    enable_dark_gradient_box=enable_dark_gradient_box,
                    subtitle_style=subtitle_style
                )
            return str(output_file), thumbnail_path
        except Exception as e:
            print(f"FFmpeg short assembly failed: {e}")
            if hasattr(e, 'stderr') and e.stderr:
                for line in e.stderr.strip().split('\n')[-5:]:
                    print(f"  [FFmpeg] {line}")
            return None, None


    def _parse_srt_to_json(self, srt_path: str) -> list:
        import re
        import os
        timestamps = []
        if not os.path.exists(srt_path):
            return timestamps
        with open(srt_path, 'r', encoding='utf-8') as f:
            content = f.read()
        blocks = content.strip().split('\n\n')
        for block in blocks:
            lines = block.split('\n')
            if len(lines) >= 3:
                time_line = lines[1]
                raw_text = " ".join(lines[2:]).strip()
                text = raw_text
                
                m = re.match(r'(\d+):(\d+):(\d+),(\d+)\s*-->\s*(\d+):(\d+):(\d+),(\d+)', time_line)
                if m:
                    h1, m1, s1, ms1, h2, m2, s2, ms2 = map(int, m.groups())
                    start_ms = h1*3600000 + m1*60000 + s1*1000 + ms1
                    end_ms = h2*3600000 + m2*60000 + s2*1000 + ms2
                    
                    # Split into words for perfect word-level JS chunking
                    words = text.split()
                    if not words: continue
                    duration_per_word = (end_ms - start_ms) / len(words)
                    for i, w in enumerate(words):
                        timestamps.append({
                            "text": w,
                            "start_ms": int(start_ms + i * duration_per_word),
                            "end_ms": int(start_ms + (i + 1) * duration_per_word)
                        })
        return timestamps

    async def build_infographic_part(self, title: str, ai_config: dict, part_num: int, is_last: bool, total_parts: int, channel_name: str = None, topic: str = "UnknownTopic", has_multiple_parts: bool = True, video_dim: float = -0.15, thumb_dim: float = -0.35, is_short: bool = False, voice_override: str = None, music_enabled: bool = True, subtitle_style: str = "classic", video_format: str = "vertical", enable_heavy_shadows: bool = True, enable_dark_gradient_box: bool = True, cta: str = None, max_duration: int = None, trailer_idx: int = 1, hook: str = None, bg_image_path: str = None, visual_mode: str = "infographic"):
        import asyncio
        import functools
        loop = asyncio.get_running_loop()
        func = functools.partial(
            self._build_infographic_part_sync,
            title, ai_config, part_num, is_last, total_parts, channel_name, topic, has_multiple_parts, video_dim, thumb_dim, is_short, voice_override, music_enabled, subtitle_style, video_format, enable_heavy_shadows, enable_dark_gradient_box, cta, max_duration, trailer_idx, hook, bg_image_path, visual_mode
        )
        return await loop.run_in_executor(None, func)

    def _build_infographic_part_sync(self, title: str, ai_config: dict, part_num: int, is_last: bool, total_parts: int, channel_name: str = None, topic: str = "UnknownTopic", has_multiple_parts: bool = True, video_dim: float = -0.15, thumb_dim: float = -0.35, is_short: bool = False, voice_override: str = None, music_enabled: bool = True, subtitle_style: str = "classic", video_format: str = "vertical", enable_heavy_shadows: bool = True, enable_dark_gradient_box: bool = True, cta: str = None, max_duration: int = None, trailer_idx: int = 1, hook: str = None, bg_image_path: str = None, visual_mode: str = "infographic"):
        print(f"\n--- Building INFOGRAPHIC Part {part_num} of {total_parts} ---")
        import re
        import time
        import math
        import shutil
        safe_topic = "".join([c if c.isalnum() else "_" for c in topic]).lower()
        safe_topic = re.sub(r'_+', '_', safe_topic).strip('_')[:50]
        safe_channel = channel_name if channel_name else "UnknownChannel"
        sub_dir = f"{safe_channel}/{safe_topic}"
        
        temp_dir_name = f"part_{part_num}_info_assets"
        temp_dir = OUTPUT_DIR / sub_dir / temp_dir_name
        temp_dir.mkdir(parents=True, exist_ok=True)
        
        scenes = ai_config.get("scenes", [])
        if not is_short:
            if not is_last:
                scenes[-1]['text'] += f" Subscribe for Part {part_num + 1}! Link in description."
            else:
                scenes[-1]['text'] += " Like, comment & subscribe for more!"
                
        format_type = ai_config.get("video_format", "vertical")
        template_name = ai_config.get("template", "infographic")
        
        scene_mp4s = []
        total_audio_duration = 0.0
        
        FPS = 30
        
        from playwright.sync_api import sync_playwright
        import subprocess
        
        with sync_playwright() as p:
            # Initialize browser ONCE outside the loop
            browser = p.chromium.launch(headless=True)
            width, height = (1080, 1920) if format_type == "vertical" else (1920, 1080)
            
            # For perfect mode, we reuse one page. For record mode, we create new contexts per scene.
            if visual_mode == "infographic":
                page = browser.new_page(viewport={"width": width, "height": height})
            
            for idx, scene in enumerate(scenes):
                scene_id = scene.get('id', f"scene{idx+1}")
                print(f"  [SCENE {scene_id}] Processing...")
                
                scene_audio_name = f"{scene_id}.mp3"
                # Since we are already running in a background thread, we can call this directly!
                scene_audio_path, scene_srt_path = self.voice.generate_audio(
                    scene['text'], 
                    scene_audio_name, 
                    sub_dir=f"{sub_dir}/{temp_dir_name}", 
                    voice_override=voice_override, 
                    subtitle_style="classic"
                )
                
                if not scene_audio_path:
                    print(f"  [SCENE {scene_id}] Audio failed. Skipping.")
                    continue
                    
                scene_duration = self.get_audio_duration(scene_audio_path)
                scene["duration_sec"] = scene_duration
                total_audio_duration += scene_duration
                
                # Parse SRT to JSON
                scene["word_timestamps"] = self._parse_srt_to_json(scene_srt_path)
                
                # Inject HTML
                template_file = Path("scripts/story_maker/templates") / f"template_{template_name}_{format_type}.html"
                
                if not template_file.exists():
                    # Fallback to vertical if horizontal not found or vice versa
                    print(f"  Warning: {template_file} not found. Falling back to template_infographic_vertical.html")
                    template_file = Path("scripts/story_maker/templates/template_infographic_vertical.html")
                    
                with open(template_file, "r", encoding="utf-8") as f:
                    html = f.read()
                    
                accent = scene.get("accent_color", "#ffaa00")
                html = html.replace("{{ BG_COLOR }}", scene.get("bg_color", "#0a0a0a"))
                html = html.replace("{{ ICON_COLOR }}", accent)
                
                # Convert hex to RGB for transparent CSS elements to prevent headless Chromium crash
                accent = accent.lstrip('#')
                if len(accent) == 6:
                    accent_rgb = tuple(int(accent[i:i+2], 16) for i in (0, 2, 4))
                else:
                    accent_rgb = (255, 170, 0)
                html = html.replace("{{ ICON_COLOR_RGB }}", f"{accent_rgb[0]}, {accent_rgb[1]}, {accent_rgb[2]}")
                html = html.replace("{{ TOTAL_DURATION_MS }}", str(int(scene_duration * 1000)))
                html = html.replace("{{ WORDS_JSON }}", json.dumps(scene.get("word_timestamps", [])))
                html = html.replace("{{ VISUAL_NODES_JSON }}", json.dumps(scene.get("visual_nodes", [])))
                
                # (Removed autoplay replacement to ensure manual sync)
                
                injected_path = temp_dir / f"injected_{scene_id}.html"
                with open(injected_path, "w", encoding="utf-8") as f:
                    f.write(html)
                
                scene_mp4 = temp_dir / f"{scene_id}.mp4"
                
                if visual_mode == "infographic_record":
                    print(f"  [SCENE {scene_id}] Real-Time Recording mode active ({scene_duration:.1f}s)...")
                    context = browser.new_context(
                        viewport={"width": width, "height": height},
                        record_video_dir=str(temp_dir),
                        record_video_size={"width": width, "height": height}
                    )
                    
                    record_page = context.new_page()
                    page_create_time = time.time()  # Track exact start of WebM recording
                    
                    record_page.goto(f"file:///{str(injected_path.resolve()).replace(chr(92), '/')}", wait_until="load")
                    
                    # Sleep slightly to ensure page is visually fully rendered (no white screen)
                    time.sleep(0.3)
                    
                    # Trigger animation manually and mark the time
                    play_start_time = time.time()
                    try:
                        record_page.evaluate("tl.play()")
                    except Exception as e:
                        print(f"  [SCENE {scene_id}] Warning: tl.play() failed.")
                        
                    # Sleep in real time to let the animation play out
                    time.sleep(scene_duration + 0.3)
                    
                    # Calculate exact idle time before animation started
                    idle_duration = play_start_time - page_create_time
                    
                    webm_path = record_page.video.path()
                    record_page.close()
                    context.close()
                    
                    # Mux WebM with Audio into MP4, trimming the blank load time and forcing constant framerate (fps=30) for VFR safety
                    cmd = [
                        "ffmpeg", "-y", "-i", webm_path, "-i", str(scene_audio_path),
                        "-filter_complex", f"[0:v]trim=start={idle_duration:.3f},setpts=PTS-STARTPTS,fps=30[v]",
                        "-map", "[v]", "-map", "1:a",
                        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(scene_mp4)
                    ]
                    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                else:
                    # Current perfect frame-by-frame loop
                    print(f"  [SCENE {scene_id}] Rendering frames directly to FFmpeg memory pipe...")
                    page.goto(f"file:///{str(injected_path.resolve()).replace(chr(92), '/')}", wait_until="domcontentloaded")
                    
                    try:
                        page.wait_for_function("typeof window.seekAnimation === 'function'", timeout=15000)
                    except Exception as e:
                        print(f"  [SCENE {scene_id}] Warning: seekAnimation not found or timed out.")
                    
                    print(f"  [SCENE {scene_id}] Rendering frames to disk...")
                    frame_dir = temp_dir / f"frames_{scene_id}"
                    frame_dir.mkdir(exist_ok=True)
                    
                    total_frames = int(FPS * scene_duration)
                    for frame_idx in range(total_frames):
                        timestamp_ms = (frame_idx / FPS) * 1000.0
                        try:
                            page.evaluate(f"window.seekAnimation({timestamp_ms})")
                        except:
                            pass
                        page.screenshot(path=str(frame_dir / f"frame_{frame_idx:04d}.jpg"), type="jpeg", quality=70, timeout=60000)
                        
                    print(f"  [SCENE {scene_id}] Muxing audio and video...")
                    cmd = [
                        "ffmpeg", "-y", "-framerate", str(FPS), "-i", f"{frame_dir}/frame_%04d.jpg",
                        "-i", str(scene_audio_path), 
                        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(scene_mp4)
                    ]
                    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                
                scene_mp4s.append(scene_mp4)
                
            browser.close()
                
        if not scene_mp4s:
            print("CRITICAL ERROR: No infographic scenes were built.")
            return None, None
            
        target_dir = OUTPUT_DIR / sub_dir
        
        if is_short:
            if has_multiple_parts:
                final_mp4 = target_dir / f"{safe_topic}_part_{part_num}_short_{trailer_idx}_infographic.mp4"
                thumb_name = f"{safe_topic}_part_{part_num}_short_{trailer_idx}_thumbnail"
            else:
                if trailer_idx > 1:
                    final_mp4 = target_dir / f"{safe_topic}_short_{trailer_idx}_infographic.mp4"
                    thumb_name = f"{safe_topic}_short_{trailer_idx}_thumbnail"
                else:
                    final_mp4 = target_dir / f"{safe_topic}_short_infographic.mp4"
                    thumb_name = f"{safe_topic}_short_thumbnail"
        else:
            final_mp4 = target_dir / (f"{safe_topic}_part_{part_num}_infographic.mp4" if has_multiple_parts else f"{safe_topic}_infographic.mp4")
            thumb_name = f"{safe_topic}_part_{part_num}_thumbnail" if has_multiple_parts else f"{safe_topic}_thumbnail"
            
        concat_list = temp_dir / "concat_list.txt"
        with open(concat_list, "w", encoding="utf-8") as f:
            for mp4 in scene_mp4s:
                safe_mp4 = str(mp4.resolve()).replace('\\', '/')
                f.write(f"file '{safe_mp4}'\n")
                
        concat_cmd = [
            'ffmpeg', '-y', '-nostdin',
            '-f', 'concat', '-safe', '0', '-i', str(concat_list),
            '-c', 'copy'
        ]
        
        if max_duration and max_duration > 0:
            concat_cmd.extend(['-t', str(max_duration)])
            
        concat_cmd.append(str(final_mp4))
        
        print(f"Stitching {len(scene_mp4s)} infographic scenes together...")
        try:
            subprocess.run(concat_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            
            if music_enabled:
                music_path = self.media.get_background_music(channel_name)
                if music_path:
                    mixed_mp4 = target_dir / f"{final_mp4.stem}_mixed.mp4"
                    loops = math.ceil(total_audio_duration / self.get_audio_duration(music_path)) + 1
                    music_concat = temp_dir / "music_concat.txt"
                    with open(music_concat, "w", encoding="utf-8") as f:
                        safe_music = str(Path(music_path).resolve()).replace('\\', '/')
                        for _ in range(loops):
                            f.write(f"file '{safe_music}'\n")
                            
                    mix_cmd = [
                        'ffmpeg', '-y', '-nostdin',
                        '-i', str(final_mp4),
                        '-f', 'concat', '-safe', '0', '-i', str(music_concat),
                        '-filter_complex', '[0:a]volume=1.0[v]; [1:a]volume=0.05[m]; [v][m]amix=inputs=2:duration=first:dropout_transition=0[aout]',
                        '-map', '0:v', '-map', '[aout]',
                        '-c:v', 'copy',
                        '-c:a', 'aac',
                        str(mixed_mp4)
                    ]
                    subprocess.run(mix_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
                    os.replace(mixed_mp4, final_mp4)
            
            print(f"[FINAL] Infographic Video Built: {final_mp4}")
            
            # Thumbnail Generation
            thumbnail_path = None
            try:
                thumb_dir = Path("data/thumbnails") / sub_dir
                thumb_dir.mkdir(parents=True, exist_ok=True)
                thumbnail_path = str(thumb_dir / f"{thumb_name}_thumb.jpg")
                
                # Render Thumbnail via Playwright using a static thumbnail template
                thumb_width, thumb_height = (1080, 1920) if is_short else (1920, 1080)
                thumb_template_name = "template_infographic_thumbnail_vertical.html" if is_short else "template_infographic_thumbnail_horizontal.html"
                thumb_template_file = Path(f"scripts/story_maker/templates/{thumb_template_name}")
                
                with open(thumb_template_file, "r", encoding="utf-8") as f:
                    thumb_html = f.read()
                    
                thumb_html = thumb_html.replace("{{ BG_COLOR }}", scenes[0].get("bg_color", "#0a0a0a"))
                thumb_html = thumb_html.replace("{{ ICON_COLOR }}", scenes[0].get("accent_color", "#ffaa00"))
                thumb_html = thumb_html.replace("{{ HOOK_TEXT }}", hook if hook else scenes[0].get('text', '')[:30] + "...")
                
                # Extract thumbnail icon (either explicitly defined or first icon)
                thumb_icon = ai_config.get("thumbnail_icon")
                if not thumb_icon:
                    thumb_icon = "key" # better fallback than brain
                    for node in scenes[0].get("visual_nodes", []):
                        if node.get("type") == "icon" and "keyword" in node:
                            thumb_icon = node["keyword"]
                            break
                thumb_html = thumb_html.replace("{{ ICON_KEYWORD }}", thumb_icon)
                
                thumb_injected = temp_dir / "thumb_injected.html"
                with open(thumb_injected, "w", encoding="utf-8") as f:
                    f.write(thumb_html)
                    
                import nest_asyncio
                nest_asyncio.apply()
                from playwright.sync_api import sync_playwright
                with sync_playwright() as p:
                    thumb_browser = p.chromium.launch(headless=True)
                    thumb_page = thumb_browser.new_page(viewport={"width": thumb_width, "height": thumb_height})
                    thumb_page.goto(f"file:///{str(thumb_injected.resolve()).replace(chr(92), '/')}", wait_until="domcontentloaded")
                    thumb_page.wait_for_timeout(1000)
                    thumb_page.screenshot(path=thumbnail_path, type="jpeg", quality=90)
                    thumb_browser.close()
                    
                print(f"[FINAL] Infographic Thumbnail Rendered: {thumbnail_path}")
            except Exception as e:
                import traceback
                print(f"[THUMBNAIL CRASH] Infographic thumbnail failed for {thumb_name}:")
                traceback.print_exc()
                
            try:
                shutil.rmtree(temp_dir)
            except Exception as e:
                pass
                
            return str(final_mp4), thumbnail_path
            
        except Exception as e:
            print(f"Infographic Concat failed: {e}")
            return None, None
