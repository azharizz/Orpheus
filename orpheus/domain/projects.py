"""Validate uploads and preserve originals beside separate prepared media."""

import hashlib
import json
import math
import re
import shutil
import subprocess
import uuid
from pathlib import Path

from ..config import DATA_DIR, PROJECTS, prepare_storage
from ..config import UPLOAD_LIMIT_BYTES as LIMIT
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
    return {
        **doc,
        "video_path": path / "video.mp4",
        "original_path": path / "original.wav",
        "sfx_path": path / "sfx.wav",
    }


def ff(*args):
    subprocess.run(
        ["ffmpeg", "-v", "error", "-nostdin", "-y", *map(str, args)],
        check=True,
        capture_output=True,
        timeout=300,
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
    """Resolve requests to actual decoded frame timestamps, including the final frame."""
    directory.mkdir(parents=True, exist_ok=True)
    info = json.loads(
        subprocess.check_output(
            [
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "v:0",
                "-show_frames",
                "-show_entries",
                "frame=best_effort_timestamp_time",
                "-of",
                "json",
                str(case["video_path"]),
            ],
            timeout=120,
        )
    )
    pts = [
        float(f["best_effort_timestamp_time"])
        for f in info["frames"]
        if "best_effort_timestamp_time" in f
    ]
    if not pts:
        raise ValueError("No decoded video frames")
    result = []
    for t in times:
        if (
            not isinstance(t, (int, float))
            or not math.isfinite(t)
            or not 0 <= t < case["seconds"]
        ):
            raise ValueError("Frame outside clipped window")
        actual = min(pts, key=lambda p: abs(p - t))
        path = directory / f"frame-{actual:.6f}.jpg"
        if not path.exists() or not path.stat().st_size:
            ff(
                "-i",
                case["video_path"],
                "-ss",
                actual,
                "-frames:v",
                1,
                "-vf",
                "scale=512:-2,format=yuvj420p",
                "-threads",
                1,
                "-q:v",
                4,
                path,
            )
        if not path.exists() or not path.stat().st_size:
            raise ValueError("Frame could not be decoded")
        result.append((actual, path))
    return result


def create(video, sfx, context="", style="", video_name=None, sfx_name=None):
    video, sfx = Path(video), Path(sfx)
    if len(context) > 240 or len(style) > 240:
        raise ValueError("Context and sound brief are limited to 240 characters each")
    if video.suffix.lower() not in (
        ".mp4",
        ".mov",
        ".webm",
        ".mkv",
    ) or sfx.suffix.lower() not in (".wav", ".mp3", ".m4a", ".flac", ".ogg"):
        raise ValueError("Unsupported file extension")
    if any(not p.is_file() or not 0 < p.stat().st_size <= LIMIT for p in (video, sfx)):
        raise ValueError("Each file must be nonempty and <=100 MiB")
    vp, sp = probe(video), probe(sfx)
    if not any(s["codec_type"] == "video" for s in vp["streams"]):
        raise ValueError("Target must contain video")
    if not any(s["codec_type"] == "audio" for s in sp["streams"]):
        raise ValueError("SFX must contain audio")
    video_seconds = float(vp["format"]["duration"])
    sfx_seconds = float(sp["format"]["duration"])
    if not all(math.isfinite(t) and t > 0 for t in (video_seconds, sfx_seconds)):
        raise ValueError("Media durations must be finite and positive")
    seconds = min(30, video_seconds)
    if seconds < 0.5:
        raise ValueError("Video must be at least 0.5 seconds")
    has_audio = any(s["codec_type"] == "audio" for s in vp["streams"])
    pid = uuid.uuid4().hex[:16]
    folder = project_dir(pid)
    folder.mkdir(parents=True)
    try:
        originals = folder / "originals"
        originals.mkdir()
        for name, path in [("video", video), ("sfx", sfx)]:
            shutil.copyfile(path, originals / (name + path.suffix.lower()))
        ff(
            "-protocol_whitelist",
            "file,pipe",
            "-i",
            video,
            "-t",
            seconds,
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
                "-t",
                seconds,
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
        ff(
            "-protocol_whitelist",
            "file,pipe",
            "-i",
            sfx,
            "-t",
            30,
            "-vn",
            "-ar",
            48000,
            "-ac",
            1,
            "-c:a",
            "pcm_s16le",
            folder / "sfx.wav",
        )
        source_analysis = media.analyse(folder / "sfx.wav")
        if source_analysis["body_dbfs"] < -65:
            raise ValueError("SFX too quiet: supply a usable recording")
        original_analysis = media.analyse(folder / "original.wav")
        warnings = ["mono_analysis_copy", "whole_soundtrack_replacement"]
        if video_seconds > 30:
            warnings.append("video_truncated")
        if sfx_seconds > 30:
            warnings.append("source_truncated")
        if not has_audio:
            warnings.append("no_original_audio")
        if source_analysis["clipped_samples"]:
            warnings.append("source_near_full_scale_samples")
        if has_audio and original_analysis["clipped_samples"]:
            warnings.append("original_near_full_scale_samples")
        doc = {
            "id": pid,
            "seconds": seconds,
            "input_duration_s": float(vp["format"]["duration"]),
            "context": context,
            "style": style,
            "has_original_audio": has_audio,
            "video_name": (video_name or video.name)[:180],
            "sfx_name": (sfx_name or sfx.name)[:180],
            "source_hashes": {
                k: hashlib.sha256(p.read_bytes()).hexdigest()
                for k, p in [("video", video), ("sfx", sfx)]
            },
            "prepared_hashes": {
                n: hashlib.sha256((folder / n).read_bytes()).hexdigest()
                for n in ["video.mp4", "original.wav", "sfx.wav"]
            },
            "rights": "User-supplied local test media; no redistribution licence inferred.",
            "preparation": {
                "sfx_input_duration_s": sfx_seconds,
                "sfx_prepared_duration_s": source_analysis["duration_s"],
                "video_truncated": video_seconds > 30,
                "sfx_truncated": sfx_seconds > 30,
                "analysis_format": "48kHz mono PCM16; original.wav extracted directly from uploaded video",
                "original_files": {
                    name: "originals/" + name + path.suffix.lower()
                    for name, path in [("video", video), ("sfx", sfx)]
                },
                "warning": "Private byte-for-byte originals retained; analysis is a separate clipped mono copy. Originals are not served over HTTP.",
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
