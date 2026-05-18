"""Compatibility wrapper for the packaged TTS Toolkit CLI."""

from pathlib import Path
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from tts_toolkit.cli import main  # noqa: E402


if __name__ == "__main__":
    main()
