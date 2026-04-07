# TTS Toolkit

Turn any text content into narrated audio (MP3) or video (MP4) using AI text-to-speech. Give Claude or Codex a chapter, article, or document and it preserves your text, prepares it for audio (stripping footnotes, handling tables, formatting for natural speech), and generates the output.

Works with **Claude Code**, **Claude Cowork**, and **OpenAI Codex**.

## How It Works

You don't write code. You don't read API documentation. You tell Claude (or Codex) what you want in plain English, and it handles the technical parts.

For example, you could say:

> "I have a chapter saved as chapter3.txt. Convert it to an MP3 file."

Claude reads the chapter, prepares a narration-ready version of the text, calls the TTS API, and saves the audio file to your computer. If you want video instead of audio, it generates an MP4 with a title card, ready for YouTube.

Here's what happens step by step:

1. **Claude reads your content** and summarizes it (word count, estimated duration)
2. **Claude prepares it for audio** — your text is preserved in full, but footnotes, superscripts, and raw table data are stripped, and formatting is adjusted for natural-sounding speech. You review and approve before anything is generated.
3. **You choose the format:** MP3 (audio only) or MP4 (video with title card)
4. **Claude generates the file** and reports the size and duration
5. **A transcript is created** alongside the audio, ready for YouTube captions or accessibility

## What Is an API Key?

An API key is a password that gives software permission to access a service on your behalf. You sign up at the provider's website, generate a key, and paste it into your setup. That's it.

You'll need a key from one of these TTS providers:

- **Google Gemini** (recommended) — [Get a key at Google AI Studio](https://aistudio.google.com/apikey). Best voice quality. A typical textbook chapter costs around $0.25.
- **Mistral** (cheapest) — [Get a key at Mistral Console](https://console.mistral.ai/home). Currently free for most usage. Good quality, slightly flatter intonation than Gemini.

Both providers offer free usage tiers, so you can experiment before setting up billing.

## What Does It Cost?

Here's what the same long chapter (6,400 words, 43 minutes of audio) costs across different TTS services:

| Service | Est. Cost | Notes |
|---|---|---|
| Mistral Voxtral | ~$0.58 | Currently free tier covers most usage |
| Gemini 2.5 Flash TTS | ~$0.67 | Good quality, half the cost of Pro |
| Gemini 2.5 Pro TTS | ~$1.34 | Best quality, default in this skill |
| ElevenLabs Flash | ~$2.16 | Dedicated TTS platform |
| ElevenLabs Multilingual v2 | ~$4.32 | Highest quality, highest cost |

Most textbook chapters are shorter than this example. A typical chapter through Gemini Pro runs about $0.25. For a full 15-chapter textbook, expect roughly $0 with Mistral, $10 with Gemini Flash, or $20 with Gemini Pro.

## Installation

### What You'll Need

- **An AI coding tool**: Claude Code, Claude Cowork, or OpenAI Codex. This is what talks to the API for you. If you don't have one yet, [Claude Cowork](https://claude.ai) is the most accessible option (visual interface, no terminal required).
- **An API key** from Google or Mistral (see above).
- **Python 3.10+** and **[ffmpeg](https://ffmpeg.org/download.html)** installed on your computer. If you're not sure whether you have these, ask Claude or Codex: *"Do I have Python and ffmpeg installed?"* It will check for you.

### Option A: Claude Cowork (recommended for most faculty)

Cowork is the visual, non-terminal version of Claude, available at [claude.ai](https://claude.ai) and in the Claude desktop app.

1. **Download the skill**: Click the green **Code** button on this GitHub page, then **Download ZIP**.
2. **Open Cowork**: Go to [claude.ai](https://claude.ai) or open the Claude desktop app and switch to the **Cowork** tab.
3. **Upload the skill**: Click **Customize** in the left sidebar, then **Skills**, then the **+** button, then **+ Create skill**, and upload the ZIP file you downloaded.
4. **Set up your API key**: When you first use the skill, Claude will ask for your API key. Paste it in when prompted.

Once installed, the skill appears in your Skills list and Claude will use it automatically when you ask it to narrate content.

### Option B: Claude Code (CLI / desktop app)

Claude Code is the terminal-based version. If you're comfortable with the command line:

1. **Clone and install dependencies**:

```bash
git clone https://github.com/Brehove/tts-toolkit.git
cd tts-toolkit
pip install -r requirements.txt
```

2. **Set up your API key**:

```bash
cp .env.example .env
```

Open `.env` in any text editor and paste in your API key.

3. **Register the skill**:

```bash
cp -r . ~/.claude/skills/tts-toolkit
```

### Option C: OpenAI Codex

If you use Codex instead of Claude, you can still use this toolkit. Clone the repo, install the dependencies, and point Codex at the `SKILL.md` file. Codex will follow the same workflow.

## Using It

Tell Claude (or Codex) what you want narrated. Examples:

- *"Turn this chapter into an audio file"*
- *"Make an MP3 of this article for my students"*
- *"Create a narrated video of Chapter 3 with a title card"*

For video output, you can optionally provide a background image and subtitle (like a course name). If you don't, Claude generates a clean dark title card.

## Voice Options

The default engine is **Gemini TTS** with the "Enceladus" voice (clear, slightly breathy). You can ask Claude to use a different voice:

- *"Use the Kore voice, it's more firm"*
- *"Switch to Mistral TTS for this one"*

**Gemini voices** include Enceladus, Kore, Puck, Zephyr, and 26+ others. **Mistral TTS** is available as an alternative engine (requires a Mistral API key and `pip install mistralai`).

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
