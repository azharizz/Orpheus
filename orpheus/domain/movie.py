"""Resumable, bounded movie-level evidence over the sound-family workflow."""

import hashlib
import json
import math
import time
import uuid
import wave
from pathlib import Path

import numpy as np

from ..config import SAMPLE_RATE as RATE
from ..ops import observability as obs
from . import families, media, projects, takes

SCHEMA = "movie-analysis.v1"
SCAN_S = 0.1
MAX_WAVE_BUCKETS = 2400


def _path(pid):
    return projects.project_dir(pid) / "movie-analysis.json"


def status(pid):
    projects.load(pid)
    path = _path(pid)
    if path.exists():
        return json.loads(path.read_text())
    return {
        "schema": SCHEMA,
        "project_id": pid,
        "status": "not_started",
        "progress": 0,
        "waveform": [],
        "events": [],
        "noise_regions": [],
        "review_queue": [],
        "families": [],
    }


def _save(pid, doc):
    doc["updated_at"] = time.time()
    projects.atomic(_path(pid), doc)


def _bucket(samples):
    values = samples.astype(np.float32) / 32768
    if not len(values):
        return 0.0, 0.0, 0.0
    rms = float(np.sqrt(np.mean(values * values)))
    peak = float(np.max(np.abs(values)))
    peak_at = int(np.argmax(np.abs(values)))
    local = values[peak_at : peak_at + min(len(values) - peak_at, round(RATE * .06))]
    zcr = float(np.mean(np.signbit(local[1:]) != np.signbit(local[:-1]))) if len(local) > 1 else 0
    return rms, peak, zcr


def _events(rows, seconds):
    levels = np.array([row[1] for row in rows], dtype=np.float32)
    if not len(levels):
        return [], []
    floor = float(np.median(levels))
    spread = float(np.median(np.abs(levels - floor)))
    threshold = max(10 ** (-38 / 20), floor + max(spread * 6, 0.006))
    events, current = [], []
    for row in rows:
        active = row[1] >= threshold and row[2] >= threshold * 1.35
        if active:
            current.append(row)
        elif current:
            events.append(current)
            current = []
    if current:
        events.append(current)
    result = []
    for group in events:
        peak = max(group, key=lambda row: row[2])
        start = max(0.0, group[0][0] - 0.08)
        end = min(seconds, group[-1][0] + SCAN_S + 0.18)
        if end - start < 0.04:
            continue
        zcr = sum(row[3] for row in group) / len(group)
        band = "low" if zcr < 0.015 else "mid" if zcr < 0.055 else "bright"
        result.append({
            "id": uuid.uuid5(uuid.NAMESPACE_URL, f"{start:.3f}:{end:.3f}").hex[:12],
            "range_s": [round(start, 3), round(end, 3)],
            "anchor_s": round(peak[0], 3),
            "rms_dbfs": round(media.db(max(peak[1], 1e-9)), 2),
            "peak_dbfs": round(media.db(max(peak[2], 1e-9)), 2),
            "acoustic_band": band,
            "status": "unreviewed",
        })
    active = [index for index, (_, rms, peak, _) in enumerate(rows) if rms > max(floor * 2.5, 10 ** (-42 / 20)) and peak / max(rms, 1e-9) < 2.4]
    groups = []
    for index in active:
        if not groups or index - groups[-1][-1] > 5:
            groups.append([index])
        else:
            groups[-1].append(index)
    noise = []
    for group in groups:
        start, end = rows[group[0]][0], min(seconds, rows[group[-1]][0] + SCAN_S)
        if end - start >= 1.5:
            noise.append({
                "id": uuid.uuid5(uuid.NAMESPACE_URL, f"noise:{start:.3f}:{end:.3f}").hex[:12],
                "range_s": [round(start, 3), round(end, 3)],
                "kind": "potential_noise",
                "status": "unreviewed",
                "warning": "Sustained-signal heuristic; listen before removing anything.",
            })
    return result, noise


def _waveform(rows, seconds):
    step = max(1, math.ceil(len(rows) / MAX_WAVE_BUCKETS))
    return [
        {
            "time_s": round(group[0][0], 3),
            "rms_dbfs": round(media.db(max(sum(r[1] for r in group) / len(group), 1e-9)), 2),
            "peak_dbfs": round(media.db(max(r[2] for r in group)), 2),
        }
        for start in range(0, len(rows), step)
        if (group := rows[start : start + step])
    ]


def _propose_families(pid, events):
    existing = families.list_families(pid)
    automatic = {item.get("proposal_band"): item for item in existing if item.get("origin") == "movie_agent"}
    proposed = []
    labels = {"low": "Body and low impacts", "mid": "Footsteps and contact", "bright": "Cloth and bright props"}
    for band in ("low", "mid", "bright"):
        group = [event for event in events if event["acoustic_band"] == band]
        if len(group) < 2:
            continue
        family = automatic.get(band)
        if family is None:
            seed = max(group, key=lambda item: item["peak_dbfs"])
            seed_range = [max(0, seed["anchor_s"] - .08), min(projects.load(pid)["seconds"], seed["anchor_s"] + .56)]
            family = families.create(pid, labels[band], seed_range, defer=True)
            family.update(origin="movie_agent", proposal_band=band)
            projects.atomic(projects.project_dir(pid) / "families" / f"{family['id']}.json", family)
            try:
                family = families.search(pid, family["id"])
            except Exception:
                family = families.get(pid, family["id"])
        proposed.append({
            "id": family["id"],
            "name": family["name"],
            "band": band,
            "event_count": len(group),
            "status": family["status"],
            "replacement_take_id": family.get("replacement_take_id"),
        })
    return proposed


def analyze(pid, *, resume=True):
    """Scan PCM in small blocks, checkpoint progress, then propose families."""
    case = projects.load(pid)
    if case.get("status") in ("preparing", "preparation_failed"):
        raise ValueError("Movie media must finish preparation before analysis")
    prior = status(pid)
    if resume and prior.get("status") in ("review_required", "ready"):
        return prior
    bucket_path = projects.project_dir(pid) / "movie-buckets.jsonl"
    source_hash = case.get("prepared_hashes", {}).get("original.wav")
    can_resume = resume and prior.get("status") == "analyzing" and prior.get("source_hash") == source_hash and bucket_path.exists()
    rows = []
    if can_resume:
        for line in bucket_path.read_text().splitlines():
            try:
                row = json.loads(line)
                rows.append((row["time_s"], row["rms"], row["peak"], row["zcr"]))
            except (ValueError, KeyError, TypeError):
                break
    else:
        bucket_path.unlink(missing_ok=True)
    doc = {
        "schema": SCHEMA,
        "project_id": pid,
        "status": "analyzing",
        "progress": 0,
        "started_at": time.time(),
        "source_hash": source_hash,
        "completed_buckets": len(rows),
        "waveform": [],
        "events": [],
        "noise_regions": [],
        "review_queue": [],
        "families": [],
        "agent": {"role": "coordinator", "stage": "deterministic_evidence"},
    }
    _save(pid, doc)
    with wave.open(str(case["original_path"]), "rb") as source:
        channels, total = source.getnchannels(), source.getnframes()
        size = round(RATE * SCAN_S)
        offset = min(total, len(rows) * size)
        source.setpos(offset)
        pending_rows = []
        while offset < total:
            raw = source.readframes(min(size, total - offset))
            values = np.frombuffer(raw, dtype="<i2")
            if channels == 2:
                values = values.reshape(-1, 2).mean(axis=1).astype("<i2")
            row = (offset / RATE, *_bucket(values))
            rows.append(row)
            pending_rows.append(row)
            offset += len(values)
            if len(pending_rows) >= 600 or offset >= total:
                with bucket_path.open("a") as stream:
                    for at, rms, peak, zcr in pending_rows:
                        stream.write(json.dumps({"time_s": at, "rms": rms, "peak": peak, "zcr": zcr}) + "\n")
                pending_rows.clear()
                doc["progress"] = round(offset / total * 70, 1)
                doc["completed_buckets"] = len(rows)
                _save(pid, doc)
    doc["waveform"] = _waveform(rows, case["seconds"])
    doc["events"], doc["noise_regions"] = _events(rows, case["seconds"])
    doc["progress"] = 75
    doc["agent"]["stage"] = "family_proposals"
    _save(pid, doc)
    doc["families"] = _propose_families(pid, doc["events"])
    doc["review_queue"] = [
        *[{"id": item["id"], "kind": "family", "family_id": item["id"], "time_s": next((e["anchor_s"] for e in doc["events"] if e["acoustic_band"] == item.get("band")), 0), "title": item["name"], "status": "review_required", "reason": "Review acoustic matches and assign a replacement take."} for item in doc["families"]],
        *[{"id": item["id"], "kind": "noise", "time_s": item["range_s"][0], "title": "Potential noise", "status": item["status"], "reason": item["warning"]} for item in doc["noise_regions"]],
    ]
    doc["status"] = "review_required" if doc["review_queue"] else "ready"
    doc["progress"] = 100
    doc["agent"]["stage"] = "awaiting_human_review" if doc["review_queue"] else "complete"
    doc["finished_at"] = time.time()
    _save(pid, doc)
    obs.emit(pid, "movie_analysis", {"status": doc["status"], "measurements": {"progress": 100, "events": len(doc["events"]), "families": len(doc["families"]), "noise_regions": len(doc["noise_regions"]), "duration_s": case["seconds"]}})
    for item in doc["waveform"]:
        obs.emit(pid, "movie_signal", item)
    for item in doc["noise_regions"]:
        obs.emit(pid, "movie_noise", {**item, "start_s": item["range_s"][0], "end_s": item["range_s"][1]})
    return doc


def review(pid, item_id, decision):
    if decision not in ("accepted", "rejected", "needs_sfx"):
        raise ValueError("Invalid movie review decision")
    doc = status(pid)
    item = next((row for row in doc["review_queue"] if row["id"] == item_id), None)
    if item is None:
        raise ValueError("Unknown movie review item")
    item["status"] = decision
    item["reviewed_at"] = time.time()
    _save(pid, doc)
    obs.emit(pid, "movie_review", {"event_id": item_id, "family_id": item.get("family_id"), "decision": decision, "time_s": item["time_s"]})
    return doc


def eligible_families(pid):
    return [item for item in families.list_families(pid) if item.get("replacement_take_id") and item.get("accepted_ranges")]


def render_draft(pid):
    """Compose reviewed families into one movie draft without touching other PCM."""
    case = projects.load(pid)
    if case.get("status") in ("preparing", "preparation_failed"):
        raise ValueError("Movie media must finish preparation before rendering")
    selected = eligible_families(pid)
    if not selected:
        raise ValueError("Assign a replacement take to at least one reviewed family")
    folder = projects.project_dir(pid)
    render_id = uuid.uuid4().hex[:12]
    current = Path(case["mix_path"])
    temporary = []
    rows = []
    occupied = []
    try:
        for index, family in enumerate(selected):
            accepted = sorted(family["accepted_ranges"], key=lambda item: item["range_s"][0])
            if any(a[0] < b[1] and b[0] < a[1] for item in accepted for a in [item["range_s"]] for b in occupied):
                rows.append({"family_id": family["id"], "status": "deferred_overlap"})
                continue
            source, _ = takes.validated_audio(pid, family["id"], family["replacement_take_id"])
            output = folder / f".{render_id}-{index}.wav"
            families._write_selective_wav(
                current,
                output,
                families._mono(families._read_pcm(source)),
                accepted,
                -12,
                0.025,
                0,
            )
            if current != Path(case["mix_path"]):
                temporary.append(current)
            current = output
            occupied.extend(item["range_s"] for item in accepted)
            rows.append({"family_id": family["id"], "take_id": family["replacement_take_id"], "status": "drafted", "ranges": len(accepted)})
        if not any(row["status"] == "drafted" for row in rows):
            raise ValueError("Reviewed family ranges overlap; resolve them before rendering")
        wav_path = folder / f"{render_id}.wav"
        current.replace(wav_path)
        video_path = folder / f"{render_id}.mp4"
        projects.ff("-i", case["video_path"], "-i", wav_path, "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", case["seconds"], video_path)
        picture_unchanged = media.picture_hash(case["video_path"]) == media.picture_hash(video_path)
        if not picture_unchanged:
            raise ValueError("Picture preservation failed")
        receipt = {
            "schema": "movie-render.v1",
            "id": render_id,
            "project_id": pid,
            "video": video_path.name,
            "wav": wav_path.name,
            "audio_sha256": projects.digest(wav_path),
            "render_mode": "reviewed_multi_family_selective_overlay",
            "families": rows,
            "metrics": {**media.measure_export(video_path), "picture_unchanged": True, "clipped_samples": 0},
            "human_approved": False,
            "warning": "Only reviewed families with assigned takes were drafted; overlap and unknown sounds remain untouched.",
        }
        projects.atomic(folder / f"{render_id}.json", receipt)
        doc = status(pid)
        doc["latest_render"] = receipt
        doc["status"] = "review_required"
        _save(pid, doc)
        obs.emit(pid, "movie_candidate", {**receipt, "measurements": {"families_drafted": sum(row["status"] == "drafted" for row in rows)}})
        return receipt
    finally:
        for path in temporary:
            path.unlink(missing_ok=True)
        if current.name.startswith(f".{render_id}-"):
            current.unlink(missing_ok=True)
