---
name: tts-toolkit
description: >
  Turn Markdown, TXT, HTML, EPUB, or PDF into narration-ready text and LMS/OER-ready
  audio. Use when someone asks to make an MP3, audio companion, narrated
  reading, static-title-card MP4, or text-to-speech version of course
  materials, OER pages, articles, chapters, module pages, or other
  educational text. Defaults to local Kokoro TTS and supports optional
  ElevenLabs, OpenAI, Gemini, and Mistral engines.
---

# TTS Toolkit

Use this skill to convert educational text into accessible audio while
preserving a reviewable transcript-first workflow.

## Inputs

Accepted source formats:

- Markdown: `.md`, `.markdown`
- Plain text: `.txt`
- HTML: `.html`, `.htm`
- EPUB: `.epub`
- PDF: `.pdf`

If the user provides a webpage, exported chapter, LMS page, OER text, or
article, save or identify the local source before running the CLI.

Prefer Markdown, TXT, or HTML when available. EPUB is usually reliable because
it is packaged HTML. Treat PDF as best-effort for born-digital PDFs; scanned
PDFs need OCR first and complex layouts require careful transcript review.

## Workflow

1. Inspect the source and estimate words and listening time at 150 words per minute.
2. Prepare narration with:

```bash
tts-toolkit prepare path/to/source.md
```

3. Review the generated narration transcript. Follow
   `references/narration-rules.md` when editing: preserve body text, strip
   references and footnote markers, replace tables with brief spoken
   placeholders, and use `[SECTION]` between major sections.
4. Ask the user to approve the narration before rendering long audio.
5. Render MP3 by default:

```bash
tts-toolkit render path/to/source_narration.txt --output path/to/source.mp3
```

Use MP4 only when the user asks for a video/title-card version.

## Defaults

- Engine: `kokoro`
- Voice: `af_heart`
- Output: MP3, 64kbps mono, suitable for LMS/OER uploads
- Transcript: clean `.txt` written beside the output

## Optional Engines

Use only when requested or clearly useful:

- ElevenLabs: `--engine elevenlabs --voice <voice_id>`
- OpenAI: `--engine openai --voice cedar`
- Gemini Flash: `--engine gemini-flash --voice Enceladus`
- Gemini Pro: `--engine gemini --voice Enceladus`
- Mistral: `--engine mistral --voice "Oliver - Cheerful"`

Cloud engines require their provider API keys in `.env` or the environment.

## Commands

Check setup:

```bash
tts-toolkit doctor
tts-toolkit setup
```

Prepare only:

```bash
tts-toolkit prepare reading.html --output reading_narration.txt
```

Render reviewed narration:

```bash
tts-toolkit render reading_narration.txt --output reading.mp3
```

Prepare and render in one step:

```bash
tts-toolkit convert reading.md --output reading.mp3
```
