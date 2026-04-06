---
name: tts-toolkit
description: >
  Turn any text content into narrated audio (MP3) or a static-image video
  (MP4) with a title card. Supports Gemini and Mistral TTS engines.
  Use when someone says "read this aloud", "make an audio version",
  "narrate this", "audio companion", "generate a voiceover", or wants
  to convert written content into listenable audio for students,
  audiences, or accessibility purposes.
---

# TTS Toolkit

Convert any text content into narrated audio or video. Two output modes:

- **Audio (MP3)** — A standalone audio file, ready to share or embed in
  an LMS, podcast feed, or website.
- **Video (MP4)** — A static title card with narrated audio, suitable
  for YouTube, LMS video players, or any platform that expects video.

## Prerequisites

- Python 3.10+
- `pip install google-genai python-dotenv Pillow` (for Gemini engine)
- `pip install mistralai` (optional, for Mistral engine)
- `ffmpeg` and `ffprobe` on PATH
- API key in `.env` or environment:
  - Gemini (default): `GOOGLE_API_KEY`
  - Mistral: `MISTRAL_API_KEY`

## Workflow

### Step 1: Prepare the Content

Read the source content (webpage, document, chapter, article, etc.)
and present a summary to the user:

| Section | Title | Words | Est. Time |
|---------|-------|-------|-----------|
| 1       | Introduction | 250 | 1:40 |
| ...     | ...   | ...   | ...       |
| **Total** | | **3200** | **21:20** |

Estimate narration time at 150 words/minute.

### Step 2: Write Narration

Write the full narration as a plain `.txt` file. Follow the rules in
`references/narration-rules.md`:

- **Include**: All body text — narrate every paragraph in full
- **Exclude**: References, figure captions, raw table data
- **TTS formatting**: Sentences <30 words, spell out abbreviations, no ALL CAPS
- **Flow**: Spoken section markers at major boundaries, brief bridge
  sentences between sections
- **Section markers**: Insert `[SECTION]` on its own line between major
  sections. The script uses these as chunk boundaries for parallel TTS.

**GATE**: The user approves the narration text before generation.

### Step 3: Choose Output Format

Ask the user:

> **Would you like audio only (MP3) or a narrated video with a title card (MP4)?**

- **MP3** — Faster to generate, smaller file, ideal for LMS audio
  embeds, podcast feeds, or download links.
- **MP4** — Includes a title card image, suitable for YouTube or video
  players. Optionally provide a background image and subtitle.

### Step 4: Generate

**Audio only (MP3):**

```bash
python3 scripts/tts_toolkit.py \
  --title "Content Title" \
  --narration narration.txt \
  --output "Content Title - Audio.mp3"
```

**Video with title card (MP4):**

```bash
python3 scripts/tts_toolkit.py \
  --title "Content Title" \
  --subtitle "Course or Source Name" \
  --background background.jpg \
  --narration narration.txt \
  --output "Content Title - Audio Companion.mp4"
```

**Flags:**

| Flag | Description | Default |
|------|-------------|---------|
| `--engine` | `gemini` or `mistral` | `gemini` |
| `--voice` | Voice name | Enceladus (Gemini) / Oliver - Cheerful (Mistral) |
| `--model` | Model override | Engine-specific |
| `--background` | Background image for title card | Solid dark card |
| `--subtitle` | Text below the title (video only) | None |
| `--no-transcript` | Skip transcript generation | Transcript on by default |

**Gemini voices**: Enceladus (breathy), Kore (firm), Puck (upbeat),
Zephyr (bright), and 26+ others. Gemini TTS accepts natural-language
style instructions in the prompt.

### Step 5: Deliver

Report the output file size and duration. The script auto-generates a
clean `transcript.txt` (narration with `[SECTION]` markers stripped).

For YouTube uploads: use `transcript.txt` under **Subtitles > Add
Language > Upload File > "Without timing."** YouTube auto-syncs the
text to the audio.

## Technical Notes

- **Chunked parallel TTS**: The script splits narration at `[SECTION]`
  markers (and further at paragraph boundaries if chunks exceed 4000
  chars), then generates audio in parallel. Gemini uses 2 workers;
  Mistral uses 4.
- **Audio encoding**: Both engines output 24kHz PCM WAV. For MP4, the
  script re-encodes to 44.1kHz stereo AAC (required for QuickTime
  compatibility on macOS). For MP3, it encodes with libmp3lame VBR
  quality 2 (~190kbps).
- **Background images**: Center-cropped to 1920x1080 without stretching.
  Portrait images work fine — they get cropped to landscape.
- **Retries**: Each TTS chunk has 3 retries with exponential backoff
  (10s, 20s). If chunks still fail, reduce `max_chars` in the
  `chunk_narration` function.
- **Cross-platform fonts**: The title card renderer tries macOS, Linux,
  and Windows system fonts before falling back to Pillow's default.
