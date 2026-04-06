# TTS Toolkit

Turn any text into narrated audio (MP3) or video (MP4) using AI text-to-speech.

Built as a [Claude Code skill](https://docs.anthropic.com/en/docs/claude-code) — Claude reads your content, writes the narration, and generates the output. You can also run the script standalone.

## What It Does

1. **Reads your content** — article, textbook chapter, documentation, blog post, etc.
2. **Writes narration** — optimized for natural-sounding TTS (sentence length, abbreviations, flow)
3. **Generates output** — your choice:
   - **MP3** — Audio file for LMS embeds, podcast feeds, or downloads
   - **MP4** — Static title card + narrated audio for YouTube or video players
4. **Creates a transcript** — clean text file for captions or accessibility

## Quick Start

### Prerequisites

- Python 3.10+
- [ffmpeg](https://ffmpeg.org/download.html) installed and on PATH
- A Google API key (for Gemini TTS) or Mistral API key

### Setup

```bash
git clone https://github.com/YOUR_USERNAME/tts-toolkit.git
cd tts-toolkit
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API key(s)
```

### Usage

**Audio only (MP3):**

```bash
python3 scripts/tts_toolkit.py \
  --title "My Content Title" \
  --narration narration.txt \
  --output "My Content - Audio.mp3"
```

**Video with title card (MP4):**

```bash
python3 scripts/tts_toolkit.py \
  --title "My Content Title" \
  --subtitle "Course Name" \
  --background cover.jpg \
  --narration narration.txt \
  --output "My Content - Audio Companion.mp4"
```

### All Options

| Flag | Description | Default |
|------|-------------|---------|
| `--engine` | `gemini` or `mistral` | `gemini` |
| `--title` | Title (required) | — |
| `--subtitle` | Subtitle below title (video only) | None |
| `--background` | Background image for title card (video only) | Solid dark card |
| `--narration` | Path to narration text file (required) | — |
| `--output` | Output path — `.mp3` or `.mp4` (required) | — |
| `--voice` | Voice name | Enceladus (Gemini) / Oliver - Cheerful (Mistral) |
| `--model` | Model override | Engine-specific |
| `--no-transcript` | Skip transcript generation | Transcript on |

## Using as a Claude Code Skill

Copy the `SKILL.md` and `scripts/` directory into your Claude Code skills folder. Claude will:

1. Read your source content and summarize it
2. Write TTS-optimized narration following the rules in `references/narration-rules.md`
3. Ask whether you want MP3 or MP4
4. Generate the output and report file size/duration

See `SKILL.md` for the full skill workflow.

## Writing Good Narration

The `references/narration-rules.md` file contains guidelines for preparing text for TTS. Key points:

- Keep sentences under 30 words
- Spell out abbreviations on first use
- Replace ALL CAPS with regular case
- Add `[SECTION]` markers between major sections (enables parallel TTS generation)
- Include brief bridge sentences between sections for natural flow

## How It Works

- **Parallel TTS**: Splits narration at `[SECTION]` markers, generates audio chunks in parallel
- **Title cards**: Auto-generated 1920x1080 images with center-cropped backgrounds
- **Audio**: 24kHz WAV from TTS, re-encoded to MP3 (VBR ~190kbps) or AAC stereo for MP4
- **Cross-platform**: System font detection for macOS, Linux, and Windows

## TTS Engines

### Gemini (default)

Uses Google's Gemini 2.5 Pro TTS. Voices include Enceladus (breathy), Kore (firm), Puck (upbeat), Zephyr (bright), and 26+ others. Requires a `GOOGLE_API_KEY`.

### Mistral

Uses Mistral's Voxtral TTS. Requires a `MISTRAL_API_KEY`. Install with `pip install mistralai`.

## License

MIT
