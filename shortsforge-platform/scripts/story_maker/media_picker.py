import os
import random
import subprocess
import requests
from pathlib import Path
from ddgs import DDGS  # Updated import per library rename
from core.config import PEXELS_API_KEY, PIXABAY_API_KEY

# Paths
BG_DIR = Path("data/backgrounds")
GAMEPLAY_FILE = BG_DIR / "gameplay.mp4"
OUTPUT_DIR = Path("data/video_temp")

BG_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

class MediaPicker:
    """Selects and slices background media (Gameplay or Static Image) for stories."""
    
    def __init__(self):
        try:
            self.ddgs = DDGS()
        except:
            self.ddgs = None

    def get_video_duration(self, filepath):
        """Uses ffprobe to get video duration in seconds."""
        cmd = [
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
            '-of', 'default=noprint_wrappers=1:nokey=1', str(filepath)
        ]
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            return float(result.stdout.strip())
        except Exception as e:
            print(f"Error getting duration for {filepath}: {e}")
            return 0.0

    def get_background_video(self, required_duration: float, output_filename: str, channel_name: str = None, sub_dir: str = ""):
        """
        Slices a random chunk from a background video.
        Checks channel-specific folder first, then falls back to default GAMEPLAY_FILE.
        """
        target_file = None
        
        if channel_name:
            channel_video = BG_DIR / channel_name / "gameplay.mp4"
            if channel_video.exists():
                target_file = channel_video
        
        # If we didn't want a channel, or we wanted one and couldn't find it, we return None
        # EXCEPT if this function is called specifically to get the global fallback!
        if not target_file:
            # Only use global GAMEPLAY_FILE if we are explicitly asking for global fallback (no channel_name)
            if not channel_name:
                target_file = GAMEPLAY_FILE
            else:
                return None
                    
        if not target_file or not target_file.exists():
            return None

        total_duration = self.get_video_duration(target_file)
        
        # We need to leave room for the required duration
        if total_duration <= required_duration:
            start_time = 0.0
        else:
            max_start = total_duration - required_duration - 1.0 # 1 sec buffer
            start_time = random.uniform(0.0, max_start)
            
        target_dir = OUTPUT_DIR / sub_dir if sub_dir else OUTPUT_DIR
        target_dir.mkdir(parents=True, exist_ok=True)
        output_path = target_dir / output_filename
        
        # FFmpeg command to slice fast and mute audio
        cmd = [
            'ffmpeg', '-y', 
            '-ss', str(start_time),
            '-i', str(target_file),
            '-t', str(required_duration),
            '-an', # Remove original game audio
            '-c:v', 'libx264', '-preset', 'fast', '-crf', '23', '-pix_fmt', 'yuv420p',
            str(output_path)
        ]
        
        print(f"[TEMP] Slicing gameplay video from {start_time:.2f}s for {required_duration}s into {output_path}...")
        try:
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return str(output_path)
        except Exception as e:
            print(f"FFmpeg slicing failed: {e}")
            return None

    def get_static_image(self, channel_name: str = None):
        """Returns a random static image. Checks channel-specific folder first, then universal BG_DIR."""
        images = []
        if channel_name:
            channel_dir = BG_DIR / channel_name
            if channel_dir.exists():
                images = list(channel_dir.glob("*.jpg")) + list(channel_dir.glob("*.png"))
                
        if not images and not channel_name:
            # Only use universal static images if we didn't specifically ask for a channel
            images = list(BG_DIR.glob("*.jpg")) + list(BG_DIR.glob("*.png"))
            
        if not images:
            return None
        return str(random.choice(images))

    def _download_and_verify_image(self, url: str, save_path: Path, source_name: str) -> int:
        """
        Downloads an image and performs strict 3-layer security sanitization.
        Returns file_size (int) if successful and safe, or -1 if malicious/corrupt/failed.
        """
        try:
            response = requests.get(url, timeout=10)
            
            # 1. Content-Type Security Check
            content_type = response.headers.get("Content-Type", "").lower()
            if "text/html" in content_type or "application" in content_type:
                print(f"  [SECURITY] Blocked non-image payload from {source_name} (Content-Type: {content_type}): {url[:60]}")
                return -1
                
            img_data = response.content
            file_size = len(img_data)
            
            with open(save_path, "wb") as f:
                f.write(img_data)
                
            # 2 & 3. Pillow Magic Bytes Verification and EXIF Sanitization
            from PIL import Image
            try:
                with Image.open(save_path) as img:
                    img.verify()
                with Image.open(save_path) as img:
                    safe_img = img.convert("RGB")
                    safe_img.save(save_path, "JPEG", quality=90)
            except Exception as sec_err:
                print(f"  [SECURITY] Image validation failed (Corrupt or Disguised). Deleting {save_path.name}")
                try:
                    os.remove(save_path)
                except Exception:
                    pass
                return -1
                
            return file_size
        except Exception as e:
            print(f"  Failed to download from {source_name}: {e}")
            return -1

    def fetch_internet_image(self, query: str, style: str = "", sub_dir: str = "", is_temp: bool = False):
        """
        Searches and downloads a contextual background image.

        Strategy:
        - Adds art style bias to the search query (anime/digital art, no people)
        - Downloads up to 3 candidate images
        - Picks the largest file (largest file = most detail = best quality proxy)
        - Rejects images smaller than 50KB (likely thumbnails/icons/watermarked junk)

        Args:
            query: Story title or context for the image search
            style: Art style preference appended to the query
            sub_dir: Channel/Story topic subdirectory
        """
        if not self.ddgs:
            print("DDGS not initialized.")
            return None

        styled_query = f"{query} {style}".strip()
        print(f"Searching for image: '{styled_query}'...")

        MIN_FILE_SIZE_BYTES = 50_000  # Reject images smaller than 50KB

        try:
            results = list(self.ddgs.images(styled_query, max_results=5, safesearch="on"))
            if not results:
                # Fallback: try without style bias
                print(f"FALLBACK: No images found for styled query. Falling back to basic query: '{query}'")
                results = list(self.ddgs.images(query, max_results=5, safesearch="on"))
            if not results:
                return None

            candidates = []
            safe_name = "".join([c if c.isalnum() else "_" for c in query]).strip("_")[:30]
            
            if is_temp and sub_dir:
                target_dir = OUTPUT_DIR / sub_dir
            else:
                channel_name = sub_dir.split('/')[0] if sub_dir else None
                if channel_name:
                    target_dir = BG_DIR / channel_name / "downloads"
                else:
                    target_dir = BG_DIR / "downloads"
            
            target_dir.mkdir(parents=True, exist_ok=True)

            for idx, res in enumerate(results):
                image_url = res.get("image")
                if not image_url:
                    continue
                try:
                    save_path = target_dir / f"{safe_name}_candidate_{idx}.jpg"
                    file_size = self._download_and_verify_image(image_url, save_path, "DuckDuckGo")
                    
                    if file_size == -1:
                        continue
                        
                    if file_size < MIN_FILE_SIZE_BYTES:
                        print(f"  Skipping small image ({file_size // 1024}KB): {image_url[:60]}")
                        try:
                            os.remove(save_path)
                        except Exception:
                            pass
                        continue

                    candidates.append((file_size, str(save_path)))
                    print(f"  Candidate {idx}: {file_size // 1024}KB [Verified Clean]")

                except Exception as e:
                    print(f"  Unexpected error on candidate {idx}: {e}")
                    continue

            if not candidates:
                return None

            # Pick the largest file as the best quality proxy
            candidates.sort(key=lambda x: x[0], reverse=True)
            best_path = candidates[0][1]
            print(f"[FINAL] Selected best image: {best_path} ({candidates[0][0] // 1024}KB)")
            
            # Clean up the unused candidates
            for size, path in candidates[1:]:
                try:
                    os.remove(path)
                except Exception:
                    pass
                    
            return best_path

        except Exception as e:
            print(f"Internet image search failed: {e}")
            return None

    def fetch_pixabay_image(self, query: str, style: str = "", sub_dir: str = "", is_temp: bool = False):
        if not PIXABAY_API_KEY:
            print("Pixabay API key not set.")
            return None
        
        styled_query = f"{query} {style} scenery".strip()
        print(f"Searching Pixabay for: '{styled_query}'...")
        try:
            params = {
                "key": PIXABAY_API_KEY,
                "q": styled_query,
                "image_type": "photo",
                "per_page": 5,
                "safesearch": "true",
                "orientation": "horizontal"
            }
            response = requests.get("https://pixabay.com/api/", params=params, timeout=10)
            response.raise_for_status()
            hits = response.json().get("hits", [])
            if not hits:
                return None
            
            image_url = hits[0].get("largeImageURL")
            if not image_url:
                return None
            safe_name = "".join([c if c.isalnum() else "_" for c in query]).strip("_")[:30]
            if is_temp and sub_dir:
                target_dir = OUTPUT_DIR / sub_dir
            else:
                channel_name = sub_dir.split('/')[0] if sub_dir else None
                if channel_name:
                    target_dir = BG_DIR / channel_name / "downloads"
                else:
                    target_dir = BG_DIR / "downloads"
            target_dir.mkdir(parents=True, exist_ok=True)
            
            save_path = target_dir / f"{safe_name}_pixabay.jpg"
            file_size = self._download_and_verify_image(image_url, save_path, "Pixabay")
            if file_size == -1:
                return None
                
            return str(save_path)
        except Exception as e:
            print(f"Pixabay search failed: {e}")
            return None

    def fetch_pexels_image(self, query: str, style: str = "anime illustration digital art", sub_dir: str = "", is_temp: bool = False):
        if not PEXELS_API_KEY:
            print("Pexels API key not set.")
            return None
            
        styled_query = f"{query} {style} scenery"
        print(f"Searching Pexels for: '{styled_query}'...")
        try:
            headers = {"Authorization": PEXELS_API_KEY}
            params = {"query": styled_query, "per_page": 5, "orientation": "landscape"}
            response = requests.get("https://api.pexels.com/v1/search", headers=headers, params=params, timeout=10)
            response.raise_for_status()
            photos = response.json().get("photos", [])
            if not photos:
                return None
                
            image_url = photos[0].get("src", {}).get("large2x") or photos[0].get("src", {}).get("large")
            if not image_url:
                return None
            safe_name = "".join([c if c.isalnum() else "_" for c in query]).strip("_")[:30]
            
            if is_temp and sub_dir:
                target_dir = OUTPUT_DIR / sub_dir
            else:
                channel_name = sub_dir.split('/')[0] if sub_dir else None
                if channel_name:
                    target_dir = BG_DIR / channel_name / "downloads"
                else:
                    target_dir = BG_DIR / "downloads"
            target_dir.mkdir(parents=True, exist_ok=True)
            
            save_path = target_dir / f"{safe_name}_pexels.jpg"
            file_size = self._download_and_verify_image(image_url, save_path, "Pexels")
            if file_size == -1:
                return None
                
            return str(save_path)
        except Exception as e:
            print(f"Pexels search failed: {e}")
            return None

    def get_background_music(self, channel_name: str = None) -> str:
        """Returns a random music file. Checks channel-specific folder first, then global folder."""
        music_files = []
        if channel_name:
            channel_music_dir = BG_DIR / channel_name / "music"
            if channel_music_dir.exists():
                music_files = list(channel_music_dir.glob("*.mp3")) + list(channel_music_dir.glob("*.wav"))
                
        if not music_files:
            global_music_dir = BG_DIR / "global_music"
            if global_music_dir.exists():
                music_files = list(global_music_dir.glob("*.mp3")) + list(global_music_dir.glob("*.wav"))
                
        if not music_files:
            return None
            
        return str(random.choice(music_files))

if __name__ == "__main__":
    picker = MediaPicker()
    print("Checking for gameplay file...")
    if GAMEPLAY_FILE.exists():
        print(f"Found {GAMEPLAY_FILE}. Duration: {picker.get_video_duration(GAMEPLAY_FILE)}s")
    else:
        print(f"Gameplay file missing at {GAMEPLAY_FILE}")
