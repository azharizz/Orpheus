"""Deterministic media generated in temporary storage; no private lab fixtures."""
import atexit
import os
import tempfile
import wave
from functools import lru_cache
from pathlib import Path
import numpy as np

os.environ.setdefault("AGENT_PROVIDER_API_KEY", "offline-test-key")
os.environ["ORPHEUS_GRAFANA_ENABLED"] = "0"
from orpheus.projects import ff

_storage = tempfile.TemporaryDirectory(prefix="orpheus-tests-")
atexit.register(_storage.cleanup)


@lru_cache(maxsize=2)
def load_case(name="shoes"):
    folder = Path(_storage.name) / name
    folder.mkdir(exist_ok=True)
    rate = 48000
    seconds = 8.4 if name == "shoes" else 30
    count = round(seconds * rate)
    source = np.zeros(round(4 * rate))
    for time, level in [(0.25, 0.6), (1.1, 0.35), (2.0, 0.02)]:
        n = round(rate * 0.2)
        t = np.arange(n) / rate
        pulse = level * np.exp(-t * 45) * np.cos(2 * np.pi * 230 * t)
        offset = round(time * rate)
        source[offset:offset+n] += pulse
    original = np.zeros(count)
    for time in np.arange(0.8, seconds - 0.5, 0.7):
        start = round(time * rate)
        part = source[round(.25 * rate):round(.45 * rate)]
        original[start:start+len(part)] += part
    for filename, audio in [("sfx.wav", source), ("original.wav", original)]:
        with wave.open(str(folder / filename), "wb") as stream:
            stream.setparams((1, 2, rate, len(audio), "NONE", "not compressed"))
            stream.writeframes(np.round(audio * 32767).astype("<i2").tobytes())
    ff("-f", "lavfi", "-i", "testsrc2=s=96x64:r=30", "-i", folder / "original.wav",
       "-t", seconds, "-c:v", "libx264", "-c:a", "aac", folder / "video.mp4")
    return {"id": "a" * 16, "seconds": seconds, "context": "Synthetic fixture", "style": "",
            "has_original_audio": True, "input_warnings": [],
            "video_path": folder / "video.mp4", "original_path": folder / "original.wav", "sfx_path": folder / "sfx.wav"}
