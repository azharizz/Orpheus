"""Bind the existing fitting agent to one reviewed sound family."""

import json
import math
import re
import time
import uuid
import wave
from pathlib import Path

import numpy as np

from ..config import SAMPLE_RATE as RATE
from ..ops import observability as obs
from . import families, media, projects, takes

CHUNK_FRAMES = RATE * 10
PREVIEW_SECONDS = 15


def _write_wav(path, samples):
    samples = np.asarray(samples)
    channels = 1 if samples.ndim == 1 else samples.shape[1]
    with wave.open(str(path), "wb") as output:
        output.setparams((channels, 2, RATE, len(samples), "NONE", "not compressed"))
        output.writeframes(
            np.clip(np.round(samples * 32768), -32768, 32767).astype("<i2").tobytes()
        )


def load_case(pid, family_id):
    """Resolve one assigned take without creating a linked compatibility project."""
    case = projects.load(pid)
    family = families.get(pid, family_id)
    accepted = family.get("accepted_ranges")
    take_id = family.get("replacement_take_id")
    if not accepted:
        raise ValueError("Confirm at least one family range before agent fitting")
    if not take_id:
        raise ValueError("Assign a replacement take before agent fitting")
    wav, _ = takes.validated_audio(pid, family_id, take_id)
    case.update(
        sfx_path=wav,
        family_id=family_id,
        family_name=family["name"],
        accepted_ranges=[item["range_s"] for item in accepted],
        replacement_take_id=take_id,
    )
    if case["seconds"] > PREVIEW_SECONDS:
        seed = next((item for item in accepted if item["id"] == "seed"), accepted[0])
        center = sum(seed["range_s"]) / 2
        start = max(0, min(case["seconds"] - PREVIEW_SECONDS, center - PREVIEW_SECONDS / 2))
        duration = min(PREVIEW_SECONDS, case["seconds"] - start)
        folder = projects.project_dir(pid) / "previews"
        folder.mkdir(exist_ok=True)
        video = folder / f"{family_id}.mp4"
        original = folder / f"{family_id}-original.wav"
        mix = folder / f"{family_id}-mix.wav"
        if not video.is_file():
            projects.ff(
                "-ss", start, "-i", case["video_path"], "-t", duration,
                "-map", "0:v:0", "-an", "-c:v", "libx264", "-preset", "ultrafast", video,
            )
        for source, output in ((case["original_path"], original), (case.get("mix_path", case["original_path"]), mix)):
            if not output.is_file():
                _write_wav(output, families._read_range(source, round(start * RATE), round(duration * RATE)))
        local = [[round(max(0, value - start), 6) for value in seed["range_s"]]]
        case.update(
            full_seconds=case["seconds"],
            timeline_offset_s=start,
            seconds=duration,
            video_path=video,
            source_video_path=video,
            original_path=original,
            mix_path=mix,
            accepted_ranges=local,
            accepted_items=[{
                **seed,
                "range_s": local[0],
                "refined_anchor_s": seed.get("refined_anchor_s", center) - start,
            }],
        )
    return case


def render_baseline(pid, family_id, *, persist=False):
    case = load_case(pid, family_id)
    return families.render(
        pid, family_id, case=case, accepted=case.get("accepted_items"), persist=persist
    )


def _ranges(case):
    return [
        tuple(round(value * RATE) for value in families._range(item, case["seconds"]))
        for item in case["accepted_ranges"]
    ]


def _decode(raw, channels):
    values = np.frombuffer(raw, dtype="<i2").astype(np.float32) / 32768
    return values.reshape(-1, channels) if channels == 2 else values


def _pairs(original_path, layer_path):
    original_frames, original_channels = families._wav_shape(original_path)
    layer_frames, layer_channels = families._wav_shape(layer_path)
    if layer_channels != 1 or layer_frames != original_frames:
        raise ValueError("Agent layer must be full-duration mono PCM")
    with wave.open(str(original_path), "rb") as original, wave.open(
        str(layer_path), "rb"
    ) as layer:
        offset = 0
        while offset < original_frames:
            count = min(CHUNK_FRAMES, original_frames - offset)
            source = _decode(original.readframes(count), original_channels)
            fitted = _decode(layer.readframes(count), 1)
            yield offset, source, fitted
            offset += len(fitted)


def _components(original, layer, offset, ranges, duck_db, ramp_s):
    floor = 10 ** (duck_db / 20)
    allowed = np.zeros(len(layer), dtype=bool)
    envelope = np.ones(len(layer), dtype=np.float32)
    stop = offset + len(layer)
    for start, end in ranges:
        left, right = max(offset, start), min(stop, end)
        if left >= right:
            continue
        a, b = left - offset, right - offset
        allowed[a:b] = True
        length = end - start
        ramp = min(round(ramp_s * RATE), length // 2)
        curve = np.full(length, floor, dtype=np.float32)
        if ramp:
            curve[:ramp] = np.linspace(1, floor, ramp, endpoint=False)
            curve[-ramp:] = np.linspace(floor, 1, ramp, endpoint=False)
        c = left - start
        envelope[a:b] = np.minimum(envelope[a:b], curve[c : c + b - a])
    if np.any(layer[~allowed]):
        raise ValueError("Agent layer places sound outside accepted family ranges")
    fitted = (
        layer
        if original.ndim == 1
        else np.broadcast_to(layer[:, None], original.shape)
    )
    ducked = original * (envelope if original.ndim == 1 else envelope[:, None])
    return ducked, fitted


def _write_mix(original_path, layer_path, output_path, ranges, duck_db, ramp_s):
    scale = 1.0
    for offset, original, layer in _pairs(original_path, layer_path):
        ducked, fitted = _components(original, layer, offset, ranges, duck_db, ramp_s)
        positive, negative = fitted > 1e-9, fitted < -1e-9
        if np.any(positive):
            scale = min(scale, float(np.min((0.999 - ducked[positive]) / fitted[positive])))
        if np.any(negative):
            scale = min(scale, float(np.min((-0.999 - ducked[negative]) / fitted[negative])))
    scale = min(1.0, max(0.0, scale))
    frames, channels = families._wav_shape(original_path)
    peak = 0.0
    with wave.open(str(output_path), "wb") as output:
        output.setparams((channels, 2, RATE, frames, "NONE", "not compressed"))
        for offset, original, layer in _pairs(original_path, layer_path):
            ducked, fitted = _components(original, layer, offset, ranges, duck_db, ramp_s)
            mixed = ducked + fitted * scale
            peak = max(peak, float(np.max(np.abs(mixed))))
            output.writeframes(
                np.clip(np.round(mixed * 32768), -32768, 32767)
                .astype("<i2")
                .tobytes()
            )
    if peak >= 1:
        output_path.unlink(missing_ok=True)
        raise ValueError("Agent-fitted mix clips")
    return round(20 * math.log10(max(scale, 1e-9)), 3)


def render_selection(
    pid,
    family_id,
    candidate_id,
    *,
    duck_db=-12,
    ramp_s=0.025,
    baseline=None,
    grafana_evidence=None,
):
    """Validate a fitted layer, then mix it only across accepted family windows."""
    case = load_case(pid, family_id)
    if not isinstance(candidate_id, str) or not re.fullmatch("[a-f0-9]{12}", candidate_id):
        raise ValueError("Invalid agent candidate")
    folder = projects.project_dir(pid)
    candidate_path = folder / f"{candidate_id}.json"
    layer_path = folder / f"{candidate_id}.wav"
    candidate = json.loads(candidate_path.read_text())
    if (
        candidate.get("family_id") != family_id
        or projects.digest(layer_path) != candidate.get("audio_sha256")
    ):
        raise ValueError("Agent candidate provenance mismatch")
    if not -30 <= float(duck_db) <= 0 or not 0.005 <= float(ramp_s) <= 0.25:
        raise ValueError("Mix controls outside bounds")
    ranges = _ranges(case)
    render_id = uuid.uuid4().hex[:12]
    wav_path, video_path = folder / f"{render_id}.wav", folder / f"{render_id}.mp4"
    protection = _write_mix(
        Path(case.get("mix_path", case["original_path"])),
        layer_path,
        wav_path,
        ranges,
        float(duck_db),
        float(ramp_s),
    )
    projects.ff(
        "-i", case["video_path"], "-i", wav_path, "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", case["seconds"],
        "-movflags", "+faststart", video_path,
    )
    source_video = Path(case.get("source_video_path", case["video_path"]))
    suffix = ".mp4" if source_video.suffix.lower() == ".mp4" else ".mkv"
    master_path = folder / f"{render_id}-master{suffix}"
    projects.ff(
        "-i", source_video, "-i", wav_path, "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-t", case["seconds"],
        master_path,
    )
    if media.picture_hash(source_video) != media.picture_hash(master_path):
        raise ValueError("Picture preservation failed")
    family_doc = families.get(pid, family_id)
    accepted = case.get("accepted_items") or family_doc["accepted_ranges"]
    mix_path = Path(case.get("mix_path", case["original_path"]))
    dialogue = [
        item["id"]
        for item in accepted
        if families._possible_dialogue_or_music(
            families._read_range(
                mix_path,
                round(item["range_s"][0] * RATE),
                round((item["range_s"][1] - item["range_s"][0]) * RATE),
            )
        )
    ]
    receipt = {
        "id": render_id,
        "schema": "family-render.v1",
        "project_id": pid,
        "family_id": family_id,
        "take_id": case["replacement_take_id"],
        "video": video_path.name,
        "master": master_path.name,
        "wav": wav_path.name,
        "render_mode": "agent_fitted_selective_duck_overlay",
        "timeline_offset_s": case.get("timeline_offset_s", 0),
        "preview_duration_s": case["seconds"],
        "audio_sha256": projects.digest(wav_path),
        "agent_fitting": {
            "candidate_id": candidate_id,
            "render_mode": candidate.get("render_mode"),
            "arrangement": candidate.get("arrangement"),
            "plan": candidate.get("plan", []),
            "deterministic_baseline": baseline,
            "grafana_evidence": grafana_evidence or {},
        },
        "mix": {
            "duck_db": float(duck_db),
            "ramp_s": float(ramp_s),
            "replacement_peak_protection_db": protection,
            "ranges_s": [item["range_s"] for item in accepted],
            "global_ranges_s": [item["range_s"] for item in family_doc["accepted_ranges"]],
            "possible_dialogue_or_music_overlap_ids": dialogue,
            "warning": "Dialogue/music overlap is a conservative spectral heuristic, not source separation.",
        },
        "metrics": {
            **media.measure_export(video_path),
            "picture_unchanged": True,
            "clipped_samples": 0,
        },
        "human_approved": False,
        "warning": "Agent fitting is confined to human-accepted windows; approval remains human.",
    }
    projects.atomic(folder / f"{render_id}.json", receipt)
    family = family_doc
    family["latest_render_id"] = render_id
    family["latest_render"] = {
        key: receipt[key]
        for key in (
            "id", "video", "master", "wav", "render_mode", "audio_sha256",
            "agent_fitting", "mix", "metrics", "human_approved", "warning",
        )
    }
    family["updated_at"] = time.time()
    projects.atomic(folder / "families" / f"{family_id}.json", family)
    obs.emit(pid, "candidate", {**receipt, "measurements": {"accepted_events": len(accepted)}})
    return receipt
