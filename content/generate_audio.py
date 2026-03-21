#!/usr/bin/env python3
"""
Generate Hebrew audio narration from lesson scripts using ElevenLabs TTS.

Usage:
    python generate_audio.py content/scripts/m1_01_welcome.md --output content/audio/m1_01.mp3
    python generate_audio.py content/scripts/m1_01_welcome.md --voice "Israeli Male" --dry-run
    python generate_audio.py --batch content/scripts/ --output content/audio/
"""

import argparse
import os
import re
import sys
import time
from pathlib import Path

# ElevenLabs config
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY", "")
ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1"

# Default voice settings for Hebrew narration
DEFAULT_VOICE_SETTINGS = {
    "stability": 0.65,           # Slightly varied for natural feel
    "similarity_boost": 0.80,    # Stay close to voice character
    "style": 0.35,               # Some expressiveness
    "use_speaker_boost": True
}

# Hebrew male voices on ElevenLabs (check your account for available voices)
RECOMMENDED_VOICES = {
    "default": "pNInz6obpgDQGcFmaJgB",   # Adam - good for Hebrew
    "warm": "ErXwobaYiN019PkySvjV",       # Antoni
    "professional": "VR6AewLTigWG4xSOukaG", # Arnold
}


def extract_narration(script_path: str) -> str:
    """Extract only the narration text from a lesson script markdown file.

    Removes:
    - Headers (#, ##, ###)
    - SLIDE markers
    - Metadata (bold keys like **משך:**)
    - Horizontal rules (---)
    - Empty lines
    """
    with open(script_path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")
    narration_lines = []
    in_metadata = True  # Skip front matter

    for line in lines:
        stripped = line.strip()

        # Skip empty lines
        if not stripped:
            continue

        # Skip headers
        if stripped.startswith("#"):
            in_metadata = False
            continue

        # Skip horizontal rules
        if stripped == "---":
            in_metadata = False
            continue

        # Skip metadata lines (bold key-value pairs at the top)
        if in_metadata and stripped.startswith("**"):
            continue

        # Skip SLIDE markers in headers
        if "(SLIDE:" in stripped:
            continue

        # Skip task/materials lines at the bottom
        if stripped.startswith("**משימה:**") or stripped.startswith("**חומרים:**"):
            continue

        # Skip bullet list formatting but keep content
        if stripped.startswith("- ") or stripped.startswith("* "):
            narration_lines.append(stripped[2:])
            continue

        # Skip numbered list formatting but keep content
        if re.match(r"^\d+\.", stripped):
            narration_lines.append(re.sub(r"^\d+\.\s*", "", stripped))
            continue

        in_metadata = False
        narration_lines.append(stripped)

    # Join with periods for natural pauses
    text = " ".join(narration_lines)

    # Clean up markdown formatting
    text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)  # Remove bold
    text = re.sub(r"\*(.+?)\*", r"\1", text)       # Remove italic
    text = re.sub(r"`(.+?)`", r"\1", text)          # Remove code
    text = re.sub(r"\s+", " ", text)                 # Normalize whitespace

    return text.strip()


def estimate_duration(text: str) -> float:
    """Estimate audio duration in minutes based on Hebrew text length.
    Average Hebrew speech: ~130 words per minute.
    """
    words = len(text.split())
    return words / 130


def split_text(text: str, max_chars: int = 4500) -> list[str]:
    """Split text into chunks that fit ElevenLabs API limits.
    Split at sentence boundaries (periods, question marks).
    """
    if len(text) <= max_chars:
        return [text]

    chunks = []
    current = ""

    # Split by sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)

    for sentence in sentences:
        if len(current) + len(sentence) + 1 > max_chars:
            if current:
                chunks.append(current.strip())
            current = sentence
        else:
            current += " " + sentence if current else sentence

    if current:
        chunks.append(current.strip())

    return chunks


def generate_audio_elevenlabs(text: str, output_path: str, voice_id: str = None,
                               model: str = "eleven_multilingual_v2") -> bool:
    """Generate audio using ElevenLabs API."""
    try:
        import requests
    except ImportError:
        print("Error: 'requests' package required. pip install requests")
        return False

    if not ELEVENLABS_API_KEY:
        print("Error: ELEVENLABS_API_KEY not set.")
        print("Get your key from: https://elevenlabs.io/")
        return False

    voice = voice_id or RECOMMENDED_VOICES["default"]

    # Split into chunks if needed
    chunks = split_text(text)

    if len(chunks) == 1:
        # Single request
        url = f"{ELEVENLABS_API_URL}/text-to-speech/{voice}"
        headers = {
            "xi-api-key": ELEVENLABS_API_KEY,
            "Content-Type": "application/json"
        }
        payload = {
            "text": text,
            "model_id": model,
            "voice_settings": DEFAULT_VOICE_SETTINGS
        }

        resp = requests.post(url, json=payload, headers=headers)
        if resp.status_code == 200:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(resp.content)
            return True
        else:
            print(f"Error: {resp.status_code} - {resp.text[:200]}")
            return False
    else:
        # Multiple chunks - generate and concatenate
        print(f"  Text split into {len(chunks)} chunks")
        temp_files = []

        for i, chunk in enumerate(chunks):
            temp_path = output_path.replace(".mp3", f"_part{i:03d}.mp3")
            url = f"{ELEVENLABS_API_URL}/text-to-speech/{voice}"
            headers = {
                "xi-api-key": ELEVENLABS_API_KEY,
                "Content-Type": "application/json"
            }
            payload = {
                "text": chunk,
                "model_id": model,
                "voice_settings": DEFAULT_VOICE_SETTINGS
            }

            resp = requests.post(url, json=payload, headers=headers)
            if resp.status_code == 200:
                Path(temp_path).parent.mkdir(parents=True, exist_ok=True)
                with open(temp_path, "wb") as f:
                    f.write(resp.content)
                temp_files.append(temp_path)
                print(f"  Chunk {i+1}/{len(chunks)} done")
                time.sleep(1)  # Rate limit
            else:
                print(f"  Error on chunk {i+1}: {resp.status_code}")
                return False

        # Concatenate with ffmpeg
        concat_file = output_path.replace(".mp3", "_concat.txt")
        with open(concat_file, "w") as f:
            for tf in temp_files:
                f.write(f"file '{tf}'\n")

        os.system(f'ffmpeg -f concat -safe 0 -i "{concat_file}" -c copy "{output_path}" -y -loglevel error')

        # Cleanup
        os.remove(concat_file)
        for tf in temp_files:
            os.remove(tf)

        return os.path.exists(output_path)


def main():
    parser = argparse.ArgumentParser(description="Generate Hebrew audio from lesson scripts")
    parser.add_argument("script", nargs="?", help="Path to lesson script (.md)")
    parser.add_argument("-o", "--output", help="Output audio file path")
    parser.add_argument("--voice", choices=list(RECOMMENDED_VOICES.keys()), default="default",
                       help="Voice preset (default, warm, professional)")
    parser.add_argument("--voice-id", help="Custom ElevenLabs voice ID")
    parser.add_argument("--batch", help="Process all scripts in directory")
    parser.add_argument("--dry-run", action="store_true", help="Show text without generating")
    parser.add_argument("-v", "--verbose", action="store_true")

    args = parser.parse_args()

    # Batch mode
    if args.batch:
        scripts_dir = Path(args.batch)
        output_dir = Path(args.output or "content/audio")
        output_dir.mkdir(parents=True, exist_ok=True)

        scripts = sorted(scripts_dir.glob("m*_*.md"))
        print(f"Found {len(scripts)} scripts")

        for script in scripts:
            stem = script.stem  # e.g., m1_01_welcome
            output_path = output_dir / f"{stem}.mp3"

            text = extract_narration(str(script))
            duration = estimate_duration(text)

            print(f"\n{'='*50}")
            print(f"Script: {script.name}")
            print(f"Words: {len(text.split())} | Est. duration: {duration:.1f} min")

            if args.dry_run:
                print(f"First 200 chars: {text[:200]}...")
                continue

            print(f"Generating → {output_path}")
            voice_id = args.voice_id or RECOMMENDED_VOICES[args.voice]
            success = generate_audio_elevenlabs(text, str(output_path), voice_id)
            print(f"{'✅ Done' if success else '❌ Failed'}")

        return

    # Single file mode
    if not args.script:
        parser.print_help()
        return

    text = extract_narration(args.script)
    duration = estimate_duration(text)
    words = len(text.split())

    print(f"Script: {args.script}")
    print(f"Words: {words}")
    print(f"Estimated duration: {duration:.1f} minutes")
    print(f"Characters: {len(text)}")

    if args.dry_run:
        print(f"\n--- NARRATION TEXT ---")
        print(text[:1000])
        if len(text) > 1000:
            print(f"\n... ({len(text) - 1000} more characters)")
        return

    output = args.output or f"content/audio/{Path(args.script).stem}.mp3"
    voice_id = args.voice_id or RECOMMENDED_VOICES[args.voice]

    print(f"\nGenerating audio → {output}")
    success = generate_audio_elevenlabs(text, output, voice_id)

    if success:
        size = os.path.getsize(output) / (1024 * 1024)
        print(f"✅ Saved: {output} ({size:.1f} MB)")
    else:
        print("❌ Generation failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
