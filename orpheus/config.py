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
VIDEO_UPLOAD_LIMIT_BYTES = int(
    VALUES.get("ORPHEUS_MAX_VIDEO_BYTES", 20 * 1024 * 1024 * 1024)
)
AUDIO_UPLOAD_LIMIT_BYTES = int(
    VALUES.get("ORPHEUS_MAX_AUDIO_BYTES", 100 * 1024 * 1024)
)
FREE_DISK_MARGIN_BYTES = int(
    VALUES.get("ORPHEUS_FREE_DISK_MARGIN_BYTES", 512 * 1024 * 1024)
)
if min(VIDEO_UPLOAD_LIMIT_BYTES, AUDIO_UPLOAD_LIMIT_BYTES, FREE_DISK_MARGIN_BYTES) <= 0:
    raise ValueError("Media and free-disk limits must be positive")
UPLOAD_LIMIT_BYTES = AUDIO_UPLOAD_LIMIT_BYTES
MEDIA_SECONDS = None
SAMPLE_RATE = 48000
MAX_TAKE_DURATION_S = int(VALUES.get("ORPHEUS_MAX_TAKE_SECONDS", 30))
if not 1 <= MAX_TAKE_DURATION_S <= 300:
    raise ValueError("Take duration must be between 1 and 300 seconds")
CONTROLLER_MODELS = [
    "meta/muse-spark-1.3-contributor",
    "qwen/qwen3.8-flash",
    "deepseek/deepseek-v4-flash-vision-exp",
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


MAX_FILE_BYTES = VIDEO_UPLOAD_LIMIT_BYTES
MAX_DURATION_S = MEDIA_SECONDS
MAX_BRIEF_CHARS = 240
MAX_FEEDBACK_CHARS = 500
SERVER_PORT = int(VALUES.get("ORPHEUS_SERVER_PORT", 8766))
if not 1024 <= SERVER_PORT <= 65535:
    raise ValueError("Orpheus server port must be between 1024 and 65535")

AUDIO_ENABLED = str(VALUES.get("ORPHEUS_AUDIO_ENABLED", "1")).lower() in (
    "1",
    "true",
    "yes",
)

# Separate loopback ports keep the reference lab and clean application independent.
GRAFANA_PORTS = {
    "GRAFANA": 13000,
    "LOKI": 13100,
    "PROMETHEUS": 19090,
    "TEMPO": 13200,
    "OTLP": 14319,
    "MCP": 18001,
    "METRICS": 19464,
}
GRAFANA_PORTS = {
    name: int(VALUES.get("ORPHEUS_" + name + "_PORT", value))
    for name, value in GRAFANA_PORTS.items()
}
if any(not 1024 <= port <= 65535 for port in GRAFANA_PORTS.values()) or len(
    set(GRAFANA_PORTS.values())
) != len(GRAFANA_PORTS):
    raise ValueError(
        "Orpheus observability ports must be distinct values from 1024 to 65535"
    )
