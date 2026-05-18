# TTS Toolkit

Local-first text-to-audio for teaching, OER, LMS, and accessible course materials.

TTS Toolkit turns **Markdown**, **TXT**, **HTML**, **EPUB**, or **PDF** into a cleaned narration transcript and then renders it as an **MP3** or optional static-title-card **MP4**. It is designed for course readings, web chapters, OER textbook material, articles, module pages, and other educational text that should be easy to upload to an LMS, OER platform, website, podcast feed, or video host.

Kokoro is the default engine: local, free, fast, and consistent for long educational readings. Kokoro is an [open-weight](https://huggingface.co/hexgrad/Kokoro-82M), Apache-2.0-licensed TTS model with code available on [GitHub](https://github.com/hexgrad/kokoro). Cloud engines are available when you want a hosted voice or provider-specific model.

## What It Does

The default workflow is transcript-first:

1. Prepare a narration transcript from Markdown, TXT, HTML, EPUB, or PDF.
2. Review or edit the narration text.
3. Render MP3 audio, or MP4 video with a title card.
4. Save a clean transcript beside the output for captions or accessibility.

This keeps the source text inspectable before any text-to-speech credits are spent or any long audio job is run.

## Install

### macOS

```bash
brew install ffmpeg espeak-ng
pipx install git+https://github.com/Brehove/tts-toolkit.git
tts-toolkit setup
```

Or with `uv`:

```bash
brew install ffmpeg espeak-ng
uv tool install git+https://github.com/Brehove/tts-toolkit.git
tts-toolkit setup
```

`tts-toolkit setup` runs one tiny Kokoro test. The first run may download the Kokoro model files into your normal local model cache.

### Local Development

```bash
git clone https://github.com/Brehove/tts-toolkit.git
cd tts-toolkit
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
tts-toolkit doctor
```

## Basic Use

Prepare a narration transcript:

```bash
tts-toolkit prepare reading.md
```

Render the reviewed transcript to an LMS/OER-friendly MP3:

```bash
tts-toolkit render reading_narration.txt --output reading.mp3
```

Do both in one command:

```bash
tts-toolkit convert reading.html --output reading.mp3
```

Create a static-title-card video:

```bash
tts-toolkit render reading_narration.txt \
  --title "Week 3 Reading" \
  --subtitle "Introduction to Ethics" \
  --output reading.mp4
```

## Inputs

Supported source formats:

- Markdown: `.md`, `.markdown`
- Plain text: `.txt`
- HTML: `.html`, `.htm`
- EPUB: `.epub`
- PDF: `.pdf`

The prepare step strips or softens elements that usually sound bad in TTS: footnote markers, raw tables, figures, captions, references, bibliography sections, navigation, and page chrome. Tables become a short spoken placeholder rather than row-by-row narration.

Markdown, TXT, and HTML are the cleanest inputs. EPUB is usually reliable because it is packaged HTML. PDF support is best-effort for born-digital PDFs; scanned PDFs should be OCRed first, and dense layouts may need transcript review.

## Outputs

Default MP3 output is intentionally size-conscious:

- `standard`: 64kbps mono MP3, good default for LMS and OER upload limits
- `small`: 48kbps mono MP3
- `high`: 128kbps stereo MP3

Example:

```bash
tts-toolkit render reading_narration.txt --output reading.mp3 --quality high
```

MP4 output uses a 1920x1080 title card plus narrated audio.

## Engines

Kokoro is the default and requires no API key:

```bash
tts-toolkit render reading_narration.txt --output reading.mp3
```

Cloud engines are included in the install, but they only run when selected
and when the matching API key is available:

```bash
tts-toolkit render reading_narration.txt --output reading.mp3 \
  --engine elevenlabs --voice JBFqnCBsd6RMkjVDRZzb

tts-toolkit render reading_narration.txt --output reading.mp3 \
  --engine openai --voice cedar

tts-toolkit render reading_narration.txt --output reading.mp3 \
  --engine gemini-flash --voice Enceladus

tts-toolkit render reading_narration.txt --output reading.mp3 \
  --engine mistral --voice "Oliver - Cheerful"
```

Copy `.env.example` to `.env` and add only the keys you need:

- `ELEVENLABS_API_KEY`
- `OPENAI_API_KEY`
- `GOOGLE_API_KEY`
- `MISTRAL_API_KEY`

## Agent Skills

This repo includes installable skill folders for Claude and Codex.

Claude:

```bash
cp -R skills/claude/tts-toolkit ~/.claude/skills/tts-toolkit
```

Codex:

```bash
cp -R skills/codex/tts-toolkit ~/.codex/skills/tts-toolkit
```

Once installed, ask your agent for things like:

- "Turn this Markdown reading into an MP3 for my LMS."
- "Prepare this HTML chapter as narration, then let me review it."
- "Use Kokoro to make an audio companion for this module page."
- "Use ElevenLabs for this one, but keep the transcript-first workflow."

## Why This Exists

Generic audiobook tools often center EPUB conversion. TTS Toolkit is narrower and more practical for teaching: take the text instructors actually have, clean it into listenable narration, and produce upload-ready audio without making an entire publishing pipeline mandatory.

## License

MIT
