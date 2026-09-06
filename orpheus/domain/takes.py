"""Immutable family-scoped Foley takes and local measurements."""

import json
import math
import re
import time
import uuid
from pathlib import Path

from ..ops import observability as obs
from ..config import AUDIO_UPLOAD_LIMIT_BYTES, MAX_TAKE_DURATION_S
from .projects import atomic, digest, ff, load, probe, project_dir


def list_takes(pid):
    folder = project_dir(pid) / "takes"
    return (
        [json.loads(p.read_text()) for p in sorted(folder.glob("*.json"))]
        if folder.exists()
        else []
    )


def validated_audio(pid, family_id, take_id):
    if not isinstance(take_id, str) or not re.fullmatch(r"[a-f0-9]{12}", take_id):
        raise ValueError("Invalid take ID")
    folder = project_dir(pid) / "takes"
    wav, receipt_path = folder / f"{take_id}.wav", folder / f"{take_id}.json"
    if not wav.is_file() or not receipt_path.is_file():
        raise ValueError("Unknown take")
    receipt = json.loads(receipt_path.read_text())
    if (
        receipt.get("id") != take_id
        or receipt.get("parent_project_id") != pid
        or receipt.get("family_id") != family_id
        or digest(wav) != receipt.get("audio_sha256")
    ):
        raise ValueError("Take provenance mismatch")
    return wav, receipt


def add_take(pid, path, brief="", start_s=0, clock="uploaded", family_id=None):
    case = load(pid)
    if family_id:
        from . import families

        families.get(pid, family_id)
    path = Path(path)
    if not isinstance(brief, str) or len(brief) > 240:
        raise ValueError("Take brief <=240 characters")
    if (
        isinstance(start_s, bool)
        or not isinstance(start_s, (int, float))
        or not math.isfinite(start_s)
        or not 0 <= start_s < case["seconds"]
    ):
        raise ValueError("Invalid picture start")
    if clock not in ("uploaded", "browser_playback"):
        raise ValueError("Invalid take clock")
    if (
        path.suffix.lower()
        not in (".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm", ".mp4")
        or not path.is_file()
        or not 0 < path.stat().st_size <= AUDIO_UPLOAD_LIMIT_BYTES
    ):
        raise ValueError("Invalid audio upload")
    info = probe(path)
    if not any(s["codec_type"] == "audio" for s in info["streams"]):
        raise ValueError("Take has no audio")
    folder = project_dir(pid) / "takes"
    folder.mkdir(exist_ok=True)
    tid = uuid.uuid4().hex[:12]
    wav = folder / (tid + ".wav")
    ff(
        "-protocol_whitelist",
        "file,pipe",
        "-i",
        path,
        "-t",
        MAX_TAKE_DURATION_S,
        "-vn",
        "-ar",
        48000,
        "-ac",
        1,
        "-c:a",
        "pcm_s16le",
        wav,
    )
    profile = obs.sound_profile(wav)
    if profile["duration_s"] < 0.1:
        raise ValueError("Take is too short")
    receipt = {
        "id": tid,
        "parent_project_id": pid,
        "created_at": time.time(),
        "brief": brief,
        "picture_start_s": start_s,
        "clock": clock,
        "clock_uncertainty": "Browser capture and picture clocks are not sample-synchronized; inspect and fit, do not assume zero latency.",
        "audio_sha256": digest(wav),
        "profile": profile,
        "provenance": "user_take",
        "family_id": family_id,
        "truncated": float(info["format"].get("duration", profile["duration_s"]))
        > MAX_TAKE_DURATION_S,
    }
    atomic(folder / (tid + ".json"), receipt)
    if family_id:
        families.assign_take(pid, family_id, tid)
    obs.emit(
        pid,
        "take_recorded",
        {
            "take_id": tid,
            "parent_project_id": pid,
            "profile": profile,
            "audio_sha256": receipt["audio_sha256"],
            "provenance": "user_take",
        },
    )
    return receipt


def save_experiment(pid, proposal, receipt_id):
    if not isinstance(proposal, dict) or set(proposal) != {
        "take_id",
        "change",
        "expected_effect",
        "reason",
    }:
        raise ValueError("Proposal requires take_id, change, expected_effect, reason")
    if proposal["take_id"] not in {r["id"] for r in list_takes(pid)}:
        raise ValueError("Unknown take")
    for key in ("change", "expected_effect", "reason"):
        if not isinstance(proposal[key], str) or not 1 <= len(proposal[key]) <= 500:
            raise ValueError("Experiment text 1..500 characters")
    record = {
        "id": uuid.uuid4().hex[:12],
        **proposal,
        "grafana_receipt_id": receipt_id,
        "created_at": time.time(),
        "provenance": "agent_hypothesis",
        "human_approved": False,
    }
    atomic(project_dir(pid) / (record["id"] + "-experiment.json"), record)
    obs.emit(
        pid,
        "take_experiment",
        {
            "parent_project_id": pid,
            "take_id": proposal["take_id"],
            "provenance": "agent_hypothesis",
        },
    )
    return record
