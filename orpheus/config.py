"""Runtime settings shared by ingestion, agents and the HTTP API."""

import os
from pathlib import Path
from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_DIR = Path(__file__).resolve().parent
VALUES = {**dotenv_values(ROOT / ".env"), **os.environ}
DATA_DIR = Path(VALUES.get("ORPHEUS_DATA_DIR", ROOT / "data")).expanduser().resolve()
PROJECTS = DATA_DIR / "projects"
OBSERVABILITY_DIR = DATA_DIR / "observability"
OBSERVABILITY_ASSETS = ROOT / "observability"
UPLOAD_LIMIT_BYTES = 100 * 1024 * 1024
MEDIA_SECONDS = 30
SAMPLE_RATE = 48000
CONTROLLER_MODELS = [
    "deepseek/deepseek-v4-flash-vision-exp",
    "qwen/qwen3.8-flash",
    "meta/muse-spark-1.3-contributor",
]
CONTROLLER_MAX_TOKENS = 30000
AUDIO_MODEL = "google/gemini-2.5-flash-lite"
AUDIO_MAX_TOKENS = 30000
PROVIDER_TIMEOUT_SECONDS = 180
TURN_TIMEOUT_SECONDS = 1800
MAX_CONTROLLER_CALLS = 40
MAX_CYCLES = 5
AUDIO_CALL_LIMIT = 6


def prepare_storage():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PROJECTS.mkdir(parents=True, exist_ok=True)
    OBSERVABILITY_DIR.mkdir(parents=True, exist_ok=True)


MAX_FILE_BYTES = UPLOAD_LIMIT_BYTES
MAX_DURATION_S = MEDIA_SECONDS
MAX_BRIEF_CHARS = 240
MAX_FEEDBACK_CHARS = 500

AUDIO_ENABLED = str(VALUES.get("ORPHEUS_AUDIO_ENABLED", "1")).lower() in ("1", "true", "yes")
