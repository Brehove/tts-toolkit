"""Command-line interface for TTS Toolkit."""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import importlib.util
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import wave
import zipfile
from collections import Counter
from pathlib import Path
from urllib.parse import unquote

from defusedxml import ElementTree as ET


SUPPORTED_INPUT_EXTS = {".md", ".markdown", ".txt", ".html", ".htm", ".epub", ".pdf"}
MAX_EPUB_MEMBER_BYTES = 25 * 1024 * 1024
MAX_EPUB_TOTAL_BYTES = 150 * 1024 * 1024

DEFAULTS = {
    "kokoro": {
        "voice": "af_heart",
        "model": "hexgrad/Kokoro-82M",
        "workers": 1,
        "max_chars": None,
    },
    "elevenlabs": {
        "voice": "JBFqnCBsd6RMkjVDRZzb",
        "model": "eleven_flash_v2_5",
        "workers": 2,
        "max_chars": 39000,
        "output_format": "mp3_44100_64",
    },
    "openai": {
        "voice": "cedar",
        "model": "gpt-4o-mini-tts",
        "workers": 2,
        "max_chars": 3800,
    },
    "gemini": {
        "voice": "Enceladus",
        "model": "gemini-2.5-pro-preview-tts",
        "workers": 2,
        "max_chars": 4000,
    },
    "gemini-flash": {
        "voice": "Enceladus",
        "model": "gemini-2.5-flash-preview-tts",
        "workers": 3,
        "max_chars": 4000,
    },
    "mistral": {
        "voice": "Oliver - Cheerful",
        "model": "voxtral-mini-tts-2603",
        "workers": 4,
        "max_chars": 4000,
    },
}

QUALITY_PROFILES = {
    "small": {"bitrate": "48k", "channels": "1"},
    "standard": {"bitrate": "64k", "channels": "1"},
    "high": {"bitrate": "128k", "channels": "2"},
}

SKIP_HEADING_RE = re.compile(
    r"^(references|bibliography|works cited|notes|endnotes|footnotes|"
    r"attributions?|image credits?|license|licensing)\b",
    re.IGNORECASE,
)
SKIP_CONTAINER_RE = re.compile(
    r"(references?|bibliography|footnotes?|endnotes?|attributions?|"
    r"image-?credits?|license|licensing|caption)",
    re.IGNORECASE,
)


def load_env() -> None:
    """Load environment variables from .env when python-dotenv is available."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        load_dotenv = None

    if load_dotenv:
        load_dotenv()

    env_file = Path.cwd() / ".env"
    if not env_file.exists():
        env_file = Path(__file__).resolve().parents[1] / ".env"

    if env_file.exists():
        if load_dotenv:
            load_dotenv(env_file)
        else:
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def require_import(module_name: str, install_hint: str):
    try:
        return __import__(module_name)
    except ImportError:
        sys.exit(f"Missing Python package: {module_name}. Install with: {install_hint}")


def require_command(command: str, install_hint: str) -> str:
    command_path = shutil.which(command)
    if command_path is None:
        sys.exit(f"Missing command: {command}. Install with: {install_hint}")
    return command_path


def module_available(module_name: str) -> bool:
    try:
        return importlib.util.find_spec(module_name) is not None
    except ModuleNotFoundError:
        return False


def clean_inline_text(text: str) -> str:
    text = text.replace("\xa0", " ")
    text = re.sub(r"\[(?:\^?\d+|footnote\s*\d+)\]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\[\s*image\s*#?\d+[^\]]*\]", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s+", " ", text)
    text = text.replace("e.g.", "for example")
    text = text.replace("i.e.", "that is")
    text = text.replace("—", " - ")
    text = text.replace("–", "-")
    text = text.replace("“", '"').replace("”", '"')
    text = text.replace("‘", "'").replace("’", "'")
    return text.strip()


def normalize_narration_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"(?:\n\s*){0,1}\[SECTION\](?:\s*\n){0,1}", "\n\n[SECTION]\n\n", text)
    return text.strip()


def tag_in_skip_container(tag) -> bool:
    for parent in tag.parents:
        values = []
        if parent.get("id"):
            values.append(parent.get("id"))
        values.extend(parent.get("class", []))
        if any(SKIP_CONTAINER_RE.search(str(value)) for value in values):
            return True
    return False


def html_to_narration(html_text: str) -> str:
    bs4 = require_import("bs4", "pip install beautifulsoup4")
    soup = bs4.BeautifulSoup(html_text, "html.parser")

    for tag in soup(["script", "style", "noscript", "nav", "header", "footer"]):
        tag.decompose()
    for tag in soup.find_all(["sup", "figure", "figcaption"]):
        tag.decompose()

    for table in soup.find_all("table"):
        placeholder = soup.new_tag("p")
        placeholder.string = (
            "The source includes a table here. Refer to the original text "
            "for the full details."
        )
        table.replace_with(placeholder)

    body = soup.body or soup
    nodes = body.find_all(["h1", "h2", "h3", "h4", "p", "li", "blockquote"], recursive=True)
    parts: list[str] = []
    skip_until_heading_level: int | None = None

    for node in nodes:
        if tag_in_skip_container(node):
            continue

        name = node.name.lower()
        text = clean_inline_text(node.get_text(" ", strip=True))
        if not text:
            continue

        is_heading = name in {"h1", "h2", "h3", "h4"}
        if is_heading:
            level = int(name[1])
            if skip_until_heading_level is not None and level <= skip_until_heading_level:
                skip_until_heading_level = None

            if SKIP_HEADING_RE.search(text):
                skip_until_heading_level = level
                continue

            if skip_until_heading_level is not None:
                continue

            if parts and parts[-1] != "[SECTION]":
                parts.append("[SECTION]")
            parts.append(text)
            continue

        if skip_until_heading_level is not None:
            continue
        parts.append(text)

    return normalize_narration_text("\n\n".join(parts))


def epub_to_narration(epub_path: Path) -> str:
    with zipfile.ZipFile(epub_path) as archive:
        infos = archive.infolist()
        total_uncompressed = sum(info.file_size for info in infos)
        largest_member = max((info.file_size for info in infos), default=0)
        if total_uncompressed > MAX_EPUB_TOTAL_BYTES or largest_member > MAX_EPUB_MEMBER_BYTES:
            sys.exit(
                "EPUB is too large to process safely. Convert the relevant chapter "
                "or section to Markdown, TXT, or HTML first."
            )

        try:
            container_xml = archive.read("META-INF/container.xml")
            container = ET.fromstring(container_xml)
            rootfile = container.find(".//{*}rootfile")
            if rootfile is None:
                raise ValueError("No rootfile in EPUB container.xml")
            opf_path = Path(unquote(rootfile.attrib["full-path"]))
            opf = ET.fromstring(archive.read(str(opf_path)))
            manifest = {
                item.attrib["id"]: item.attrib
                for item in opf.findall(".//{*}manifest/{*}item")
                if "id" in item.attrib and "href" in item.attrib
            }
            spine_items = opf.findall(".//{*}spine/{*}itemref")
            html_paths = []
            for itemref in spine_items:
                manifest_item = manifest.get(itemref.attrib.get("idref", ""))
                if not manifest_item:
                    continue
                media_type = manifest_item.get("media-type", "")
                href = unquote(manifest_item["href"])
                if media_type in {"application/xhtml+xml", "text/html"} or href.lower().endswith((".xhtml", ".html", ".htm")):
                    html_paths.append((opf_path.parent / href).as_posix())
        except Exception:
            html_paths = sorted(
                name
                for name in archive.namelist()
                if name.lower().endswith((".xhtml", ".html", ".htm"))
            )

        sections = []
        for html_path in html_paths:
            try:
                html_text = archive.read(html_path).decode("utf-8", errors="replace")
            except KeyError:
                continue
            narration = html_to_narration(html_text)
            if narration:
                sections.append(narration)

    if not sections:
        sys.exit("No readable HTML/XHTML content found in EPUB.")
    return normalize_narration_text("\n\n[SECTION]\n\n".join(sections))


def markdown_to_narration(markdown_text: str) -> str:
    markdown = require_import("markdown", "pip install markdown")
    html_text = markdown.markdown(markdown_text, extensions=["extra", "sane_lists"])
    return html_to_narration(html_text)


def remove_repeated_pdf_lines(page_lines: list[list[str]]) -> list[list[str]]:
    line_counts = Counter(line for lines in page_lines for line in set(lines) if line)
    page_count = len(page_lines)
    repeated = {
        line
        for line, count in line_counts.items()
        if page_count >= 3 and count >= 3 and count / page_count >= 0.4 and len(line) <= 80
    }

    cleaned_pages = []
    for lines in page_lines:
        cleaned_pages.append(
            [
                line
                for line in lines
                if line not in repeated and not re.fullmatch(r"(?:page\s*)?\d+", line, flags=re.IGNORECASE)
            ]
        )
    return cleaned_pages


def pdf_to_narration(pdf_path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError:
        sys.exit("Missing PDF dependency. Install with: pip install pypdf")

    try:
        reader = PdfReader(str(pdf_path))
    except Exception as exc:
        sys.exit(f"Could not read PDF: {exc}")

    page_lines = []
    for page in reader.pages:
        text = page.extract_text() or ""
        lines = [clean_inline_text(line) for line in text.splitlines()]
        lines = [line for line in lines if line]
        page_lines.append(lines)

    page_lines = remove_repeated_pdf_lines(page_lines)
    sections = []
    for lines in page_lines:
        if not lines:
            continue
        paragraphs = []
        current = []
        for line in lines:
            if SKIP_HEADING_RE.search(line):
                break
            current.append(line)
            if re.search(r"[.!?]$", line):
                paragraphs.append(clean_inline_text(" ".join(current)))
                current = []
        if current:
            paragraphs.append(clean_inline_text(" ".join(current)))
        page_text = "\n\n".join(part for part in paragraphs if part)
        if page_text:
            sections.append(page_text)

    if not sections:
        sys.exit(
            "No extractable text found in PDF. If this is a scanned PDF, OCR it first "
            "and then rerun TTS Toolkit."
        )
    return normalize_narration_text("\n\n[SECTION]\n\n".join(sections))


def plain_text_to_narration(text: str) -> str:
    paragraphs = []
    for part in re.split(r"\n\s*\n", text):
        paragraph = clean_inline_text(part)
        if not paragraph:
            continue
        if SKIP_HEADING_RE.search(paragraph):
            break
        paragraphs.append(paragraph)
    return normalize_narration_text("\n\n".join(paragraphs))


def prepare_source(input_path: Path) -> str:
    ext = input_path.suffix.lower()
    if ext not in SUPPORTED_INPUT_EXTS:
        supported = ", ".join(sorted(SUPPORTED_INPUT_EXTS))
        sys.exit(f"Unsupported input type '{ext}'. Use one of: {supported}")

    if ext == ".epub":
        return epub_to_narration(input_path)
    if ext == ".pdf":
        return pdf_to_narration(input_path)

    text = input_path.read_text(encoding="utf-8")
    if ext in {".md", ".markdown"}:
        return markdown_to_narration(text)
    if ext in {".html", ".htm"}:
        return html_to_narration(text)
    return plain_text_to_narration(text)


def estimate_duration_text(text: str) -> tuple[int, int]:
    words = len(text.split())
    seconds = int(words / 150 * 60) if words else 0
    return words, seconds


def default_narration_path(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}_narration.txt")


def prepare_command(args) -> Path:
    input_path = Path(args.input).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve() if args.output else default_narration_path(input_path)
    narration = prepare_source(input_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(narration + "\n", encoding="utf-8")

    words, seconds = estimate_duration_text(narration)
    print(f"Prepared narration: {output_path}")
    print(f"Source: {input_path.name} | {words} words | est. {seconds // 60}m {seconds % 60}s")
    print("Review the narration file before rendering audio.")
    return output_path


def chunk_narration(text: str, max_chars: int) -> list[str]:
    chunks: list[str] = []
    sections = text.split("[SECTION]")

    for section in sections:
        section = section.strip()
        if not section:
            continue
        if len(section) <= max_chars:
            chunks.append(section)
            continue

        current = ""
        for paragraph in re.split(r"\n\s*\n", section):
            paragraph = paragraph.strip()
            if not paragraph:
                continue
            if len(current) + len(paragraph) + 2 > max_chars and current:
                chunks.append(current.strip())
                current = paragraph
            else:
                current = f"{current}\n\n{paragraph}".strip() if current else paragraph

        if current:
            chunks.append(current.strip())

    return chunks


def write_wav(filename: Path, pcm_data: bytes, channels: int = 1, rate: int = 24000, sample_width: int = 2) -> None:
    with wave.open(str(filename), "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(rate)
        wf.writeframes(pcm_data)


def concat_media_to_wav(chunk_paths: list[Path], audio_wav: Path, tmp: Path) -> None:
    if not chunk_paths:
        sys.exit("No audio chunks were generated.")
    ffmpeg = require_command("ffmpeg", "brew install ffmpeg")

    concat_list = tmp / "concat.txt"
    concat_list.write_text(
        "\n".join(f"file '{path.as_posix()}'" for path in chunk_paths),
        encoding="utf-8",
    )
    result = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_list),
            "-ac",
            "1",
            "-ar",
            "24000",
            "-c:a",
            "pcm_s16le",
            str(audio_wav),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"ffmpeg error:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)
    print(f"  Audio assembled from {len(chunk_paths)} chunk(s)")


def generate_audio_kokoro(narration_text: str, audio_wav: Path, voice_name: str, model: str | None) -> None:
    require_import("numpy", "pip install numpy")
    require_import("soundfile", "pip install soundfile")
    try:
        import numpy as np
        import soundfile as sf
        from kokoro import KPipeline
    except ImportError:
        sys.exit("Missing Kokoro dependencies. Install with: pip install 'kokoro>=0.9.4' soundfile numpy")

    text = narration_text.replace("[SECTION]", "").strip()
    if not text:
        sys.exit("Narration file is empty after stripping section markers.")

    lang_code = "b" if voice_name.startswith("b") else "a"
    repo_id = model or DEFAULTS["kokoro"]["model"]

    print("Generating audio via Kokoro TTS (local)...")
    print(f"  Voice: {voice_name}")
    print("  Loading Kokoro pipeline...")
    t0 = time.time()
    pipeline = KPipeline(lang_code=lang_code, repo_id=repo_id)
    print(f"  Loaded in {time.time() - t0:.1f}s")

    chunks = []
    print("  Generating audio...")
    t0 = time.time()
    for index, (_graphemes, _phonemes, audio) in enumerate(pipeline(text, voice=voice_name), start=1):
        chunks.append(audio)
        if index % 25 == 0:
            print(f"  {index} segments processed...")

    if not chunks:
        sys.exit("Kokoro did not return any audio.")

    audio = np.concatenate(chunks)
    duration = len(audio) / 24000
    elapsed = time.time() - t0
    rtf = elapsed / duration if duration else 0
    print(f"  {len(chunks)} segments, {duration:.1f}s audio in {elapsed:.1f}s (RTF {rtf:.2f}x)")

    audio_wav.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(audio_wav), audio, 24000)


def generate_audio_gemini(
    narration_text: str,
    audio_wav: Path,
    voice_name: str,
    model: str,
    tmp: Path,
    workers: int,
    max_chars: int,
) -> None:
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        sys.exit("GOOGLE_API_KEY not found. Set it in your environment or .env file.")

    print(f"Generating audio via Gemini TTS ({model})...")
    try:
        from google import genai
        from google.genai import types
    except ImportError:
        sys.exit("Missing Gemini dependency. Install with: pip install google-genai")

    client = genai.Client(api_key=api_key)
    chunks = chunk_narration(narration_text, max_chars=max_chars)
    print(f"  Voice: {voice_name}")
    print(f"  Split into {len(chunks)} chunk(s)")

    def gen_chunk(item):
        index, chunk = item
        chunk_wav = tmp / f"chunk_{index:03d}.wav"
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
                write_wav(chunk_wav, pcm_data)
                print(f"  Chunk {index + 1}/{len(chunks)} done ({len(chunk)} chars)")
                return chunk_wav
            except Exception as exc:
                if attempt == 3:
                    raise
                wait = attempt * 10
                print(f"    Chunk {index + 1} retry {attempt}/3 ({exc}), waiting {wait}s...")
                time.sleep(wait)

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        chunk_wavs = list(pool.map(gen_chunk, enumerate(chunks)))

    concat_media_to_wav(chunk_wavs, audio_wav, tmp)


def generate_audio_mistral(
    narration_text: str,
    audio_wav: Path,
    voice_name: str,
    model: str,
    tmp: Path,
    workers: int,
    max_chars: int,
) -> None:
    api_key = os.environ.get("MISTRAL_API_KEY")
    if not api_key:
        sys.exit("MISTRAL_API_KEY not found. Set it in your environment or .env file.")

    print("Generating audio via Mistral TTS...")
    try:
        from mistralai.client import Mistral
    except ImportError:
        try:
            from mistralai import Mistral
        except ImportError:
            sys.exit("Missing Mistral dependency. Install with: pip install mistralai")

    chunks = chunk_narration(narration_text, max_chars=max_chars)
    print(f"  Voice: {voice_name}")
    print(f"  Split into {len(chunks)} chunk(s)")

    voice_id = voice_name
    try:
        with Mistral(api_key=api_key) as client:
            offset = 0
            while True:
                voices = client.audio.voices.list(limit=100, offset=offset)
                for item in getattr(voices, "items", []):
                    if getattr(item, "name", "").casefold() == voice_name.casefold():
                        voice_id = item.id
                        print(f"  Resolved voice: {voice_name} ({voice_id})")
                        raise StopIteration
                total = getattr(voices, "total", 0)
                offset += 100
                if not total or offset >= total:
                    break
    except StopIteration:
        pass
    except Exception:
        print("  Could not look up Mistral voice by name; using the provided value as the voice ID.")

    def gen_chunk(item):
        index, chunk = item
        chunk_wav = tmp / f"chunk_{index:03d}.wav"
        for attempt in range(1, 4):
            try:
                with Mistral(api_key=api_key, timeout_ms=300000) as client:
                    try:
                        response = client.audio.speech.complete(
                            input=chunk,
                            model=model,
                            voice_id=voice_id,
                            response_format="wav",
                        )
                    except TypeError:
                        response = client.audio.speech.complete(
                            input=chunk,
                            model=model,
                            voice=voice_id,
                            response_format="wav",
                        )
                audio_data = getattr(response, "audio_data", None)
                if isinstance(audio_data, str):
                    chunk_wav.write_bytes(base64.b64decode(audio_data))
                elif isinstance(audio_data, bytes):
                    chunk_wav.write_bytes(audio_data)
                else:
                    sys.exit("Mistral response did not include audio data.")
                print(f"  Chunk {index + 1}/{len(chunks)} done ({len(chunk)} chars)")
                return chunk_wav
            except Exception as exc:
                if attempt == 3:
                    raise
                wait = attempt * 10
                print(f"    Chunk {index + 1} retry {attempt}/3 ({exc}), waiting {wait}s...")
                time.sleep(wait)

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        chunk_wavs = list(pool.map(gen_chunk, enumerate(chunks)))

    concat_media_to_wav(chunk_wavs, audio_wav, tmp)


def generate_audio_elevenlabs(
    narration_text: str,
    audio_wav: Path,
    voice_id: str,
    model: str,
    tmp: Path,
    workers: int,
    max_chars: int,
    output_format: str,
) -> None:
    api_key = os.environ.get("ELEVENLABS_API_KEY")
    if not api_key:
        sys.exit("ELEVENLABS_API_KEY not found. Set it in your environment or .env file.")

    requests = require_import("requests", "pip install requests")
    chunks = chunk_narration(narration_text, max_chars=max_chars)
    print(f"Generating audio via ElevenLabs ({model})...")
    print(f"  Voice ID: {voice_id}")
    print(f"  Split into {len(chunks)} chunk(s)")

    def gen_chunk(item):
        index, chunk = item
        chunk_mp3 = tmp / f"chunk_{index:03d}.mp3"
        url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
        params = {"output_format": output_format}
        payload = {"text": chunk, "model_id": model}
        headers = {
            "xi-api-key": api_key,
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
        }
        for attempt in range(1, 4):
            response = requests.post(url, params=params, json=payload, headers=headers, timeout=300)
            if response.ok:
                chunk_mp3.write_bytes(response.content)
                print(f"  Chunk {index + 1}/{len(chunks)} done ({len(chunk)} chars)")
                return chunk_mp3
            if attempt == 3:
                sys.exit(f"ElevenLabs request failed: {response.status_code} {response.text[:500]}")
            wait = attempt * 10
            print(f"    Chunk {index + 1} retry {attempt}/3 ({response.status_code}), waiting {wait}s...")
            time.sleep(wait)

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        chunk_mp3s = list(pool.map(gen_chunk, enumerate(chunks)))

    concat_media_to_wav(chunk_mp3s, audio_wav, tmp)


def generate_audio_openai(
    narration_text: str,
    audio_wav: Path,
    voice_name: str,
    model: str,
    tmp: Path,
    workers: int,
    max_chars: int,
) -> None:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        sys.exit("OPENAI_API_KEY not found. Set it in your environment or .env file.")

    try:
        from openai import OpenAI
    except ImportError:
        sys.exit("Missing OpenAI dependency. Install with: pip install openai")

    chunks = chunk_narration(narration_text, max_chars=max_chars)
    print(f"Generating audio via OpenAI ({model})...")
    print(f"  Voice: {voice_name}")
    print(f"  Split into {len(chunks)} chunk(s)")

    def gen_chunk(item):
        index, chunk = item
        chunk_mp3 = tmp / f"chunk_{index:03d}.mp3"
        for attempt in range(1, 4):
            try:
                client = OpenAI(api_key=api_key)
                with client.audio.speech.with_streaming_response.create(
                    model=model,
                    voice=voice_name,
                    input=chunk,
                    instructions="Read in a clear, measured tone for educational listening.",
                    response_format="mp3",
                ) as response:
                    response.stream_to_file(chunk_mp3)
                print(f"  Chunk {index + 1}/{len(chunks)} done ({len(chunk)} chars)")
                return chunk_mp3
            except Exception as exc:
                if attempt == 3:
                    raise
                wait = attempt * 10
                print(f"    Chunk {index + 1} retry {attempt}/3 ({exc}), waiting {wait}s...")
                time.sleep(wait)

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        chunk_mp3s = list(pool.map(gen_chunk, enumerate(chunks)))

    concat_media_to_wav(chunk_mp3s, audio_wav, tmp)


def load_font(size: int):
    from PIL import ImageFont

    candidates = [
        "/System/Library/Fonts/HelveticaNeue.ttc",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size)
            except Exception:
                continue
    return ImageFont.load_default()


def wrap_text(text: str, font, max_width: int, draw) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
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


def make_title_card(title: str, subtitle: str, background_path: str, output_path: Path, w: int = 1920, h: int = 1080) -> None:
    try:
        from PIL import Image, ImageDraw
    except ImportError:
        sys.exit("Missing Pillow dependency. Install with: pip install Pillow")

    bg_color = (25, 31, 43)
    text_color = (255, 255, 255)
    subtitle_color = (210, 218, 225)

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
        overlay = Image.new("RGBA", (w, h), (0, 0, 0, 170))
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    else:
        img = Image.new("RGB", (w, h), bg_color)

    draw = ImageDraw.Draw(img)
    title_font = load_font(72)
    subtitle_font = load_font(36)
    max_width = int(w * 0.78)

    title_lines = wrap_text(title, title_font, max_width, draw)
    line_h_title = 90
    line_h_subtitle = 50
    total_h = len(title_lines) * line_h_title
    subtitle_lines: list[str] = []
    if subtitle:
        subtitle_lines = wrap_text(subtitle, subtitle_font, max_width, draw)
        total_h += 40 + len(subtitle_lines) * line_h_subtitle

    y = (h - total_h) // 2
    for line in title_lines:
        bbox = draw.textbbox((0, 0), line, font=title_font)
        x = (w - (bbox[2] - bbox[0])) // 2
        draw.text((x, y), line, fill=text_color, font=title_font)
        y += line_h_title

    if subtitle_lines:
        y += 40
        for line in subtitle_lines:
            bbox = draw.textbbox((0, 0), line, font=subtitle_font)
            x = (w - (bbox[2] - bbox[0])) // 2
            draw.text((x, y), line, fill=subtitle_color, font=subtitle_font)
            y += line_h_subtitle

    output_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(output_path), "PNG")


def export_mp3(audio_wav: Path, output_path: Path, quality: str) -> None:
    ffmpeg = require_command("ffmpeg", "brew install ffmpeg")
    profile = QUALITY_PROFILES[quality]
    print(f"Encoding MP3 ({quality}, {profile['bitrate']}, {profile['channels']} channel(s))...")
    result = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(audio_wav),
            "-ar",
            "44100",
            "-ac",
            profile["channels"],
            "-b:a",
            profile["bitrate"],
            str(output_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"ffmpeg error:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)


def export_video(audio_wav: Path, title_card: Path, output_path: Path) -> None:
    ffmpeg = require_command("ffmpeg", "brew install ffmpeg")
    print("Assembling MP4 title-card video...")
    result = subprocess.run(
        [
            ffmpeg,
            "-y",
            "-loop",
            "1",
            "-i",
            str(title_card),
            "-i",
            str(audio_wav),
            "-c:v",
            "libx264",
            "-tune",
            "stillimage",
            "-pix_fmt",
            "yuv420p",
            "-r",
            "30",
            "-crf",
            "23",
            "-c:a",
            "aac",
            "-ar",
            "44100",
            "-ac",
            "2",
            "-b:a",
            "128k",
            "-shortest",
            "-movflags",
            "+faststart",
            str(output_path),
        ],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(f"ffmpeg error:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)


def probe_duration(audio_path: Path) -> float:
    ffprobe = require_command("ffprobe", "brew install ffmpeg")
    result = subprocess.run(
        [
            ffprobe,
            "-v",
            "quiet",
            "-show_entries",
            "format=duration",
            "-of",
            "csv=p=0",
            str(audio_path),
        ],
        capture_output=True,
        text=True,
    )
    try:
        return float(result.stdout.strip())
    except ValueError:
        return 0.0


def generate_transcript(narration_path: Path, transcript_path: Path) -> None:
    text = narration_path.read_text(encoding="utf-8")
    text = text.replace("[SECTION]", "")
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    transcript_path.write_text(text + "\n", encoding="utf-8")
    print(f"  Transcript: {transcript_path}")


def render_narration(args) -> Path:
    load_env()
    require_command("ffmpeg", "brew install ffmpeg")
    require_command("ffprobe", "brew install ffmpeg")

    narration_arg = getattr(args, "narration", None) or getattr(args, "narration_path", None)
    if not narration_arg:
        sys.exit("Provide a narration file with --narration or as the render argument.")

    narration_path = Path(narration_arg).expanduser().resolve()
    output_path = Path(args.output).expanduser().resolve()
    output_ext = output_path.suffix.lower()
    if output_ext not in {".mp3", ".mp4"}:
        sys.exit(f"Unsupported output format '{output_ext}'. Use .mp3 or .mp4.")

    engine = args.engine
    defaults = DEFAULTS[engine]
    voice = args.voice or defaults["voice"]
    model = args.model or defaults["model"]
    workers = args.workers or defaults["workers"]
    max_chars = args.max_chars or defaults["max_chars"]
    title = args.title or output_path.stem

    narration_text = narration_path.read_text(encoding="utf-8").strip()
    words, seconds = estimate_duration_text(narration_text)
    print(f"Narration: {len(narration_text)} chars, {words} words, est. {seconds // 60}m {seconds % 60}s")
    print(f"Engine: {engine} | Output: {'MP4 video' if output_ext == '.mp4' else 'MP3 audio'}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        audio_wav = tmp / "audio.wav"

        if engine == "kokoro":
            generate_audio_kokoro(narration_text, audio_wav, voice, model)
        elif engine in {"gemini", "gemini-flash"}:
            generate_audio_gemini(narration_text, audio_wav, voice, model, tmp, workers, max_chars)
        elif engine == "mistral":
            generate_audio_mistral(narration_text, audio_wav, voice, model, tmp, workers, max_chars)
        elif engine == "elevenlabs":
            output_format = args.elevenlabs_output_format or defaults["output_format"]
            generate_audio_elevenlabs(narration_text, audio_wav, voice, model, tmp, workers, max_chars, output_format)
        elif engine == "openai":
            generate_audio_openai(narration_text, audio_wav, voice, model, tmp, workers, max_chars)
        else:
            sys.exit(f"Unsupported engine: {engine}")

        duration = probe_duration(audio_wav)
        print(f"  Audio: {int(duration // 60)}m {int(duration % 60)}s")

        if output_ext == ".mp4":
            title_card = tmp / "title-card.png"
            print("Generating title card...")
            make_title_card(title, args.subtitle or "", args.background or "", title_card)
            export_video(audio_wav, title_card, output_path)
        else:
            export_mp3(audio_wav, output_path, args.quality)

    size_mb = output_path.stat().st_size / (1024 * 1024)
    print(f"\nDone: {output_path} ({size_mb:.1f} MB, {int(duration // 60)}m {int(duration % 60)}s)")

    if args.transcript:
        generate_transcript(narration_path, output_path.with_suffix(".txt"))

    return output_path


def convert_command(args) -> Path:
    input_path = Path(args.input).expanduser().resolve()
    narration_path = (
        Path(args.narration_output).expanduser().resolve()
        if args.narration_output
        else default_narration_path(input_path)
    )
    args.input = str(input_path)
    args.output_prepare = str(narration_path)

    narration = prepare_source(input_path)
    narration_path.parent.mkdir(parents=True, exist_ok=True)
    narration_path.write_text(narration + "\n", encoding="utf-8")
    print(f"Prepared narration: {narration_path}")

    args.narration = str(narration_path)
    if not args.title:
        args.title = input_path.stem.replace("-", " ").replace("_", " ").title()
    return render_narration(args)


def doctor_command(_args) -> None:
    checks = [
        ("ffmpeg", shutil.which("ffmpeg") is not None, "brew install ffmpeg"),
        ("ffprobe", shutil.which("ffprobe") is not None, "brew install ffmpeg"),
        ("espeak-ng", shutil.which("espeak-ng") is not None, "brew install espeak-ng"),
    ]

    packages = [
        ("beautifulsoup4", "bs4", "pip install beautifulsoup4"),
        ("defusedxml", "defusedxml", "pip install defusedxml"),
        ("markdown", "markdown", "pip install markdown"),
        ("kokoro", "kokoro", "pip install 'kokoro>=0.9.4'"),
        ("soundfile", "soundfile", "pip install soundfile"),
        ("numpy", "numpy", "pip install numpy"),
        ("pypdf", "pypdf", "pip install pypdf"),
        ("requests", "requests", "pip install requests"),
    ]

    print("System checks")
    for name, ok, hint in checks:
        mark = "OK" if ok else "MISSING"
        print(f"  {mark:7} {name}" + ("" if ok else f" ({hint})"))

    print("\nPython package checks")
    for label, module_name, hint in packages:
        ok = module_available(module_name)
        mark = "OK" if ok else "MISSING"
        print(f"  {mark:7} {label}" + ("" if ok else f" ({hint})"))

    print("\nOptional cloud package checks")
    optional = [
        ("google-genai", "google.genai", "pip install google-genai"),
        ("mistralai", "mistralai", "pip install mistralai"),
        ("openai", "openai", "pip install openai"),
    ]
    for label, module_name, hint in optional:
        ok = module_available(module_name)
        mark = "OK" if ok else "OPTIONAL"
        print(f"  {mark:8} {label}" + ("" if ok else f" ({hint})"))


def setup_command(args) -> None:
    load_env()
    require_command("espeak-ng", "brew install espeak-ng")
    require_command("ffmpeg", "brew install ffmpeg")

    voice = args.voice or DEFAULTS["kokoro"]["voice"]
    with tempfile.TemporaryDirectory() as tmp_dir:
        audio_wav = Path(tmp_dir) / "setup.wav"
        generate_audio_kokoro(
            "This is a short TTS Toolkit setup test.",
            audio_wav,
            voice,
            DEFAULTS["kokoro"]["model"],
        )
    print("Kokoro setup check complete.")


def add_render_args(parser: argparse.ArgumentParser, include_narration: bool = True) -> None:
    if include_narration:
        parser.add_argument("narration_path", nargs="?", help="Prepared narration .txt file")
        parser.add_argument("--narration", help="Prepared narration .txt file")
    parser.add_argument("--output", required=True, help="Output file path (.mp3 or .mp4)")
    parser.add_argument("--title", help="Title for MP4 title card or metadata")
    parser.add_argument("--subtitle", default="", help="Subtitle below the title (MP4 only)")
    parser.add_argument("--background", default="", help="Background image for MP4 title card")
    parser.add_argument(
        "--engine",
        choices=sorted(DEFAULTS.keys()),
        default="kokoro",
        help="TTS engine (default: kokoro)",
    )
    parser.add_argument("--voice", help="Voice name or provider voice ID")
    parser.add_argument("--model", help="Provider model override")
    parser.add_argument("--workers", type=int, help="Parallel cloud workers")
    parser.add_argument("--max-chars", type=int, help="Maximum characters per cloud request chunk")
    parser.add_argument(
        "--quality",
        choices=sorted(QUALITY_PROFILES.keys()),
        default="standard",
        help="MP3 export quality (default: standard, 64kbps mono)",
    )
    parser.add_argument(
        "--elevenlabs-output-format",
        help="ElevenLabs output format (default: mp3_44100_64)",
    )
    parser.add_argument("--transcript", action="store_true", default=True, help="Write clean transcript next to output")
    parser.add_argument("--no-transcript", action="store_false", dest="transcript", help="Skip transcript output")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tts-toolkit",
        description="Turn Markdown, TXT, HTML, EPUB, or PDF into LMS/OER-ready audio.",
    )
    subparsers = parser.add_subparsers(dest="command")

    prepare = subparsers.add_parser("prepare", help="Create a narration transcript from Markdown, TXT, HTML, EPUB, or PDF")
    prepare.add_argument("input", help="Input .md, .txt, .html, .epub, or .pdf file")
    prepare.add_argument("--output", help="Narration transcript output path")
    prepare.set_defaults(func=prepare_command)

    render = subparsers.add_parser("render", help="Render a prepared narration transcript to MP3 or MP4")
    add_render_args(render, include_narration=True)
    render.set_defaults(func=render_narration)

    convert = subparsers.add_parser("convert", help="Prepare and render in one command")
    convert.add_argument("input", help="Input .md, .txt, .html, .epub, or .pdf file")
    convert.add_argument("--narration-output", help="Where to save the generated narration transcript")
    add_render_args(convert, include_narration=False)
    convert.set_defaults(func=convert_command)

    doctor = subparsers.add_parser("doctor", help="Check local system and Python dependencies")
    doctor.set_defaults(func=doctor_command)

    setup = subparsers.add_parser("setup", help="Trigger the first Kokoro model download with a tiny test")
    setup.add_argument("--voice", default=DEFAULTS["kokoro"]["voice"], help="Kokoro voice to test")
    setup.set_defaults(func=setup_command)

    return parser


def main(argv: list[str] | None = None) -> None:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] not in {"-h", "--help"} and argv[0].startswith("--"):
        argv = ["render", *argv]

    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return
    args.func(args)
