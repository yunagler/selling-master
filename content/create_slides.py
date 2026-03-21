#!/usr/bin/env python3
"""
create_slides.py - Generate HTML slide presentation from a lesson script.

Usage:
    python create_slides.py content/scripts/m1_01_welcome.md --output content/slides/m1_01.html
    python create_slides.py content/scripts/m1_01_welcome.md  # outputs to stdout

Reads markdown lesson scripts with SLIDE markers and generates a complete
HTML presentation file that can be opened in a browser.

Script format:
    ## SLIDE: Slide Title
    type: title|bullets|two-column|quote|example|exercise|image|section
    title: The Title
    subtitle: Optional subtitle
    bullets:
    - First point
    - Second point
    left_title: Left Column Title
    left_bullets:
    - Left item
    right_title: Right Column Title
    right_bullets:
    - Right item
    quote: The quote text
    author: Quote author
    content: Free-form content for example slides
    steps:
    - Step one
    - Step two
    section_number: 02

    ---NARRATION---
    The narration text for TTS (ignored by this script).
"""

import argparse
import re
import sys
import os
from pathlib import Path
from html import escape


# ===== Brand Configuration =====
BRAND = {
    "navy_dark": "#0A1628",
    "navy_mid": "#1B2D4A",
    "navy_light": "#2A4060",
    "gold": "#EEB332",
    "gold_light": "#F5CC66",
    "white": "#FFFFFF",
    "text_secondary": "#B0C4DE",
    "text_dim": "#6B8299",
    "font": "Heebo",
    "course_name": "SELLING MASTER",
}


def parse_script(filepath: str) -> dict:
    """Parse a markdown lesson script into structured slide data.

    Supports two formats:
    1. Structured format: ## SLIDE: Title (with type:, bullets:, etc.)
    2. Prose format: ### Section Title (SLIDE: slide description)
       followed by narration text paragraphs.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    # Extract lesson title (first H1)
    title_match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    lesson_title = title_match.group(1).strip() if title_match else "Untitled Lesson"

    # Extract module/lesson info from filename or H2
    fname = Path(filepath).stem
    module_match = re.match(r"m(\d+)_(\d+)", fname)
    if module_match:
        module_num = int(module_match.group(1))
        lesson_num = int(module_match.group(2))
        lesson_info = f"מודול {module_num} | שיעור {module_num}.{lesson_num}"
    else:
        module_num = 1
        lesson_num = 1
        lesson_info = ""

    # Detect format: structured (## SLIDE:) or prose (### Title (SLIDE:))
    has_structured = re.search(r"^##\s+SLIDE:", content, re.MULTILINE)
    has_prose = re.search(r"^###\s+.+\(SLIDE:", content, re.MULTILINE)

    slides = []

    if has_structured:
        # Structured format: ## SLIDE: Title
        slide_blocks = re.split(r"^##\s+SLIDE:\s*", content, flags=re.MULTILINE)
        for block in slide_blocks[1:]:
            slide = parse_slide_block(block)
            if slide:
                slides.append(slide)

    elif has_prose:
        # Prose format: ### Title (SLIDE: description)
        slides = parse_prose_format(content)

    else:
        # Fallback: try to split by ### headings and treat each as a slide
        slides = parse_prose_format(content)

    return {
        "title": lesson_title,
        "lesson_info": lesson_info,
        "module_num": module_num,
        "lesson_num": lesson_num,
        "slides": slides,
    }


def parse_prose_format(content: str) -> list:
    """Parse prose-style scripts with ### Title (SLIDE: description) markers.

    In this format, each ### section is a slide. The heading contains
    the slide description in parentheses, and the body text becomes
    the narration. Bold items (**text**) in the body are extracted
    as bullet points for the slide.
    """
    slides = []

    # Split by ### headings
    sections = re.split(r"^###\s+", content, flags=re.MULTILINE)

    for section in sections[1:]:  # Skip content before first ###
        lines = section.strip().split("\n")
        if not lines:
            continue

        heading = lines[0].strip()
        body = "\n".join(lines[1:]).strip()

        # Remove trailing --- and metadata (משימה:, חומרים:)
        body = re.split(r"^---\s*$", body, flags=re.MULTILINE)[0].strip()

        # Extract SLIDE description from heading
        slide_match = re.search(r"\(SLIDE:\s*(.+?)\)$", heading)
        if slide_match:
            slide_desc = slide_match.group(1).strip()
            section_title = re.sub(r"\s*\(SLIDE:.*?\)\s*$", "", heading).strip()
        else:
            slide_desc = heading
            section_title = heading

        # Extract bold items as potential bullet points
        bold_items = re.findall(r"\*\*(.+?)\*\*", body)

        # Build narration: the full body text, cleaned
        narration = body.strip()
        # Remove markdown bold markers for clean narration
        narration_clean = re.sub(r"\*\*(.+?)\*\*", r"\1", narration)

        # Determine slide type based on content
        if len(bold_items) >= 3:
            # Multiple bold items -> bullets slide
            # Extract text following each bold item on the same line
            bullet_texts = []
            for match in re.finditer(r"\*\*(.+?)\*\*\s*[-–:]?\s*(.+?)(?:\n|$)", body):
                bold_part = match.group(1)
                rest = match.group(2).strip().rstrip(".")
                if rest:
                    bullet_texts.append(f"**{bold_part}** - {rest}")
                else:
                    bullet_texts.append(f"**{bold_part}**")

            if not bullet_texts:
                bullet_texts = [f"**{b}**" for b in bold_items]

            # Limit to 6 bullets max for readability
            bullet_texts = bullet_texts[:6]

            slides.append({
                "slide_title": section_title,
                "type": "bullets",
                "title": section_title,
                "bullets": bullet_texts,
                "narration": narration_clean,
            })
        elif "סיכום" in section_title or "סיום" in section_title or "נתחיל" in slide_desc:
            # Closing slide -> title type
            slides.append({
                "slide_title": section_title,
                "type": "title",
                "title": slide_desc if slide_desc != heading else section_title,
                "subtitle": "",
                "narration": narration_clean,
            })
        else:
            # Default to bullets with extracted content
            # Try to find any list-like patterns in body
            list_items = re.findall(r"^[-*]\s+(.+)$", body, re.MULTILINE)
            if list_items:
                slides.append({
                    "slide_title": section_title,
                    "type": "bullets",
                    "title": section_title,
                    "bullets": list_items[:6],
                    "narration": narration_clean,
                })
            elif bold_items:
                slides.append({
                    "slide_title": section_title,
                    "type": "bullets",
                    "title": section_title,
                    "bullets": [f"**{b}**" for b in bold_items[:6]],
                    "narration": narration_clean,
                })
            else:
                # Simple content slide with the text as narration
                # Show first sentence or description as subtitle
                first_sentence = narration_clean.split(".")[0] + "." if "." in narration_clean else narration_clean[:100]
                slides.append({
                    "slide_title": section_title,
                    "type": "title",
                    "title": section_title,
                    "subtitle": slide_desc if slide_desc != section_title else "",
                    "narration": narration_clean,
                })

    return slides


def parse_slide_block(block: str) -> dict:
    """Parse a single slide block into a dict."""
    # Split off narration
    parts = block.split("---NARRATION---")
    slide_content = parts[0]
    narration = parts[1].strip() if len(parts) > 1 else ""

    lines = slide_content.strip().split("\n")
    if not lines:
        return None

    # First line is the slide title (from ## SLIDE: Title)
    slide_title = lines[0].strip()

    # Parse key-value pairs and lists
    slide = {
        "slide_title": slide_title,
        "type": "bullets",  # default
        "narration": narration,
    }

    current_list_key = None
    current_list = []

    for line in lines[1:]:
        line = line.rstrip()

        # Check for list item
        if line.strip().startswith("- ") and current_list_key:
            current_list.append(line.strip()[2:])
            continue

        # Save previous list if any
        if current_list_key and current_list:
            slide[current_list_key] = current_list
            current_list_key = None
            current_list = []

        # Check for key: value pairs
        kv_match = re.match(r"^(\w[\w_]*):\s*(.*)$", line.strip())
        if kv_match:
            key = kv_match.group(1).strip()
            value = kv_match.group(2).strip()

            # Keys that start lists
            if key in ("bullets", "left_bullets", "right_bullets", "steps") and not value:
                current_list_key = key
                current_list = []
            elif key in ("bullets", "left_bullets", "right_bullets", "steps") and value.startswith("- "):
                current_list_key = key
                current_list = [value[2:]]
            else:
                slide[key] = value

    # Save final list
    if current_list_key and current_list:
        slide[current_list_key] = current_list

    return slide


def render_slide_html(slide: dict, index: int) -> str:
    """Render a single slide as HTML."""
    slide_type = slide.get("type", "bullets")
    active = ' active' if index == 0 else ''
    title = escape(slide.get("title", slide.get("slide_title", "")))

    if slide_type == "title":
        subtitle = escape(slide.get("subtitle", ""))
        module_badge = escape(slide.get("badge", slide.get("module_badge", "")))
        badge_html = f'<div class="module-badge">{module_badge}</div>' if module_badge else ''
        return f'''
    <div class="slide slide-title{active}" data-type="title">
        {badge_html}
        <h1>{title}</h1>
        <div class="divider"></div>
        <p class="subtitle">{subtitle}</p>
    </div>'''

    elif slide_type == "bullets":
        bullets = slide.get("bullets", [])
        items_html = ""
        for i, bullet in enumerate(bullets, 1):
            # Support **bold** in bullets
            text = escape(bullet)
            text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
            items_html += f'''
            <li>
                <span class="bullet-icon">{i}</span>
                <span class="bullet-text">{text}</span>
            </li>'''
        return f'''
    <div class="slide slide-bullets{active}" data-type="bullets">
        <h2>{title}</h2>
        <div class="title-underline"></div>
        <ul class="bullets-list">{items_html}
        </ul>
    </div>'''

    elif slide_type == "two-column":
        left_title = escape(slide.get("left_title", ""))
        right_title = escape(slide.get("right_title", ""))
        left_bullets = slide.get("left_bullets", [])
        right_bullets = slide.get("right_bullets", [])

        def render_col_list(items):
            return "\n".join(f"                    <li>{escape(item)}</li>" for item in items)

        return f'''
    <div class="slide slide-two-column{active}" data-type="two-column">
        <h2>{title}</h2>
        <div class="title-underline"></div>
        <div class="columns">
            <div class="column">
                <h3>{right_title}</h3>
                <ul>
{render_col_list(right_bullets)}
                </ul>
            </div>
            <div class="column">
                <h3>{left_title}</h3>
                <ul>
{render_col_list(left_bullets)}
                </ul>
            </div>
        </div>
    </div>'''

    elif slide_type == "quote":
        quote = escape(slide.get("quote", slide.get("slide_title", "")))
        author = escape(slide.get("author", ""))
        author_html = f'<div class="quote-author">- {author}</div>' if author else ''
        return f'''
    <div class="slide slide-quote{active}" data-type="quote">
        <div class="quote-mark">"</div>
        <blockquote>{quote}</blockquote>
        {author_html}
    </div>'''

    elif slide_type == "example":
        content_text = slide.get("content", "")
        # Convert **text** to <span class="highlight">
        content_html = escape(content_text)
        content_html = re.sub(r'\*\*(.+?)\*\*', r'<span class="highlight">\1</span>', content_html)
        content_html = content_html.replace("\n", "<br>\n")
        label = escape(slide.get("label", "EXAMPLE"))
        return f'''
    <div class="slide slide-example{active}" data-type="example">
        <h2>{title}</h2>
        <div class="title-underline"></div>
        <div class="example-box">
            <div class="label">{label}</div>
            <div class="content">{content_html}</div>
        </div>
    </div>'''

    elif slide_type == "exercise":
        steps = slide.get("steps", [])
        steps_html = ""
        for i, step in enumerate(steps, 1):
            steps_html += f'''
            <div class="step">
                <div class="step-number">{i}</div>
                <div class="step-text">{escape(step)}</div>
            </div>'''
        return f'''
    <div class="slide slide-exercise{active}" data-type="exercise">
        <div class="exercise-badge">&#9998; תרגיל מעשי</div>
        <h2>{title}</h2>
        <div class="steps">{steps_html}
        </div>
    </div>'''

    elif slide_type == "image":
        image_src = slide.get("image", slide.get("src", ""))
        caption = escape(slide.get("caption", ""))
        if not image_src:
            image_src = f"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='800' height='500' fill='%231B2D4A'%3E%3Crect width='800' height='500' rx='16'/%3E%3Ctext x='400' y='250' fill='%23EEB332' font-size='24' text-anchor='middle'%3EImage Placeholder%3C/text%3E%3C/svg%3E"
        caption_html = f'<p class="caption">{caption}</p>' if caption else ''
        return f'''
    <div class="slide slide-image{active}" data-type="image">
        <h2>{title}</h2>
        <div class="image-frame">
            <img src="{image_src}" alt="{title}">
        </div>
        {caption_html}
    </div>'''

    elif slide_type == "section":
        section_num = escape(slide.get("section_number", ""))
        subtitle = escape(slide.get("subtitle", ""))
        return f'''
    <div class="slide slide-section{active}" data-type="section">
        <div class="section-number">{section_num}</div>
        <h2>{title}</h2>
        <p class="section-subtitle">{subtitle}</p>
    </div>'''

    else:
        # Fallback to bullets
        slide["type"] = "bullets"
        return render_slide_html(slide, index)


def generate_presentation(lesson: dict, avatar_path: str = "../avatar_presenter_closeup.png") -> str:
    """Generate a complete HTML presentation from parsed lesson data."""

    slides_html = ""
    for i, slide in enumerate(lesson["slides"]):
        slides_html += render_slide_html(slide, i)

    # Read the template CSS/JS from slide_template.html concept
    html = f'''<!DOCTYPE html>
<html lang="he" dir="rtl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=1920, height=1080">
    <title>{escape(lesson["title"])} - Selling Master</title>
    <link href="https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;500;700;900&display=swap" rel="stylesheet">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        :root {{
            --navy-dark: {BRAND["navy_dark"]};
            --navy-mid: {BRAND["navy_mid"]};
            --navy-light: {BRAND["navy_light"]};
            --gold: {BRAND["gold"]};
            --gold-light: {BRAND["gold_light"]};
            --white: {BRAND["white"]};
            --text-secondary: {BRAND["text_secondary"]};
            --text-dim: {BRAND["text_dim"]};
        }}

        body {{
            font-family: '{BRAND["font"]}', Arial, sans-serif;
            background: #000;
            overflow: hidden;
            direction: rtl;
        }}

        .slides-wrapper {{
            position: relative;
            width: 1920px;
            height: 1080px;
            margin: 0 auto;
            overflow: hidden;
        }}

        .slide {{
            position: absolute;
            top: 0; right: 0;
            width: 1920px; height: 1080px;
            padding: 80px 100px;
            display: none;
            flex-direction: column;
            background: linear-gradient(135deg, var(--navy-dark) 0%, var(--navy-mid) 100%);
            color: var(--white);
            overflow: hidden;
        }}
        .slide.active {{ display: flex; }}

        .slide::before {{
            content: '';
            position: absolute;
            top: -200px; left: -200px;
            width: 600px; height: 600px;
            background: radial-gradient(circle, rgba(238,179,50,0.06) 0%, transparent 70%);
            pointer-events: none;
        }}

        .top-bar {{
            position: absolute;
            top: 0; right: 0; left: 0;
            height: 60px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 0 40px;
            background: rgba(0,0,0,0.2);
            border-bottom: 1px solid rgba(238,179,50,0.15);
            z-index: 10;
        }}
        .top-bar .brand {{ font-size: 18px; font-weight: 700; color: var(--gold); letter-spacing: 1px; }}
        .top-bar .lesson-info {{ font-size: 14px; color: var(--text-secondary); }}

        .avatar-container {{
            position: absolute;
            bottom: 30px; left: 30px;
            width: 160px; height: 160px;
            border-radius: 50%;
            overflow: hidden;
            border: 3px solid var(--gold);
            box-shadow: 0 4px 20px rgba(0,0,0,0.4);
            z-index: 20;
        }}
        .avatar-container img {{ width: 100%; height: 100%; object-fit: cover; }}

        .progress-bar {{
            position: absolute;
            bottom: 0; right: 0; left: 0;
            height: 4px;
            background: rgba(255,255,255,0.1);
            z-index: 10;
        }}
        .progress-bar .progress {{
            height: 100%;
            background: linear-gradient(90deg, var(--gold), var(--gold-light));
            transition: width 0.3s ease;
        }}

        .slide-counter {{
            position: absolute;
            bottom: 15px; right: 40px;
            font-size: 14px; color: var(--text-dim);
            z-index: 10;
        }}

        /* Title slide */
        .slide.slide-title {{ justify-content: center; align-items: center; text-align: center; padding-top: 100px; }}
        .slide-title .module-badge {{
            display: inline-block; padding: 8px 24px;
            background: rgba(238,179,50,0.15); border: 1px solid var(--gold);
            border-radius: 30px; font-size: 18px; color: var(--gold);
            margin-bottom: 30px; font-weight: 500;
        }}
        .slide-title h1 {{
            font-size: 72px; font-weight: 900; line-height: 1.2; margin-bottom: 20px;
            background: linear-gradient(135deg, var(--white) 0%, var(--text-secondary) 100%);
            -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text;
        }}
        .slide-title .subtitle {{ font-size: 28px; color: var(--text-secondary); font-weight: 300; max-width: 800px; }}
        .slide-title .divider {{ width: 120px; height: 4px; background: var(--gold); margin: 30px auto; border-radius: 2px; }}

        /* Bullets slide */
        .slide.slide-bullets {{ padding-top: 120px; }}
        .slide-bullets h2 {{ font-size: 48px; font-weight: 700; margin-bottom: 10px; }}
        .slide-bullets .title-underline {{ width: 80px; height: 4px; background: var(--gold); margin-bottom: 50px; border-radius: 2px; }}
        .slide-bullets .bullets-list {{ list-style: none; display: flex; flex-direction: column; gap: 24px; max-width: 1400px; }}
        .slide-bullets .bullets-list li {{ display: flex; align-items: flex-start; gap: 20px; font-size: 30px; line-height: 1.5; }}
        .slide-bullets .bullets-list li .bullet-icon {{
            flex-shrink: 0; width: 36px; height: 36px;
            background: rgba(238,179,50,0.2); border: 2px solid var(--gold);
            border-radius: 50%; display: flex; align-items: center; justify-content: center;
            font-size: 18px; color: var(--gold); margin-top: 4px;
        }}
        .slide-bullets .bullets-list li .bullet-text strong {{ color: var(--gold); }}

        /* Two-column slide */
        .slide.slide-two-column {{ padding-top: 120px; }}
        .slide-two-column h2 {{ font-size: 48px; font-weight: 700; margin-bottom: 10px; }}
        .slide-two-column .title-underline {{ width: 80px; height: 4px; background: var(--gold); margin-bottom: 50px; border-radius: 2px; }}
        .slide-two-column .columns {{ display: flex; gap: 60px; flex: 1; }}
        .slide-two-column .column {{
            flex: 1; background: rgba(255,255,255,0.04);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 16px; padding: 40px;
        }}
        .slide-two-column .column h3 {{
            font-size: 28px; font-weight: 700; color: var(--gold);
            margin-bottom: 24px; padding-bottom: 16px;
            border-bottom: 2px solid rgba(238,179,50,0.3);
        }}
        .slide-two-column .column ul {{ list-style: none; display: flex; flex-direction: column; gap: 16px; }}
        .slide-two-column .column li {{ font-size: 24px; padding-right: 20px; position: relative; }}
        .slide-two-column .column li::before {{
            content: '\\25C6'; position: absolute; right: 0;
            color: var(--gold); font-size: 12px; top: 6px;
        }}

        /* Quote slide */
        .slide.slide-quote {{ justify-content: center; align-items: center; text-align: center; }}
        .slide-quote .quote-mark {{ font-size: 120px; color: var(--gold); opacity: 0.3; line-height: 0.5; margin-bottom: 20px; }}
        .slide-quote blockquote {{ font-size: 44px; font-weight: 300; line-height: 1.6; max-width: 1200px; margin-bottom: 30px; }}
        .slide-quote .quote-author {{ font-size: 22px; color: var(--gold); font-weight: 500; }}

        /* Example slide */
        .slide.slide-example {{ padding-top: 120px; }}
        .slide-example h2 {{ font-size: 44px; font-weight: 700; margin-bottom: 10px; }}
        .slide-example .title-underline {{ width: 80px; height: 4px; background: var(--gold); margin-bottom: 40px; border-radius: 2px; }}
        .slide-example .example-box {{
            background: rgba(0,0,0,0.3); border: 1px solid rgba(238,179,50,0.2);
            border-radius: 16px; padding: 50px; flex: 1;
            display: flex; flex-direction: column; justify-content: center;
        }}
        .slide-example .example-box .label {{ font-size: 16px; font-weight: 700; color: var(--gold); text-transform: uppercase; letter-spacing: 2px; margin-bottom: 20px; }}
        .slide-example .example-box .content {{ font-size: 28px; line-height: 1.8; }}
        .slide-example .example-box .highlight {{ color: var(--gold); font-weight: 700; }}

        /* Exercise slide */
        .slide.slide-exercise {{ padding-top: 120px; }}
        .slide-exercise .exercise-badge {{
            display: inline-flex; align-items: center; gap: 10px;
            padding: 10px 24px; background: rgba(238,179,50,0.15);
            border: 1px solid var(--gold); border-radius: 8px;
            font-size: 18px; color: var(--gold); margin-bottom: 30px; font-weight: 700;
        }}
        .slide-exercise h2 {{ font-size: 44px; font-weight: 700; margin-bottom: 40px; }}
        .slide-exercise .steps {{ display: flex; flex-direction: column; gap: 20px; max-width: 1400px; }}
        .slide-exercise .step {{
            display: flex; align-items: flex-start; gap: 20px;
            background: rgba(255,255,255,0.04); border-radius: 12px;
            padding: 24px 30px; border-right: 4px solid var(--gold);
        }}
        .slide-exercise .step-number {{
            flex-shrink: 0; width: 44px; height: 44px;
            background: var(--gold); color: var(--navy-dark); border-radius: 50%;
            display: flex; align-items: center; justify-content: center;
            font-size: 20px; font-weight: 900;
        }}
        .slide-exercise .step-text {{ font-size: 26px; line-height: 1.5; }}

        /* Image slide */
        .slide.slide-image {{ padding-top: 120px; }}
        .slide-image h2 {{ font-size: 44px; font-weight: 700; margin-bottom: 40px; }}
        .slide-image .image-frame {{ flex: 1; display: flex; align-items: center; justify-content: center; margin-bottom: 40px; }}
        .slide-image .image-frame img {{ max-width: 100%; max-height: 100%; border-radius: 16px; box-shadow: 0 8px 40px rgba(0,0,0,0.4); border: 2px solid rgba(238,179,50,0.2); }}
        .slide-image .caption {{ font-size: 20px; color: var(--text-secondary); text-align: center; }}

        /* Section divider slide */
        .slide.slide-section {{
            justify-content: center; align-items: center; text-align: center;
            background: linear-gradient(135deg, var(--navy-dark) 0%, #0D1F38 50%, var(--navy-mid) 100%);
        }}
        .slide-section .section-number {{ font-size: 120px; font-weight: 900; color: var(--gold); opacity: 0.2; margin-bottom: -30px; }}
        .slide-section h2 {{ font-size: 56px; font-weight: 700; margin-bottom: 16px; }}
        .slide-section .section-subtitle {{ font-size: 24px; color: var(--text-secondary); }}

        /* Print */
        @media print {{
            body {{ background: white; }}
            .slides-wrapper {{ width: 100%; height: auto; }}
            .slide {{ position: relative; display: flex !important; page-break-after: always; width: 100%; height: 100vh; print-color-adjust: exact; -webkit-print-color-adjust: exact; }}
            .slide-counter, .progress-bar {{ display: none; }}
        }}

        .nav-hint {{
            position: fixed; bottom: 20px; left: 50%; transform: translateX(-50%);
            font-size: 13px; color: var(--text-dim); z-index: 100; opacity: 0.5;
        }}
    </style>
</head>
<body>

<div class="slides-wrapper" id="slidesWrapper">
    <div class="top-bar">
        <span class="brand">{BRAND["course_name"]}</span>
        <span class="lesson-info" id="lessonInfo">{escape(lesson["lesson_info"])}</span>
    </div>

    <div class="avatar-container">
        <img src="{avatar_path}" alt="Presenter">
    </div>

    <div class="progress-bar">
        <div class="progress" id="progressBar"></div>
    </div>

    <div class="slide-counter" id="slideCounter"></div>

{slides_html}

</div>

<div class="nav-hint">Arrow keys to navigate | F for fullscreen | P for print</div>

<script>
(function() {{
    const slides = document.querySelectorAll('.slide');
    let cur = 0;
    const total = slides.length;

    function show(i) {{
        if (i < 0 || i >= total) return;
        slides[cur].classList.remove('active');
        cur = i;
        slides[cur].classList.add('active');
        update();
    }}

    function update() {{
        document.getElementById('slideCounter').textContent = (cur+1) + ' / ' + total;
        document.getElementById('progressBar').style.width = ((cur+1)/total*100) + '%';
    }}

    document.addEventListener('keydown', function(e) {{
        switch(e.key) {{
            case 'ArrowLeft': case 'ArrowDown': case ' ': case 'PageDown': e.preventDefault(); show(cur+1); break;
            case 'ArrowRight': case 'ArrowUp': case 'PageUp': e.preventDefault(); show(cur-1); break;
            case 'Home': e.preventDefault(); show(0); break;
            case 'End': e.preventDefault(); show(total-1); break;
            case 'f': case 'F': e.preventDefault();
                if (!document.fullscreenElement) document.documentElement.requestFullscreen();
                else document.exitFullscreen();
                break;
            case 'p': case 'P': e.preventDefault(); window.print(); break;
        }}
    }});

    document.querySelector('.slides-wrapper').addEventListener('click', function(e) {{
        const rect = this.getBoundingClientRect();
        if (e.clientX - rect.left < rect.width / 2) show(cur-1);
        else show(cur+1);
    }});

    let touchX = 0;
    document.addEventListener('touchstart', e => touchX = e.touches[0].clientX);
    document.addEventListener('touchend', e => {{
        const d = touchX - e.changedTouches[0].clientX;
        if (Math.abs(d) > 50) {{ if (d > 0) show(cur+1); else show(cur-1); }}
    }});

    update();
    window.slideAPI = {{ next: () => show(cur+1), prev: () => show(cur-1), goto: show, total, current: () => cur }};
}})();
</script>

</body>
</html>'''

    return html


def main():
    parser = argparse.ArgumentParser(
        description="Generate HTML slide presentation from a lesson script"
    )
    parser.add_argument("script", help="Path to the markdown lesson script")
    parser.add_argument(
        "--output", "-o",
        help="Output HTML file path (default: print to stdout)"
    )
    parser.add_argument(
        "--avatar",
        default="../avatar_presenter_closeup.png",
        help="Path to avatar image (relative to output HTML)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Just show parsed slides without generating HTML"
    )

    args = parser.parse_args()

    if not os.path.exists(args.script):
        print(f"Error: Script file not found: {args.script}", file=sys.stderr)
        sys.exit(1)

    lesson = parse_script(args.script)

    if args.dry_run:
        print(f"Lesson: {lesson['title']}")
        print(f"Info: {lesson['lesson_info']}")
        print(f"Slides: {len(lesson['slides'])}")
        print()
        for i, slide in enumerate(lesson["slides"], 1):
            stype = slide.get("type", "bullets")
            stitle = slide.get("title", slide.get("slide_title", ""))
            narration_len = len(slide.get("narration", ""))
            print(f"  Slide {i}: [{stype}] {stitle}")
            if narration_len:
                print(f"    Narration: {narration_len} chars")
        return

    html = generate_presentation(lesson, avatar_path=args.avatar)

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Generated: {args.output} ({len(lesson['slides'])} slides)")
    else:
        print(html)


if __name__ == "__main__":
    main()
