# Video Production Pipeline - Selling Master Course

## Overview

Full pipeline for producing course lesson videos:
**Script -> Slides -> Audio (TTS) -> Video Assembly**

62 lessons across 6 modules, each 15-30 minutes.

---

## Pipeline Steps

### Step 1: Script Preparation

Each lesson has a markdown script file in `content/scripts/`.

**Naming convention:** `m{module}_{lesson}_{slug}.md`
- Example: `m1_01_welcome.md`, `m2_05_dropshipping.md`

**Script format:**
```markdown
# Lesson Title

## SLIDE: Title
type: title
title: Welcome to Selling Master
subtitle: How to get the most from this course

---NARRATION---
Welcome everyone to the Selling Master course...

## SLIDE: Key Points
type: bullets
title: What You'll Learn
bullets:
- Course structure and modules
- How to study effectively
- The community

---NARRATION---
In this lesson we'll cover three main areas...

## SLIDE: Example
type: two-column
title: Physical vs Digital Products
left_title: Physical Products
left_bullets:
- Tangible inventory
- Shipping required
right_title: Digital Products
right_bullets:
- Instant delivery
- No storage costs

---NARRATION---
Let's compare these two approaches...
```

### Step 2: Slide Generation

**Tool:** `create_slides.py` (HTML-based slides)

```bash
python content/create_slides.py content/scripts/m1_01_welcome.md --output content/slides/m1_01.html
```

This generates an HTML presentation file that:
- Renders at 1920x1080 (16:9)
- Uses course brand colors (navy + gold)
- Includes avatar presenter thumbnail in corner
- Supports Hebrew RTL
- Can be opened in browser for recording/screenshotting

**Alternative slide tools (free):**
- **Canva** - drag & drop, export as images/video
- **Google Slides** - free, API available for automation
- **reveal.js** - HTML presentations (our template is based on this concept)

### Step 3: Slide Screenshots (for video assembly)

**Tool:** `generate_lesson.py` with Playwright

```bash
python content/generate_lesson.py content/scripts/m1_01_welcome.md --output content/module1/lesson01/
```

This uses Playwright (headless browser) to screenshot each slide as a PNG at 1920x1080.

**Alternative screenshot tools:**
- `playwright screenshot` (recommended, headless Chrome)
- `selenium` + Chrome driver
- `puppeteer` via Node.js
- Manual: open HTML in browser, Ctrl+S or browser DevTools screenshot

### Step 4: Audio Narration (TTS)

**Primary: ElevenLabs (paid, high quality)**
- Hebrew voices available
- API integration in `generate_lesson.py`
- Cost: ~$5/month for 30K characters (Starter plan)
- Voice ID configured per course

```python
# ElevenLabs integration point
ELEVENLABS_API_KEY = "your-api-key"
VOICE_ID = "your-hebrew-voice-id"
```

**Free alternatives:**
- **Google Cloud TTS** - free tier 1M characters/month, Hebrew support
- **Azure TTS** - free tier 500K characters/month, Hebrew support
- **Edge TTS (edge-tts Python package)** - completely free, good Hebrew quality
- **Manual recording** - record narration yourself with Audacity (free)

**edge-tts (recommended free option):**
```bash
pip install edge-tts
edge-tts --voice he-IL-AvriNeural --text "שלום לכולם" --write-media output.mp3
```

Hebrew voices in edge-tts:
- `he-IL-AvriNeural` (male)
- `he-IL-HilaNeural` (female)

### Step 5: Video Assembly

**Tool:** FFmpeg + moviepy (Python)

```bash
python content/generate_lesson.py content/scripts/m1_01_welcome.md --output content/module1/lesson01/
```

Assembly process:
1. Each slide image is shown for the duration of its narration audio
2. Avatar presenter overlay in bottom-right corner
3. Smooth transitions between slides (fade or cut)
4. Background music (optional, low volume)
5. Intro/outro cards

**FFmpeg commands used internally:**
```bash
# Combine image + audio into video segment
ffmpeg -loop 1 -i slide_01.png -i narration_01.mp3 -c:v libx264 -tune stillimage -c:a aac -b:a 192k -shortest segment_01.mp4

# Concatenate all segments
ffmpeg -f concat -safe 0 -i segments.txt -c copy lesson.mp4

# Add avatar overlay
ffmpeg -i lesson.mp4 -i avatar.png -filter_complex "overlay=W-w-40:H-h-40" final.mp4
```

**Python moviepy alternative (used in generate_lesson.py):**
```python
from moviepy.editor import ImageClip, AudioFileClip, CompositeVideoClip, concatenate_videoclips

slide = ImageClip("slide_01.png").set_duration(audio.duration)
audio = AudioFileClip("narration_01.mp3")
clip = slide.set_audio(audio)
```

---

## Directory Structure (per lesson)

```
content/
  scripts/
    m1_01_welcome.md          # Lesson script (source)
  slides/
    m1_01.html                # Generated HTML presentation
  module1/
    lesson01/
      slides/                 # Individual slide PNGs
        slide_001.png
        slide_002.png
        ...
      audio/                  # Narration audio files
        narration_001.mp3
        narration_002.mp3
        ...
      segments/               # Individual video segments
        segment_001.mp4
        segment_002.mp4
      lesson.mp4              # Final assembled video
      metadata.json           # Lesson metadata
```

---

## Tools & Dependencies

### Required (free)
- **Python 3.10+**
- **FFmpeg** - video processing (`choco install ffmpeg` or download from ffmpeg.org)
- **moviepy** - Python video editing (`pip install moviepy`)
- **Pillow** - image processing (`pip install Pillow`)
- **playwright** - browser automation for screenshots (`pip install playwright && playwright install chromium`)
- **markdown** - parse lesson scripts (`pip install markdown`)

### Optional
- **edge-tts** - free Microsoft TTS (`pip install edge-tts`)
- **elevenlabs** - paid high-quality TTS (`pip install elevenlabs`)
- **pydub** - audio manipulation (`pip install pydub`)

### Install all at once
```bash
pip install moviepy Pillow playwright markdown edge-tts pydub pyyaml
playwright install chromium
```

---

## Avatar Presenter Integration

Avatar images available at:
- `avatar_presenter_video.png` - 3:4 portrait (for side panel)
- `avatar_presenter_closeup.png` - 1:1 headshot (for corner overlay)
- `avatar_presenter_wide.png` - 16:9 wide (for intro/outro)

**Usage in videos:**
- **Corner overlay**: closeup image, bottom-right, 200x200px with rounded corners
- **Intro/Outro**: wide image as full-screen background
- **Side panel**: portrait image on right side (30% width) with slides on left

**Future: AI video avatar**
- D-ID or HeyGen can animate the avatar image into a talking head
- Synthesia offers Hebrew-speaking avatars
- Cost: $30-50/month for enough minutes

---

## Production Schedule

**Target: 2-3 lessons per week**

| Phase | Time per lesson | Notes |
|-------|----------------|-------|
| Script writing | 1-2 hours | Already partially done |
| Slide generation | 10 min (automated) | Run create_slides.py |
| Audio narration | 5 min (TTS) or 30 min (manual) | edge-tts is fastest |
| Video assembly | 5 min (automated) | Run generate_lesson.py |
| Review & QA | 15-30 min | Watch, fix issues |
| **Total** | **~1.5-3 hours** | Mostly script writing |

---

## Quick Start

```bash
# 1. Install dependencies
pip install moviepy Pillow playwright markdown edge-tts pydub pyyaml
playwright install chromium

# 2. Write a lesson script
# Edit content/scripts/m1_01_welcome.md

# 3. Generate slides HTML
python content/create_slides.py content/scripts/m1_01_welcome.md --output content/slides/m1_01.html

# 4. Preview slides in browser
start content/slides/m1_01.html

# 5. Generate full lesson video
python content/generate_lesson.py content/scripts/m1_01_welcome.md --output content/module1/lesson01/

# 6. Review the video
start content/module1/lesson01/lesson.mp4
```

---

## Brand Guidelines for Slides

| Element | Value |
|---------|-------|
| Background (dark) | #0A1628 |
| Background (medium) | #1B2D4A |
| Accent (gold) | #EEB332 |
| Text (primary) | #FFFFFF |
| Text (secondary) | #B0C4DE |
| Font (Hebrew) | Heebo |
| Font weight (titles) | 700 |
| Font weight (body) | 400 |
| Slide size | 1920 x 1080 |
| Corner radius | 12px |
| Avatar overlay size | 180x180px |
