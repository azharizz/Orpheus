"""Immutable Foley takes, local measurements, and reversible fitting projects."""

import hashlib
import json
import math
import time
import uuid
from pathlib import Path

from ..ops import observability as obs
from .projects import LIMIT, atomic, create, ff, load, probe, project_dir


def list_takes(pid):
    folder = project_dir(pid) / "takes"
    return (
        [json.loads(p.read_text()) for p in sorted(folder.glob("*.json"))]
        if folder.exists()
        else []
    )


def add_take(pid, path, brief="", start_s=0, clock="uploaded"):
    case = load(pid)
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
        or not 0 < path.stat().st_size <= LIMIT
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
        30,
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
        "audio_sha256": hashlib.sha256(wav.read_bytes()).hexdigest(),
        "profile": profile,
        "provenance": "user_take",
        "truncated_to_30s": float(info["format"].get("duration", profile["duration_s"]))
        > 30,
    }
    atomic(folder / (tid + ".json"), receipt)
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


def fitting_project(pid, tid):
    if not isinstance(tid, str) or not __import__("re").fullmatch("[a-f0-9]{12}", tid):
        raise ValueError("Invalid take")
    case = load(pid)
    folder = project_dir(pid) / "takes"
    take = json.loads((folder / (tid + ".json")).read_text())
    wav = folder / (tid + ".wav")
    if hashlib.sha256(wav.read_bytes()).hexdigest() != take["audio_sha256"]:
        raise ValueError("Take changed")
    doc = create(
        case["video_path"],
        wav,
        case["context"],
        case["style"],
        video_name="Take fitting · " + case.get("video_name", "scene"),
        sfx_name="Foley take " + tid,
    )
    doc.update(
        take_parent_project_id=pid,
        take_id=tid,
        take_brief=take["brief"],
        take_picture_start_s=take["picture_start_s"],
        take_clock=take["clock"],
    )
    atomic(project_dir(doc["id"]) / "project.json", doc)
    return doc


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
