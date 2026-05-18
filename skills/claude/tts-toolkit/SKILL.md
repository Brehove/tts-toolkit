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

Convert educational text into accessible audio with a transcript-first
workflow.

## Accepted Inputs

Use Markdown, TXT, HTML, EPUB, or PDF. Prefer Markdown, TXT, or HTML when
available. EPUB is usually reliable because it is packaged HTML. Treat PDF as
best-effort for born-digital PDFs; scanned PDFs need OCR first and complex
layouts require careful transcript review.

## Workflow

1. Inspect the source and estimate words/listening time at 150 words per minute.
2. Run:

```bash
tts-toolkit prepare path/to/source.md
```

3. Review and, if needed, revise the generated narration transcript using
   `references/narration-rules.md`.
4. Ask the user to approve the narration before rendering long audio.
5. Render MP3 by default:

```bash
tts-toolkit render path/to/source_narration.txt --output path/to/source.mp3
```

Use MP4 only when the user asks for a static-title-card video.

## Defaults

- Engine: `kokoro`
- Voice: `af_heart`
- Output: 64kbps mono MP3
- Transcript: clean `.txt` beside the output

Optional engines:

- ElevenLabs: `--engine elevenlabs --voice <voice_id>`
- OpenAI: `--engine openai --voice cedar`
- Gemini Flash: `--engine gemini-flash --voice Enceladus`
- Gemini Pro: `--engine gemini --voice Enceladus`
- Mistral: `--engine mistral --voice "Oliver - Cheerful"`
