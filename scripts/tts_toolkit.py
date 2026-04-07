"""Generate narrated audio (MP3) or audiobook-style video (MP4) from text.

Usage:
    # Audio only (MP3)
    python3 tts_toolkit.py --title "Chapter 1" --narration narration.txt --output chapter1.mp3

    # Video with title card (MP4)
    python3 tts_toolkit.py --title "Chapter 1" --narration narration.txt --output chapter1.mp4

    # Video with background image and subtitle
    python3 tts_toolkit.py --title "Chapter 1" --subtitle "Intro to Ethics" \
        --background cover.jpg --narration narration.txt --output chapter1.mp4

Takes a plain text narration file, generates TTS audio via Gemini or Mistral,
and outputs either an MP3 file or a static-image video (MP4) with ffmpeg.
Also generates a clean transcript suitable for YouTube captions.

Output format is determined by the --output file extension:
    .mp3  → Audio only
    .mp4  → Video with title card

Requires: Pillow, ffmpeg, ffprobe.
  --engine gemini (default): GOOGLE_API_KEY in .env or environment, google-genai package
  --engine mistral: MISTRAL_API_KEY in .env or environment, mistralai package
"""

import argparse
import base64
import concurrent.futures
import os
import re
import subprocess
import sys
import tempfile
import time
import wave
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Try loading from a .env file next to this script
SCRIPT_DIR = Path(__file__).resolve().parent
_env_file = SCRIPT_DIR.parent / ".env"
if not _env_file.exists():
    _env_file = SCRIPT_DIR / ".env"

if _env_file.exists():
    try:
        from dotenv import load_dotenv as _ld
        _ld(_env_file)
    except ImportError:
        # Manual fallback: parse KEY=VALUE lines
        for line in _env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))

# --- Config ---

DEFAULTS = {
    "mistral": {"voice": "Oliver - Cheerful", "model": "voxtral-mini-tts-2603", "workers": 4},
    "gemini": {"voice": "Enceladus", "model": "gemini-2.5-pro-preview-tts", "workers": 2},
    "gemini-flash": {"voice": "Enceladus", "model": "gemini-2.5-flash-preview-tts", "workers": 3},
}

BG_COLOR = (11, 17, 32)  # Dark blue-black
TEXT_COLOR = (255, 255, 255)
SUBTITLE_COLOR = (180, 190, 210)
OVERLAY_OPACITY = 170


# --- Title card ---

def load_font(size):
    """Load a system font, falling back to Pillow's default."""
    from PIL import ImageFont

    # macOS fonts
    mac_fonts = [
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/System/Library/Fonts/SFNSDisplay.ttf",
    ]
    # Linux fonts
    linux_fonts = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "/usr/share/fonts/TTF/DejaVuSans.ttf",
    ]
    # Windows fonts
    win_fonts = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
    ]

    for path in mac_fonts + linux_fonts + win_fonts:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                continue
    return ImageFont.load_default()


def wrap_text(text, font, max_width, draw):
    """Word-wrap text to fit within max_width pixels."""
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = f"{current} {word}".strip() if current else word
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] > max_width and current:
            lines.append(current)
            current = word
        else:
            current = test
    if current:
        lines.append(current)
    return lines


def make_title_card(title, subtitle, background_path, output_path, w=1920, h=1080):
    """Generate a 1920x1080 title card image."""
    from PIL import Image, ImageDraw

    if background_path and Path(background_path).exists():
        bg = Image.open(background_path).convert("RGB")
        bg_ratio = bg.width / bg.height
        canvas_ratio = w / h
        if bg_ratio > canvas_ratio:
            new_h = h
            new_w = int(h * bg_ratio)
        else:
            new_w = w
            new_h = int(w / bg_ratio)
        bg = bg.resize((new_w, new_h), Image.LANCZOS)
        left = (new_w - w) // 2
        top = (new_h - h) // 2
        img = bg.crop((left, top, left + w, top + h))
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, OVERLAY_OPACITY))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    else:
        img = Image.new("RGB", (w, h), BG_COLOR)

    draw = ImageDraw.Draw(img)
    title_font = load_font(72)
    subtitle_font = load_font(36)
    max_w = int(w * 0.8)

    title_lines = wrap_text(title, title_font, max_w, draw)
    line_h_title, line_h_sub = 90, 50
    total_h = len(title_lines) * line_h_title
    if subtitle:
        total_h += 40 + line_h_sub
    y = (h - total_h) // 2

    for line in title_lines:
        bbox = draw.textbbox((0, 0), line, font=title_font)
        draw.text(((w - bbox[2] + bbox[0]) // 2, y), line, fill=TEXT_COLOR, font=title_font)
        y += line_h_title

    if subtitle:
        y += 40
        for line in wrap_text(subtitle, subtitle_font, max_w, draw):
            bbox = draw.textbbox((0, 0), line, font=subtitle_font)
            draw.text(((w - bbox[2] + bbox[0]) // 2, y), line, fill=SUBTITLE_COLOR, font=subtitle_font)
            y += line_h_sub

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path), "PNG")


# --- Chunking ---

def chunk_narration(text, max_chars=4000):
    """Split narration into chunks at [SECTION] markers, then at paragraph boundaries."""
    parts = text.split("[SECTION]")
    chunks = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if len(part) <= max_chars:
            chunks.append(part)
        else:
            paragraphs = part.split("\n\n")
            current = ""
            for para in paragraphs:
                if len(current) + len(para) + 2 > max_chars and current:
                    chunks.append(current.strip())
                    current = para
                else:
                    current = current + "\n\n" + para if current else para
            if current.strip():
                chunks.append(current.strip())
    return chunks


# --- Mistral TTS ---

def generate_audio_mistral(narration_text, audio_wav, voice_name, model, tmp):
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        sys.exit("MISTRAL_API_KEY not found. Set it in your environment or .env file.")

    print("Generating audio via Mistral TTS...")
    from mistralai.client import Mistral

    with Mistral(api_key=api_key) as client:
        voice_id = None
        offset = 0
        while True:
            resp = client.audio.voices.list(limit=100, offset=offset)
            for item in resp.items:
                if item.name.casefold() == voice_name.casefold():
                    voice_id = item.id
                    break
            if voice_id:
                break
            offset += 100
            if offset >= resp.total:
                break
        if not voice_id:
            sys.exit(f"Voice '{voice_name}' not found.")
        print(f"  Voice: {voice_name} ({voice_id})")

        chunks = chunk_narration(narration_text)
        print(f"  Split into {len(chunks)} chunks, generating in parallel...")

        def gen_chunk(ci_chunk):
            ci, chunk = ci_chunk
            chunk_wav = tmp / f"chunk_{ci:03d}.wav"
            for attempt in range(1, 4):
                try:
                    from mistralai.client import Mistral as MC
                    with MC(api_key=api_key, timeout_ms=300000) as cc:
                        response = cc.audio.speech.complete(
                            input=chunk, model=model,
                            voice_id=voice_id, response_format="wav",
                        )
                    chunk_wav.write_bytes(base64.b64decode(response.audio_data))
                    print(f"  Chunk {ci+1}/{len(chunks)} done ({len(chunk)} chars)")
                    return chunk_wav
                except Exception as e:
                    if attempt < 3:
                        wait = attempt * 10
                        print(f"    Chunk {ci+1} retry {attempt}/3 ({e}), waiting {wait}s...")
                        time.sleep(wait)
                    else:
                        raise

        with concurrent.futures.ThreadPoolExecutor(max_workers=DEFAULTS["mistral"]["workers"]) as pool:
            chunk_wavs = list(pool.map(gen_chunk, enumerate(chunks)))

    _concat_wavs(chunk_wavs, audio_wav, tmp)


# --- Gemini TTS ---

def _write_wav(filename, pcm_data, channels=1, rate=24000, sample_width=2):
    with wave.open(str(filename), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm_data)


def generate_audio_gemini(narration_text, audio_wav, voice_name, model, tmp):
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        sys.exit("GOOGLE_API_KEY not found. Set it in your environment or .env file.")

    print(f"Generating audio via Gemini TTS ({model})...")
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    print(f"  Voice: {voice_name}")

    chunks = chunk_narration(narration_text)
    print(f"  Split into {len(chunks)} chunks, generating in parallel...")

    def gen_chunk(ci_chunk):
        ci, chunk = ci_chunk
        chunk_wav = tmp / f"chunk_{ci:03d}.wav"
        prompt = f"Read the following text in a clear, measured, educational tone:\n\n{chunk}"
        for attempt in range(1, 4):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=["AUDIO"],
                        speech_config=types.SpeechConfig(
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                    voice_name=voice_name,
                                )
                            )
                        ),
                    ),
                )
                pcm_data = response.candidates[0].content.parts[0].inline_data.data
                _write_wav(chunk_wav, pcm_data)
                print(f"  Chunk {ci+1}/{len(chunks)} done ({len(chunk)} chars)")
                return chunk_wav
            except Exception as e:
                if attempt < 3:
                    wait = attempt * 10
                    print(f"    Chunk {ci+1} retry {attempt}/3 ({e}), waiting {wait}s...")
                    time.sleep(wait)
                else:
                    raise

    with concurrent.futures.ThreadPoolExecutor(max_workers=DEFAULTS["gemini"]["workers"]) as pool:
        chunk_wavs = list(pool.map(gen_chunk, enumerate(chunks)))

    _concat_wavs(chunk_wavs, audio_wav, tmp)


# --- Shared audio helpers ---

def _concat_wavs(chunk_wavs, audio_wav, tmp):
    """Concatenate multiple WAV files into one."""
    if len(chunk_wavs) == 1:
        import shutil
        shutil.copy2(chunk_wavs[0], audio_wav)
    else:
        concat_list = tmp / "concat.txt"
        concat_list.write_text("\n".join(f"file '{w}'" for w in chunk_wavs))
        subprocess.run(
            ["ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
             "-c", "copy", str(audio_wav)],
            capture_output=True, check=True,
        )
    print(f"  Audio assembled from {len(chunk_wavs)} chunks")


def export_mp3(audio_wav, output_path):
    """Convert WAV to MP3 using ffmpeg."""
    print("Encoding MP3...")
    result = subprocess.run([
        "ffmpeg", "-y",
        "-i", str(audio_wav),
        "-codec:a", "libmp3lame", "-q:a", "2",
        str(output_path),
    ], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ffmpeg error:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)


def export_video(audio_wav, title_card, output_path):
    """Assemble a static-image video (MP4) from a title card and audio."""
    print("Assembling video...")
    result = subprocess.run([
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(title_card),
        "-i", str(audio_wav),
        "-c:v", "libx264", "-tune", "stillimage",
        "-pix_fmt", "yuv420p", "-r", "30", "-crf", "23",
        "-c:a", "aac", "-ar", "44100", "-ac", "2", "-b:a", "128k",
        "-shortest", "-movflags", "+faststart",
        str(output_path),
    ], capture_output=True, text=True)
    if result.returncode != 0:
        print(f"ffmpeg error:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)


# --- Transcript generation ---

def generate_transcript(narration_path, transcript_path):
    """Write a clean transcript (no [SECTION] markers) for captions or accessibility."""
    text = Path(narration_path).read_text()
    text = text.replace("[SECTION]", "")
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    Path(transcript_path).write_text(text)
    print(f"  Transcript: {transcript_path}")


# --- Main ---

def main():
    parser = argparse.ArgumentParser(
        description="Generate narrated audio (MP3) or video (MP4) from text using TTS",
        epilog="Output format is determined by file extension: .mp3 for audio only, .mp4 for video.",
    )
    parser.add_argument("--engine", choices=["mistral", "gemini", "gemini-flash"], default="gemini",
                        help="TTS engine: gemini (Pro, default), gemini-flash (cheaper), or mistral")
    parser.add_argument("--title", required=True, help="Title displayed on the title card / used in metadata")
    parser.add_argument("--subtitle", default="", help="Subtitle shown below the title (video only)")
    parser.add_argument("--background", default="", help="Background image for the title card (video only)")
    parser.add_argument("--narration", required=True, help="Plain text narration file")
    parser.add_argument("--output", required=True, help="Output file path (.mp3 or .mp4)")
    parser.add_argument("--voice", default=None, help="Voice name (engine-specific default if omitted)")
    parser.add_argument("--model", default=None, help="Model name (engine-specific default if omitted)")
    parser.add_argument("--transcript", action="store_true", default=True,
                        help="Generate a clean transcript file (default: true)")
    parser.add_argument("--no-transcript", action="store_false", dest="transcript",
                        help="Skip transcript generation")
    args = parser.parse_args()

    engine = args.engine
    voice = args.voice or DEFAULTS[engine]["voice"]
    model = args.model or DEFAULTS[engine]["model"]

    output_path = Path(args.output)
    output_ext = output_path.suffix.lower()
    if output_ext not in (".mp3", ".mp4"):
        sys.exit(f"Unsupported output format '{output_ext}'. Use .mp3 or .mp4")

    is_video = output_ext == ".mp4"

    narration_text = Path(args.narration).read_text().strip()
    word_count = len(narration_text.split())
    est_minutes = word_count // 150
    print(f"Narration: {len(narration_text)} chars, ~{word_count} words (~{est_minutes} min)")
    print(f"Engine: {engine} | Output: {'video' if is_video else 'audio'}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        audio_wav = tmp / "audio.wav"

        # 1. Generate TTS audio
        if engine == "mistral":
            generate_audio_mistral(narration_text, audio_wav, voice, model, tmp)
        else:
            generate_audio_gemini(narration_text, audio_wav, voice, model, tmp)

        # Get duration
        dur = float(subprocess.run(
            ["ffprobe", "-v", "quiet", "-show_entries", "format=duration",
             "-of", "csv=p=0", str(audio_wav)],
            capture_output=True, text=True,
        ).stdout.strip())
        print(f"  Audio: {int(dur // 60)}m {int(dur % 60)}s")

        # 2. Export in requested format
        if is_video:
            title_card = tmp / "title-card.png"
            print("Generating title card...")
            make_title_card(args.title, args.subtitle, args.background, title_card)
            export_video(audio_wav, title_card, output_path)
        else:
            export_mp3(audio_wav, output_path)

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"\nDone: {output_path} ({size_mb:.1f} MB, {int(dur // 60)}m {int(dur % 60)}s)")

    # 3. Generate clean transcript
    if args.transcript:
        transcript_path = output_path.with_suffix(".txt")
        generate_transcript(args.narration, transcript_path)


if __name__ == "__main__":
    main()
