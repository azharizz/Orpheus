"""Validate uploads and preserve originals beside separate prepared media."""

import hashlib
import json
import math
import re
import shutil
import subprocess
import uuid
from pathlib import Path

from ..config import (
    DATA_DIR,
    FREE_DISK_MARGIN_BYTES,
    PROJECTS,
    VIDEO_UPLOAD_LIMIT_BYTES,
    prepare_storage,
)
from . import media

ROOT = DATA_DIR

prepare_storage()


def atomic(path, data):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)


def project_dir(project_id):
    if not re.fullmatch("[a-f0-9]{16}", project_id):
        raise ValueError("Invalid project ID")
    return PROJECTS / project_id


def load(project_id):
    path = project_dir(project_id)
    doc = json.loads((path / "project.json").read_text())
    if doc.get("schema") != "orpheus.v3":
        raise ValueError("Unsupported project schema")
    source_name = doc["preparation"]["original_files"]["video"]
    return {
        **doc,
        "video_path": path / "video.mp4",
        "source_video_path": path / source_name,
        "original_path": path / "original.wav",
        "mix_path": path / "mix.wav",
    }


def digest(path):
    value = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def ff(*args):
    subprocess.run(
        ["ffmpeg", "-v", "error", "-nostdin", "-y", *map(str, args)],
        check=True,
        capture_output=True,
        timeout=7200,
    )


def probe(path):
    return json.loads(
        subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-protocol_whitelist",
                "file,pipe",
                "-show_streams",
                "-show_format",
                "-of",
                "json",
                str(path),
            ],
            stderr=subprocess.DEVNULL,
            timeout=120,
        )
    )


def frames(case, times, directory):
    """Decode bounded timestamp seeks without enumerating every frame in a film."""
    directory.mkdir(parents=True, exist_ok=True)
    result = []
    for t in times:
        if (
            not isinstance(t, (int, float))
            or not math.isfinite(t)
            or not 0 <= t < case["seconds"]
        ):
            raise ValueError("Frame outside clipped window")
        requested = min(float(t), max(0.0, case["seconds"] - 0.001))
        actual, path = requested, None
        for attempt in (requested, max(0.0, case["seconds"] - 0.25)):
            candidate = directory / f"frame-{attempt:.6f}.jpg"
            try:
                if not candidate.exists() or not candidate.stat().st_size:
                    ff(
                        "-ss", attempt, "-i", case["video_path"], "-frames:v", 1,
                        "-vf", "scale=512:-2,format=yuvj420p", "-threads", 1,
                        "-q:v", 4, candidate,
                    )
                if candidate.exists() and candidate.stat().st_size:
                    actual, path = attempt, candidate
                    break
            except subprocess.SubprocessError:
                candidate.unlink(missing_ok=True)
        if path is None:
            raise ValueError("Frame could not be decoded")
        result.append((actual, path))
    return result


def create(video, context="", style="", video_name=None):
    """Create one current-schema, video-first project."""
    video = Path(video)
    if len(context) > 240 or len(style) > 240:
        raise ValueError("Context and sound brief are limited to 240 characters each")
    if video.suffix.lower() not in (
        ".mp4",
        ".mov",
        ".webm",
        ".mkv",
    ):
        raise ValueError("Unsupported file extension")
    if not video.is_file() or not 0 < video.stat().st_size <= VIDEO_UPLOAD_LIMIT_BYTES:
        raise ValueError("Video must be nonempty and within the configured limit")
    vp = probe(video)
    if not any(s["codec_type"] == "video" for s in vp["streams"]):
        raise ValueError("Target must contain video")
    video_seconds = float(vp["format"]["duration"])
    if not math.isfinite(video_seconds) or video_seconds <= 0:
        raise ValueError("Media durations must be finite and positive")
    seconds = video_seconds
    if seconds < 0.5:
        raise ValueError("Video must be at least 0.5 seconds")
    has_audio = any(s["codec_type"] == "audio" for s in vp["streams"])
    input_channels = int(
        next((s.get("channels", 1) for s in vp["streams"] if s["codec_type"] == "audio"), 1)
    )
    PROJECTS.mkdir(parents=True, exist_ok=True)
    pcm_bytes = round(seconds * media.RATE * 2 * (1 + (min(2, input_channels) if has_audio else 1)))
    required_bytes = video.stat().st_size * 2 + pcm_bytes + FREE_DISK_MARGIN_BYTES
    if shutil.disk_usage(PROJECTS).free < required_bytes:
        raise ValueError("Insufficient free disk space for originals and prepared media")
    pid = uuid.uuid4().hex[:16]
    folder = project_dir(pid)
    folder.mkdir(parents=True)
    try:
        originals = folder / "originals"
        originals.mkdir()
        supplied = [("video", video)]
        for name, path in supplied:
            shutil.copyfile(path, originals / (name + path.suffix.lower()))
        ff(
            "-protocol_whitelist",
            "file,pipe",
            "-i",
            video,
            "-map",
            "0:v:0",
            "-map",
            "0:a:0?",
            "-vf",
            "scale=1280:720:force_original_aspect_ratio=decrease:force_divisible_by=2",
            "-c:v",
            "libx264",
            "-preset",
            "fast",
            "-crf",
            "20",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            folder / "video.mp4",
        )
        if has_audio:
            ff(
                "-protocol_whitelist",
                "file,pipe",
                "-i",
                video,
                "-map",
                "0:a:0",
                "-vn",
                "-ar",
                48000,
                "-ac",
                1,
                "-c:a",
                "pcm_s16le",
                folder / "original.wav",
            )
            ff(
                "-protocol_whitelist",
                "file,pipe",
                "-i",
                video,
                "-map",
                "0:a:0",
                "-vn",
                "-ar",
                48000,
                "-ac",
                min(2, input_channels),
                "-c:a",
                "pcm_s16le",
                folder / "mix.wav",
            )
        else:
            ff(
                "-f",
                "lavfi",
                "-i",
                "anullsrc=r=48000:cl=mono",
                "-t",
                seconds,
                folder / "original.wav",
            )
            shutil.copyfile(folder / "original.wav", folder / "mix.wav")
        warnings = ["mono_analysis_copy"]
        if not has_audio:
            warnings.append("no_original_audio")
        files = ["video.mp4", "original.wav", "mix.wav"]
        doc = {
            "schema": "orpheus.v3",
            "id": pid,
            "seconds": seconds,
            "input_duration_s": float(vp["format"]["duration"]),
            "context": context,
            "style": style,
            "has_original_audio": has_audio,
            "video_name": (video_name or video.name)[:180],
            "source_hashes": {
                k: digest(p) for k, p in supplied
            },
            "prepared_hashes": {
                n: digest(folder / n) for n in files
            },
            "rights": "User-supplied local test media; no redistribution licence inferred.",
            "preparation": {
                "video_truncated": False,
                "analysis_format": "Full-duration 48kHz mono PCM16 analysis copy",
                "mix_format": f"Full-duration 48kHz {min(2, input_channels) if has_audio else 1}-channel PCM16 working mix",
                "original_files": {
                    name: "originals/" + name + path.suffix.lower()
                    for name, path in supplied
                },
                "warning": "Private byte-for-byte originals retained; previews and analysis are derived copies. Originals are not served over HTTP.",
            },
            "input_warnings": warnings,
            "status": "ready",
            "turns": [],
        }
        atomic(folder / "project.json", doc)
        return doc
    except Exception:
        # Preserve failed preparation for diagnostics, but never advertise it as runnable.
        atomic(
            folder / "preparation_failed.json",
            {"error": "Media preparation failed; no agent called"},
        )
        raise
