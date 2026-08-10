"""
thumbnail_maker.py — Standalone thumbnail generator.

Takes a background image and hook text, produces a polished thumbnail using FFmpeg.

Can be tested independently:
    python scripts/story_maker/thumbnail_maker.py --image data/backgrounds/static/my_img.jpg --hook "My wife cheated, so I took revenge." --out data/thumbnails/test.jpg
"""

import subprocess
import argparse
from pathlib import Path

THUMBNAILS_DIR = Path("data/thumbnails")
THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)


def make_thumbnail(image_path: str, hook_text: str, output_path: str, thumb_dim: float = -0.35, is_short: bool = True, subtitle_style: str = "classic", enable_heavy_shadows: bool = True, enable_dark_gradient_box: bool = True) -> str | None:
    """
    Generates a thumbnail from a background image and hook text.

    Strategy:
    - Darken and blur the image slightly for readability
    - Overlay a semi-transparent dark band across the middle
    - Render the hook text centered in bold white with a dark outline

    Args:
        image_path: Path to the source background image (jpg/png)
        hook_text: Short hook text to overlay (ideally < 15 words)
        output_path: Destination path for the output thumbnail

    Returns:
        Path to created thumbnail, or None on failure
    """
    # [DEBUG] Log all received parameters
    print(f"[THUMB DEBUG] make_thumbnail called:")
    print(f"  image_path={image_path!r}")
    print(f"  hook_text={hook_text!r}")
    print(f"  output_path={output_path!r}")
    print(f"  thumb_dim={thumb_dim!r} is_short={is_short!r}")
    print(f"  subtitle_style={subtitle_style!r} (type={type(subtitle_style).__name__})")
    print(f"  enable_heavy_shadows={enable_heavy_shadows!r} (type={type(enable_heavy_shadows).__name__})")
    print(f"  enable_dark_gradient_box={enable_dark_gradient_box!r} (type={type(enable_dark_gradient_box).__name__})")

    # Sanitize hook text for FFmpeg — escape special characters
    safe_hook = (
        hook_text
        .replace("'", "\u2019")   # Replace straight apostrophe with curly one
        .replace(":", "\\:")
        .replace(",", "\\,")
        .replace("[", "\\[")
        .replace("]", "\\]")
    )

    part_text = ""
    if "(Part " in hook_text and hook_text.endswith(")"):
        idx = hook_text.rfind("(Part ")
        part_text = hook_text[idx:].strip()
        hook_text = hook_text[:idx].strip()

    import textwrap
    
    text_len = len(hook_text)
    if text_len < 50:
        max_chars = 15 if is_short else 25
        font_size = 140 if is_short else 90
        line_spacing = 150 if is_short else 100
    elif text_len < 100:
        max_chars = 22 if is_short else 35
        font_size = 90 if is_short else 70
        line_spacing = 100 if is_short else 80
    else:
        # Ridiculously long text
        max_chars = 35 if is_short else 50
        font_size = 55 if is_short else 45
        line_spacing = 65 if is_short else 55

    wrapped_lines = textwrap.wrap(hook_text, width=max_chars)
    lines = wrapped_lines
    
    def esc(s):
        return (
            s.replace("'", "\u2019")
             .replace(":", "\\:")
             .replace(",", "\\,")
             .replace("[", "\\[")
             .replace("]", "\\]")
        )

    scale_str = "1080:1920" if is_short else "1280:720"
    
    if thumb_dim == 0:
        vf = f"scale={scale_str}:force_original_aspect_ratio=increase,crop={scale_str}"
    else:
        vf = (
            f"scale={scale_str}:force_original_aspect_ratio=increase,crop={scale_str},"
            f"eq=brightness={thumb_dim}"
        )

    # Calculate vertical starting position based on number of lines
    total_lines = len(lines) + (1 if part_text else 0)
    start_y = -((total_lines * line_spacing) // 2) + (line_spacing // 2)
    
    if enable_dark_gradient_box:
        # Dynamically calculate box height based on number of text lines with generous padding
        padding = line_spacing  # Scale padding dynamically with the font size
        box_h = (total_lines * line_spacing) + padding
        box_y = f"(ih/2)-({box_h}/2)"
        vf += f",drawbox=y={box_y}:color=black@0.6:width=iw:height={box_h}:t=fill"
    
    if enable_heavy_shadows:
        # Scale shadow and border dynamically based on font size
        shadow = str(max(4, int(font_size * 0.08)))
        border = str(max(3, int(font_size * 0.07)))
    else:
        # Perfect 0 when OFF
        shadow = "0"
        border = "0"
        
    # Strict color mapping to prevent FFmpeg errors
    from scripts.story_maker.constants import SUBTITLE_FFMPEG_COLORS
    base_color = SUBTITLE_FFMPEG_COLORS.get(subtitle_style, "white")
    
    for i, line in enumerate(lines):
        line_esc = esc(line)
        offset = start_y + (i * line_spacing)
        sign = "+" if offset >= 0 else ""
        y_pos = f"(h/2){sign}{offset}-(text_h/2)"
        
        vf += f",drawtext=font='Impact':text='{line_esc}':fontcolor={base_color}:fontsize={font_size}:x=(w-text_w)/2:y={y_pos}:shadowx={shadow}:shadowy={shadow}:shadowcolor=black:borderw={border}:bordercolor=black"
        
    if part_text:
        part_esc = esc(part_text)
        offset = start_y + (len(lines) * line_spacing)
        sign = "+" if offset >= 0 else ""
        y_pos = f"(h/2){sign}{offset}-(text_h/2)"
        vf += f",drawtext=font='Impact':text='{part_esc}':fontcolor={base_color}:fontsize={font_size}:x=(w-text_w)/2:y={y_pos}:shadowx={shadow}:shadowy={shadow}:shadowcolor=black:borderw={border}:bordercolor=black"

    cmd = [
        "ffmpeg", "-y",
        "-i", image_path,
        "-vf", vf,
        "-vframes", "1",
        "-q:v", "2",          # High quality JPEG output
        output_path
    ]

    try:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, check=True)
        print(f"Thumbnail created: {output_path}")
        return output_path
    except subprocess.CalledProcessError as e:
        print(f"Thumbnail generation failed with FFmpeg error:\n{e.stderr}")
        return None
    except Exception as e:
        import traceback
        print(f"Thumbnail generation failed with unknown error:")
        traceback.print_exc()
        return None


def make_thumbnail_for_video(video_title: str, hook_text: str, image_path: str, sub_dir: str = "", thumb_dim: float = -0.35, is_short: bool = True, subtitle_style: str = "classic", enable_heavy_shadows: bool = True, enable_dark_gradient_box: bool = True) -> str | None:
    # We will let the inner make_thumbnail function handle the debug logging

    target_dir = THUMBNAILS_DIR / sub_dir if sub_dir else THUMBNAILS_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    
    safe_title = "".join([c if c.isalnum() else "_" for c in video_title]).lower()
    output_path = str(target_dir / f"{safe_title}_thumb.jpg")
    
    # We use make_thumbnail but intercept the print statement to add [FINAL]
    result = make_thumbnail(image_path, hook_text, output_path, thumb_dim=thumb_dim, is_short=is_short, subtitle_style=subtitle_style, enable_heavy_shadows=enable_heavy_shadows, enable_dark_gradient_box=enable_dark_gradient_box)
    if result:
        print(f"[FINAL] Thumbnail created safely at: {result}")
    return result

# -------------------------
# Standalone test entrypoint
# -------------------------
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate a video thumbnail from an image and hook text")
    parser.add_argument("--image", required=True, help="Path to the background image")
    parser.add_argument("--hook", required=True, help="Hook text to overlay on the thumbnail")
    parser.add_argument("--out", default=None, help="Output path (default: data/thumbnails/test_thumb.jpg)")
    args = parser.parse_args()

    out = args.out or str(THUMBNAILS_DIR / "test_thumb.jpg")
    result = make_thumbnail(args.image, args.hook, out)
    if result:
        print(f"Success: {result}")
    else:
        print("Failed to generate thumbnail.")
