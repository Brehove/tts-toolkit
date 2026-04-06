# TTS Toolkit

A Claude Code skill that turns any text content into narrated audio (MP3) or video (MP4) using AI text-to-speech. Give Claude a chapter, article, or document and it handles everything — writing the narration, generating the audio, and packaging the output.

## What It Does

1. **Reads your content** — textbook chapter, article, handout, blog post, etc.
2. **Writes the narration** — Claude prepares a TTS-optimized script automatically
3. **You choose the format:**
   - **MP3** — Audio file you can embed in your LMS, share as a download, or add to a podcast feed
   - **MP4** — A title card video with narrated audio, ready for YouTube or any video player
4. **Generates a transcript** — clean text file for captions or accessibility

## Setup

### Requirements

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed
- Python 3.10+
- [ffmpeg](https://ffmpeg.org/download.html) installed
- A Google API key ([get one here](https://aistudio.google.com/apikey)) for Gemini TTS

### Install the Skill

Clone this repo and install dependencies:

```bash
git clone https://github.com/Brehove/tts-toolkit.git
cd tts-toolkit
pip install -r requirements.txt
```

Set up your API key:

```bash
cp .env.example .env
```

Open `.env` in any text editor and paste in your Google API key.

### Register with Claude Code

Copy the skill into your Claude Code skills directory:

```bash
cp -r . ~/.claude/skills/tts-toolkit
```

Once installed, Claude will automatically know how to use the skill when you ask it to narrate content.

## How to Use It

Open Claude Code and tell it what you want narrated. Examples:

- *"Turn this chapter into an audio file"* (paste a URL or file path)
- *"Make an MP3 of this article for my students"*
- *"Create a narrated video of Chapter 3 with a title card"*

Claude will:

1. Read and summarize your content (word count, estimated duration)
2. Write the narration and show it to you for approval
3. Ask whether you want **MP3** (audio only) or **MP4** (video with title card)
4. Generate the file and report the size and duration

For video output, you can optionally provide a background image and subtitle (like a course name). If you don't, Claude generates a clean dark title card.

## Voice Options

The default engine is **Gemini TTS** with the "Enceladus" voice (clear, slightly breathy). You can ask Claude to use a different voice:

- *"Use the Kore voice — it's more firm"*
- *"Switch to Mistral TTS for this one"*

**Gemini voices** include Enceladus, Kore, Puck, Zephyr, and 26+ others. **Mistral TTS** is available as an alternative engine (requires a separate Mistral API key and `pip install mistralai`).

## Uploading to YouTube

For MP4 output, the skill generates a `transcript.txt` alongside the video. To add captions in YouTube:

1. Go to **Subtitles > Add Language > Upload File**
2. Choose **"Without timing"**
3. Upload `transcript.txt` — YouTube auto-syncs it to the audio

## Technical Details

- **Parallel generation** — long narrations are split into chunks and generated concurrently for speed
- **Title cards** — auto-generated at 1920x1080; background images are center-cropped without stretching
- **Audio quality** — MP3 at ~190kbps VBR; MP4 uses 44.1kHz stereo AAC
- **Cross-platform** — works on macOS, Linux, and Windows

## License

MIT
