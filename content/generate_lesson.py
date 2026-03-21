#!/usr/bin/env python3
"""
generate_lesson.py - Full lesson video production pipeline.

Takes a lesson script and generates:
1. Individual slide images (via Playwright screenshots of HTML)
2. Audio narration (via edge-tts or ElevenLabs)
3. Final video assembly (via moviepy/ffmpeg)

Usage:
    python generate_lesson.py content/scripts/m1_01_welcome.md --output content/module1/lesson01/
    python generate_lesson.py content/scripts/m1_01_welcome.md --dry-run
    python generate_lesson.py content/scripts/m1_01_welcome.md --slides-only
    python generate_lesson.py content/scripts/m1_01_welcome.md --audio-only
    python generate_lesson.py content/scripts/m1_01_welcome.md --tts elevenlabs --voice YOUR_VOICE_ID

Requirements:
    pip install moviepy Pillow playwright markdown edge-tts pydub pyyaml
    playwright install chromium
"""

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# Add parent dir to path so we can import create_slides
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from create_slides import parse_script, generate_presentation


# ===== Configuration =====
COURSE_ROOT = Path(__file__).parent.parent  # קורס למכירה באינטרנט
AVATAR_CLOSEUP = COURSE_ROOT / "avatar_presenter_closeup.png"
AVATAR_WIDE = COURSE_ROOT / "avatar_presenter_wide.png"

# TTS Configuration
TTS_CONFIG = {
    "edge-tts": {
        "voice": "he-IL-AvriNeural",  # Hebrew male voice
        "rate": "+0%",
        "pitch": "+0Hz",
    },
    "elevenlabs": {
        "api_key": os.environ.get("ELEVENLABS_API_KEY", ""),
        "voice_id": os.environ.get("ELEVENLABS_VOICE_ID", ""),
        "model_id": "eleven_multilingual_v2",
    },
}

# Video Configuration
VIDEO_CONFIG = {
    "width": 1920,
    "height": 1080,
    "fps": 30,
    "transition_duration": 0.5,  # seconds
    "min_slide_duration": 3.0,  # minimum seconds per slide
    "avatar_size": (180, 180),  # avatar overlay size in final video
    "avatar_position": ("left", "bottom"),  # bottom-left corner
}


def ensure_output_dirs(output_path: Path):
    """Create output directory structure."""
    (output_path / "slides").mkdir(parents=True, exist_ok=True)
    (output_path / "audio").mkdir(parents=True, exist_ok=True)
    (output_path / "segments").mkdir(parents=True, exist_ok=True)


# ===== Step 1: Generate Slide Images =====

async def generate_slide_images(lesson: dict, output_path: Path, avatar_path: str):
    """Generate individual slide PNG images using Playwright."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        print("ERROR: playwright not installed. Run: pip install playwright && playwright install chromium")
        print("Falling back to HTML-only generation.")
        return generate_slide_html_only(lesson, output_path, avatar_path)

    # First generate the HTML presentation
    html_path = output_path / "presentation.html"
    avatar_rel = os.path.relpath(str(avatar_path), str(output_path)).replace("\\", "/")
    html_content = generate_presentation(lesson, avatar_path=avatar_rel)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"  Generated HTML: {html_path}")

    # Screenshot each slide using Playwright
    slide_paths = []
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})
        await page.goto(f"file:///{html_path.resolve()}")
        await page.wait_for_load_state("networkidle")

        total_slides = await page.evaluate("window.slideAPI.total")
        print(f"  Screenshotting {total_slides} slides...")

        for i in range(total_slides):
            await page.evaluate(f"window.slideAPI.goto({i})")
            await page.wait_for_timeout(300)  # Let animations settle

            slide_path = output_path / "slides" / f"slide_{i+1:03d}.png"
            await page.screenshot(path=str(slide_path))
            slide_paths.append(slide_path)
            print(f"    Slide {i+1}/{total_slides}: {slide_path.name}")

        await browser.close()

    return slide_paths


def generate_slide_html_only(lesson: dict, output_path: Path, avatar_path: str):
    """Fallback: just generate the HTML file without screenshots."""
    html_path = output_path / "presentation.html"
    avatar_rel = os.path.relpath(str(avatar_path), str(output_path)).replace("\\", "/")
    html_content = generate_presentation(lesson, avatar_path=avatar_rel)

    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"  Generated HTML presentation: {html_path}")
    print("  (Install playwright for automatic slide screenshots)")
    return []


# ===== Step 2: Generate Audio Narration =====

async def generate_audio_edge_tts(narrations: list, output_path: Path, config: dict) -> list:
    """Generate audio files using edge-tts (free Microsoft TTS)."""
    try:
        import edge_tts
    except ImportError:
        print("ERROR: edge-tts not installed. Run: pip install edge-tts")
        return generate_audio_placeholder(narrations, output_path)

    audio_paths = []
    voice = config.get("voice", "he-IL-AvriNeural")
    rate = config.get("rate", "+0%")

    for i, text in enumerate(narrations):
        if not text.strip():
            # Create a short silence for slides without narration
            audio_path = output_path / "audio" / f"narration_{i+1:03d}.mp3"
            await create_silence(audio_path, duration=3.0)
            audio_paths.append(audio_path)
            print(f"    Audio {i+1}: (silence - no narration)")
            continue

        audio_path = output_path / "audio" / f"narration_{i+1:03d}.mp3"
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        await communicate.save(str(audio_path))
        audio_paths.append(audio_path)
        print(f"    Audio {i+1}: {audio_path.name} ({len(text)} chars)")

    return audio_paths


def generate_audio_elevenlabs(narrations: list, output_path: Path, config: dict) -> list:
    """Generate audio files using ElevenLabs API."""
    api_key = config.get("api_key", "")
    voice_id = config.get("voice_id", "")
    model_id = config.get("model_id", "eleven_multilingual_v2")

    if not api_key or not voice_id:
        print("ERROR: ElevenLabs API key and voice ID required.")
        print("  Set ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID environment variables,")
        print("  or use --tts edge-tts for free alternative.")
        return generate_audio_placeholder(narrations, output_path)

    try:
        import requests
    except ImportError:
        print("ERROR: requests not installed. Run: pip install requests")
        return generate_audio_placeholder(narrations, output_path)

    audio_paths = []
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key,
    }

    for i, text in enumerate(narrations):
        if not text.strip():
            audio_path = output_path / "audio" / f"narration_{i+1:03d}.mp3"
            # Create silence placeholder
            with open(audio_path, "wb") as f:
                f.write(b"")  # Empty file - will be replaced with silence
            audio_paths.append(audio_path)
            print(f"    Audio {i+1}: (silence)")
            continue

        audio_path = output_path / "audio" / f"narration_{i+1:03d}.mp3"
        data = {
            "text": text,
            "model_id": model_id,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
            },
        }

        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            with open(audio_path, "wb") as f:
                f.write(response.content)
            audio_paths.append(audio_path)
            print(f"    Audio {i+1}: {audio_path.name} ({len(text)} chars)")
        else:
            print(f"    Audio {i+1}: ERROR {response.status_code} - {response.text[:100]}")
            audio_paths.append(None)

    return audio_paths


def generate_audio_placeholder(narrations: list, output_path: Path) -> list:
    """Generate placeholder text files instead of actual audio."""
    audio_paths = []
    for i, text in enumerate(narrations):
        placeholder_path = output_path / "audio" / f"narration_{i+1:03d}.txt"
        with open(placeholder_path, "w", encoding="utf-8") as f:
            f.write(f"[NARRATION PLACEHOLDER]\n\n{text}\n\nCharacter count: {len(text)}\n")
            f.write(f"Estimated duration: {max(3, len(text) / 12):.1f} seconds\n")
        audio_paths.append(placeholder_path)
        print(f"    Placeholder {i+1}: {placeholder_path.name} ({len(text)} chars)")
    return audio_paths


async def create_silence(output_path: Path, duration: float = 3.0):
    """Create a silent audio file."""
    try:
        from pydub import AudioSegment
        from pydub.generators import Sine
        # Generate silence
        silence = AudioSegment.silent(duration=int(duration * 1000))
        silence.export(str(output_path), format="mp3")
    except ImportError:
        # Fallback: create empty file
        with open(output_path, "wb") as f:
            f.write(b"")


# ===== Step 3: Assemble Video =====

def assemble_video_moviepy(slide_paths: list, audio_paths: list, output_path: Path):
    """Assemble final video using moviepy."""
    try:
        from moviepy.editor import (
            ImageClip, AudioFileClip, CompositeVideoClip,
            concatenate_videoclips, ColorClip
        )
    except ImportError:
        print("ERROR: moviepy not installed. Run: pip install moviepy")
        print("Generating ffmpeg script instead...")
        return generate_ffmpeg_script(slide_paths, audio_paths, output_path)

    if not slide_paths:
        print("  No slide images available. Skipping video assembly.")
        return None

    clips = []
    for i, (slide_path, audio_path) in enumerate(zip(slide_paths, audio_paths)):
        if audio_path is None or not audio_path.exists() or audio_path.suffix == ".txt":
            # No audio - use minimum duration
            duration = VIDEO_CONFIG["min_slide_duration"]
            slide_clip = ImageClip(str(slide_path)).set_duration(duration)
        else:
            try:
                audio_clip = AudioFileClip(str(audio_path))
                duration = max(audio_clip.duration, VIDEO_CONFIG["min_slide_duration"])
                slide_clip = ImageClip(str(slide_path)).set_duration(duration)
                slide_clip = slide_clip.set_audio(audio_clip)
            except Exception as e:
                print(f"  Warning: Could not load audio for slide {i+1}: {e}")
                duration = VIDEO_CONFIG["min_slide_duration"]
                slide_clip = ImageClip(str(slide_path)).set_duration(duration)

        clips.append(slide_clip)
        print(f"    Segment {i+1}: {duration:.1f}s")

    if not clips:
        print("  No clips to assemble.")
        return None

    # Concatenate all clips
    print("  Concatenating clips...")
    final = concatenate_videoclips(clips, method="compose")

    # Export
    lesson_path = output_path / "lesson.mp4"
    print(f"  Exporting to {lesson_path}...")
    final.write_videofile(
        str(lesson_path),
        fps=VIDEO_CONFIG["fps"],
        codec="libx264",
        audio_codec="aac",
        audio_bitrate="192k",
        preset="medium",
        threads=4,
    )

    # Cleanup
    final.close()
    for clip in clips:
        clip.close()

    print(f"  Video saved: {lesson_path}")
    return lesson_path


def generate_ffmpeg_script(slide_paths: list, audio_paths: list, output_path: Path):
    """Generate a bash script with ffmpeg commands for manual assembly."""
    script_lines = ["#!/bin/bash", "# FFmpeg video assembly script", "# Generated by generate_lesson.py", ""]

    segments_file = output_path / "segments" / "segments.txt"
    segment_entries = []

    for i, (slide_path, audio_path) in enumerate(zip(slide_paths, audio_paths)):
        segment_path = output_path / "segments" / f"segment_{i+1:03d}.mp4"

        if audio_path and audio_path.exists() and audio_path.suffix == ".mp3":
            # Slide + audio -> video segment
            script_lines.append(
                f'ffmpeg -loop 1 -i "{slide_path}" -i "{audio_path}" '
                f'-c:v libx264 -tune stillimage -c:a aac -b:a 192k '
                f'-pix_fmt yuv420p -shortest "{segment_path}"'
            )
        else:
            # Slide only - 5 second still
            script_lines.append(
                f'ffmpeg -loop 1 -i "{slide_path}" -t 5 '
                f'-c:v libx264 -tune stillimage -pix_fmt yuv420p "{segment_path}"'
            )

        segment_entries.append(f"file '{segment_path}'")

    # Write segments list
    with open(segments_file, "w", encoding="utf-8") as f:
        f.write("\n".join(segment_entries))

    # Concatenation command
    lesson_path = output_path / "lesson.mp4"
    script_lines.append("")
    script_lines.append(f'# Concatenate all segments')
    script_lines.append(
        f'ffmpeg -f concat -safe 0 -i "{segments_file}" -c copy "{lesson_path}"'
    )

    # Write script
    script_path = output_path / "assemble.sh"
    with open(script_path, "w", encoding="utf-8") as f:
        f.write("\n".join(script_lines))

    print(f"  FFmpeg script saved: {script_path}")
    print(f"  Run it manually: bash {script_path}")
    return script_path


# ===== Metadata =====

def save_metadata(lesson: dict, output_path: Path, slide_paths: list, audio_paths: list):
    """Save lesson metadata as JSON."""
    metadata = {
        "title": lesson["title"],
        "lesson_info": lesson["lesson_info"],
        "module": lesson["module_num"],
        "lesson": lesson["lesson_num"],
        "total_slides": len(lesson["slides"]),
        "slides": [],
        "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }

    for i, slide in enumerate(lesson["slides"]):
        slide_meta = {
            "index": i + 1,
            "type": slide.get("type", "bullets"),
            "title": slide.get("title", slide.get("slide_title", "")),
            "narration_length": len(slide.get("narration", "")),
        }
        if i < len(slide_paths) and slide_paths[i]:
            slide_meta["image"] = str(slide_paths[i])
        if i < len(audio_paths) and audio_paths[i]:
            slide_meta["audio"] = str(audio_paths[i])
        metadata["slides"].append(slide_meta)

    meta_path = output_path / "metadata.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2)

    print(f"  Metadata saved: {meta_path}")


# ===== Main Pipeline =====

async def run_pipeline(args):
    """Run the full lesson generation pipeline."""

    # Parse the script
    print(f"\n{'='*60}")
    print(f"  LESSON VIDEO PIPELINE")
    print(f"{'='*60}")
    print(f"\nScript: {args.script}")

    lesson = parse_script(args.script)
    print(f"Title: {lesson['title']}")
    print(f"Info: {lesson['lesson_info']}")
    print(f"Slides: {len(lesson['slides'])}")

    # Extract narrations
    narrations = [s.get("narration", "") for s in lesson["slides"]]
    total_chars = sum(len(n) for n in narrations)
    print(f"Total narration: {total_chars} characters")
    print(f"Estimated duration: {max(60, total_chars / 12):.0f} seconds")

    if args.dry_run:
        print(f"\n--- DRY RUN ---")
        print(f"Would create output at: {args.output}")
        print(f"\nSlides to generate:")
        for i, slide in enumerate(lesson["slides"], 1):
            stype = slide.get("type", "bullets")
            stitle = slide.get("title", slide.get("slide_title", ""))
            narr = slide.get("narration", "")
            print(f"  {i}. [{stype}] {stitle}")
            if narr:
                print(f"     Narration: {narr[:80]}{'...' if len(narr) > 80 else ''}")
        print(f"\nAudio engine: {args.tts}")
        print(f"\nFiles that would be created:")
        print(f"  {args.output}/presentation.html")
        for i in range(len(lesson["slides"])):
            print(f"  {args.output}/slides/slide_{i+1:03d}.png")
            print(f"  {args.output}/audio/narration_{i+1:03d}.mp3")
        print(f"  {args.output}/lesson.mp4")
        print(f"  {args.output}/metadata.json")
        return

    output_path = Path(args.output)
    ensure_output_dirs(output_path)

    avatar_path = AVATAR_CLOSEUP
    if args.avatar:
        avatar_path = Path(args.avatar)

    # Step 1: Generate slides
    slide_paths = []
    if not args.audio_only:
        print(f"\n--- Step 1: Generating slide images ---")
        slide_paths = await generate_slide_images(lesson, output_path, str(avatar_path))

    # Step 2: Generate audio
    audio_paths = []
    if not args.slides_only:
        print(f"\n--- Step 2: Generating audio narration ({args.tts}) ---")
        if args.tts == "edge-tts":
            audio_paths = await generate_audio_edge_tts(
                narrations, output_path, TTS_CONFIG["edge-tts"]
            )
        elif args.tts == "elevenlabs":
            audio_paths = generate_audio_elevenlabs(
                narrations, output_path, TTS_CONFIG["elevenlabs"]
            )
        else:
            audio_paths = generate_audio_placeholder(narrations, output_path)

    # Step 3: Assemble video
    if not args.slides_only and not args.audio_only and slide_paths and audio_paths:
        print(f"\n--- Step 3: Assembling video ---")
        assemble_video_moviepy(slide_paths, audio_paths, output_path)

    # Save metadata
    print(f"\n--- Saving metadata ---")
    save_metadata(lesson, output_path, slide_paths, audio_paths)

    print(f"\n{'='*60}")
    print(f"  DONE!")
    print(f"  Output: {output_path}")
    print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="Generate lesson video from script (slides + audio + video)"
    )
    parser.add_argument("script", help="Path to the markdown lesson script")
    parser.add_argument(
        "--output", "-o",
        required=True,
        help="Output directory for lesson assets"
    )
    parser.add_argument(
        "--tts",
        choices=["edge-tts", "elevenlabs", "none"],
        default="edge-tts",
        help="TTS engine to use (default: edge-tts)"
    )
    parser.add_argument(
        "--voice",
        help="Voice ID (overrides default for selected TTS engine)"
    )
    parser.add_argument(
        "--avatar",
        help="Path to avatar image (default: avatar_presenter_closeup.png)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be created without generating files"
    )
    parser.add_argument(
        "--slides-only",
        action="store_true",
        help="Only generate slide images, skip audio and video"
    )
    parser.add_argument(
        "--audio-only",
        action="store_true",
        help="Only generate audio narration, skip slides and video"
    )

    args = parser.parse_args()

    if not os.path.exists(args.script):
        print(f"Error: Script file not found: {args.script}", file=sys.stderr)
        sys.exit(1)

    # Override voice if specified
    if args.voice:
        if args.tts == "edge-tts":
            TTS_CONFIG["edge-tts"]["voice"] = args.voice
        elif args.tts == "elevenlabs":
            TTS_CONFIG["elevenlabs"]["voice_id"] = args.voice

    asyncio.run(run_pipeline(args))


if __name__ == "__main__":
    main()
