#!/usr/bin/env python3
"""
Convert lesson scripts from .md to HeyGen-ready .txt files with tone/emotion annotations.
"""
import re
import os
import glob

SCRIPTS_DIR = r"C:\Users\DELL\קורס למכירה באינטרנט\content\scripts"

def extract_narration_text(md_content):
    """Extract only narration text from markdown, removing all formatting and metadata."""
    lines = md_content.split('\n')
    result_lines = []
    skip_metadata = True  # skip initial metadata block

    for line in lines:
        stripped = line.strip()

        # Skip empty lines (preserve them for paragraph breaks)
        if not stripped:
            if not skip_metadata and result_lines:
                result_lines.append('')
            continue

        # Skip title lines (# and ##)
        if stripped.startswith('# ') or stripped.startswith('## '):
            continue

        # Skip metadata lines
        if stripped.startswith('**משך:**') or stripped.startswith('**נקודות מפתח:**'):
            skip_metadata = True
            continue
        if skip_metadata and stripped.startswith('- '):
            continue

        # Skip horizontal rules
        if stripped == '---':
            skip_metadata = False
            continue

        # Skip SLIDE markers (### lines with SLIDE:)
        if stripped.startswith('### ') or stripped.startswith('#### '):
            skip_metadata = False
            continue

        # Skip task/materials lines at the end
        if stripped.startswith('**משימה:**') or stripped.startswith('**חומרים:**'):
            break
        if stripped.startswith('- [') and 'http' in stripped:
            continue

        skip_metadata = False

        # Remove markdown bold
        cleaned = re.sub(r'\*\*([^*]+)\*\*', r'\1', stripped)
        # Remove markdown italic
        cleaned = re.sub(r'\*([^*]+)\*', r'\1', cleaned)
        # Remove markdown links [text](url)
        cleaned = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', cleaned)
        # Remove any remaining markdown
        cleaned = cleaned.strip()

        if cleaned:
            result_lines.append(cleaned)

    # Clean up multiple blank lines
    text = '\n'.join(result_lines)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def detect_section_type(text):
    """Detect what kind of content a paragraph is."""
    # Numbers/statistics
    if re.search(r'\d+[%,.]?\d*\s*(אחוז|מיליארד|מיליון|אלף|שקל|דולר)', text):
        return 'statistic'
    if re.search(r'\d{2,}', text) and len(text) < 80:
        return 'number_emphasis'

    # Questions
    if '?' in text:
        return 'question'

    # Lists with numbers
    if re.match(r'^(אחד|שתיים|שלוש|ארבע|חמש|שש|שבע|שמונה|תשע|עשר|1\.|2\.|3\.|4\.|5\.|6\.|7\.|8\.|9\.|10\.)', text):
        return 'list_item'

    # Commands/calls to action
    if any(word in text for word in ['עכשיו תקשיבו', 'בואו', 'עצרו', 'תעצרו', 'תכתבו', 'תזכרו', 'חשבו']):
        return 'call_to_action'

    # Emotional/personal
    if any(word in text for word in ['אני', 'אני LEO', 'שלי', 'ראיתי', 'למדתי', 'גיליתי']):
        return 'personal'

    # Warnings
    if any(word in text for word in ['אזהרה', 'טעות', 'אסור', 'סכנה', 'זהירות', 'אל ת']):
        return 'warning'

    # Summary/conclusion
    if any(word in text for word in ['נסכם', 'לסיכום', 'סיכום', 'בואו נסכם']):
        return 'summary'

    # Opening greeting
    if any(word in text for word in ['שלום לכולם', 'ברוכים הבאים', 'היי']):
        return 'greeting'

    # Closing
    if any(word in text for word in ['נתראה', 'בשיעור הבא', 'יאללה']):
        return 'closing'

    # Tips
    if text.startswith('טיפ'):
        return 'tip'

    # Examples
    if any(word in text for word in ['דוגמה', 'דוגמא', 'למשל', 'דוגמה אמיתית', 'דוגמה ישראלית']):
        return 'example'

    # Short punchy statement
    if len(text) < 50:
        return 'punch'

    return 'narration'


def add_annotations(text):
    """Add HeyGen tone/emotion annotations to narration text."""
    paragraphs = text.split('\n\n')
    annotated = []
    prev_type = None
    para_count = 0

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue

        para_count += 1
        lines = para.split('\n')
        section_type = detect_section_type(para)

        # Determine annotation based on section type and context
        annotation = None
        pre_pause = False

        if para_count == 1:
            # First paragraph - dramatic opening
            if section_type == 'greeting':
                annotation = '[טון חם, חיוך, מבט ישיר למצלמה]'
            elif section_type in ('statistic', 'number_emphasis', 'punch'):
                annotation = '[טון נמוך, דרמטי, הפסקה קצרה לפני]'
            else:
                annotation = '[טון חם, אישי, מבט ישיר למצלמה]'
        elif section_type == 'statistic':
            pre_pause = True
            annotation = '[הדגשה, האטה, טון רציני]'
        elif section_type == 'number_emphasis':
            annotation = '[הפסקה דרמטית, 2 שניות]\n\n[הדגשה חדה, מבט ישיר]'
        elif section_type == 'question':
            if prev_type in ('statistic', 'warning'):
                annotation = '[טון חם, פנייה ישירה]'
            else:
                annotation = '[הרמת גבה, טון סקרני]'
        elif section_type == 'list_item':
            if prev_type != 'list_item':
                annotation = '[קצב מהיר, אנרגיה עולה]'
            # No annotation for subsequent list items (keep flow)
        elif section_type == 'call_to_action':
            pre_pause = True
            annotation = '[מבט ישיר למצלמה, טון תקיף]'
        elif section_type == 'personal':
            annotation = '[טון חם, אישי]'
        elif section_type == 'warning':
            pre_pause = True
            annotation = '[טון רציני, האטה]'
        elif section_type == 'summary':
            pre_pause = True
            annotation = '[הפסקה דרמטית, 2 שניות]\n\n[טון מסכם, ביטחון]'
        elif section_type == 'greeting':
            annotation = '[חיוך, אנרגיה גבוהה]'
        elif section_type == 'closing':
            annotation = '[אנרגיה גבוהה, חיוך רחב, סיום]'
        elif section_type == 'tip':
            annotation = '[הנהון, טון מעשי, ישיר]'
        elif section_type == 'example':
            annotation = '[טון מספר סיפור, חיוך קל]'
        elif section_type == 'punch':
            if prev_type in ('narration', 'statistic'):
                annotation = '[הדגשה, האטה]'
            else:
                annotation = '[טון עוצמתי]'
        else:
            # Regular narration - vary annotations
            if prev_type in ('statistic', 'warning', 'call_to_action'):
                annotation = '[טון חם, קצב רגיל]'
            elif prev_type == 'closing':
                annotation = None
            elif para_count % 5 == 0:
                annotation = '[מבט ישיר למצלמה]'
            elif para_count % 7 == 0:
                annotation = '[טון אבהי, כנה]'
            elif para_count % 3 == 0:
                annotation = '[טון מעשי, ישיר]'

        # Build output
        parts = []
        if pre_pause and annotated:
            parts.append('[הפסקה, 2 שניות]')
            parts.append('')
        if annotation:
            parts.append(annotation)
        parts.append(para)

        annotated.append('\n'.join(parts))
        prev_type = section_type

    return '\n\n'.join(annotated)


def process_file(md_path):
    """Process a single .md file and create corresponding _heygen_ready.txt."""
    with open(md_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Extract narration
    narration = extract_narration_text(content)

    # Add annotations
    annotated = add_annotations(narration)

    # Build output filename
    basename = os.path.splitext(os.path.basename(md_path))[0]
    # Remove the lesson name part after module_lesson pattern
    # e.g., m1_02_digital_revolution -> m1_02
    match = re.match(r'(m\d+_\d+)', basename)
    if match:
        prefix = match.group(1)
    else:
        prefix = basename

    output_path = os.path.join(os.path.dirname(md_path), f'{prefix}_heygen_ready.txt')

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(annotated)

    return output_path


def main():
    md_files = sorted(glob.glob(os.path.join(SCRIPTS_DIR, 'm*_*.md')))

    # Exclude m1_01 which is already done
    md_files = [f for f in md_files if not os.path.basename(f).startswith('m1_01_')]

    print(f"Found {len(md_files)} MD files to process")

    created = []
    for md_file in md_files:
        try:
            output = process_file(md_file)
            created.append(output)
            print(f"  Created: {os.path.basename(output)}")
        except Exception as e:
            print(f"  ERROR processing {os.path.basename(md_file)}: {e}")

    print(f"\nDone! Created {len(created)} HeyGen-ready files.")


if __name__ == '__main__':
    main()
