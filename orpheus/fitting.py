"""Per-event fitting with qualified source snippets and explicit temporal plans."""

import hashlib
import math
import subprocess
import uuid
import wave
import numpy as np
from .projects import media, ff, atomic

RATE = 48000
MAX_PLAN_ROWS = 100


def bounded(v, low, high, name):
    if (
        isinstance(v, bool)
        or not isinstance(v, (int, float))
        or not math.isfinite(v)
        or not low <= v <= high
    ):
        raise ValueError(f"{name} must be finite in [{low},{high}]")
    return v


def bank(case):
    source = media.read_audio(case["sfx_path"])
    events = media.detect(source, 6, 0.12)
    if not events:
        events = [{"time_s": float(np.argmax(np.abs(source))) / RATE}]
    rows = []
    for e in events:
        lo = max(0, int((e["time_s"] - 0.06) * RATE))
        hi = min(len(source), lo + int(0.45 * RATE))
        a = source[lo:hi]
        body = media.body_level(a)
        rows.append(
            {
                "id": len(rows),
                "peak_s": e["time_s"],
                "body_dbfs": round(body, 2),
                "crest_db": round(media.db(np.max(np.abs(a))) - body, 2),
            }
        )
    best = max(r["body_dbfs"] for r in rows)
    return [{**r, "usable": r["body_dbfs"] >= max(-50, best - 15)} for r in rows]


def candidates(case):
    a = media.read_audio(case["original_path"])
    # Low threshold retains quieter plausible events; model must review, not label all peaks.
    return media.detect(a, 6, 0.12)


def waveform_profile(case, center_s):
    """Numeric attack profile for review; never labels the action."""
    bounded(center_s, 0, case["seconds"] - 0.01, "center_s")
    a = media.read_audio(case["original_path"])
    lo = max(0, int((center_s - 0.15) * RATE))
    hi = min(len(a), int((center_s + 0.15) * RATE))
    x = a[lo:hi]
    hop = round(0.005 * RATE)
    bins = np.array(
        [np.sqrt(np.mean(x[i : i + hop] ** 2)) for i in range(0, len(x), hop)]
    )
    peaks = [
        {
            "time_s": round((lo + i * hop) / RATE, 6),
            "level_dbfs": round(media.db(bins[i]), 2),
        }
        for i in range(1, len(bins) - 1)
        if bins[i] >= bins[i - 1] and bins[i] > bins[i + 1]
    ]
    return {
        "center_s": center_s,
        "window_s": [max(0, center_s - 0.15), min(case["seconds"], center_s + 0.15)],
        "bin_ms": 5,
        "peaks": sorted(peaks, key=lambda p: p["level_dbfs"], reverse=True)[:8],
        "warning": "Acoustic peaks are not semantic ground truth.",
    }


def motion_evidence(case):
    """Small-frame change sensor, NOT an action classifier or contact detector."""
    raw = subprocess.check_output(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(case["video_path"]),
            "-an",
            "-vf",
            "fps=30,scale=128:72,format=gray",
            "-threads",
            "1",
            "-f",
            "rawvideo",
            "-",
        ],
        timeout=120,
    )
    pictures = np.frombuffer(raw, np.uint8).reshape(-1, 72, 128).astype(float)
    difference = np.abs(np.diff(pictures, axis=0))
    scores = np.mean(difference, axis=(1, 2))
    reference = max(float(np.percentile(scores, 90)), 0.1)
    rows = []
    for event in candidates(case):
        t = event["time_s"]
        lo = max(0, int((t - 0.15) * 30))
        hi = min(len(scores), int((t + 0.15) * 30) + 1)
        scores_here = scores[lo:hi]
        rows.append(
            {
                "audio_time_s": t,
                "audio_body_dbfs": event["body_dbfs"],
                "nearby_frame_change": round(float(np.max(scores_here)), 3)
                if len(scores_here)
                else 0,
                "motion_relative_to_p90": round(
                    float(np.max(scores_here)) / reference, 2
                )
                if len(scores_here)
                else 0,
            }
        )
    return {
        "method": "30fps mean absolute grayscale pixel change within ±150ms. Camera motion and lighting also count. NOT landing detection.",
        "audio_motion_candidates": rows,
        "frame_change_p90": round(reference, 3),
    }


def validate_plan(plan, case):
    if not isinstance(plan, list) or not 1 <= len(plan) <= MAX_PLAN_ROWS:
        raise ValueError(f"Provide 1..{MAX_PLAN_ROWS} event/interval rows")
    ids = {r["id"] for r in bank(case) if r["usable"]}
    for e in plan:
        if set(e) != {
            "time_s",
            "duration_s",
            "sample_id",
            "gain_db",
            "confidence",
            "evidence",
        }:
            raise ValueError(
                "Event fields: time_s,duration_s,sample_id,gain_db,confidence,evidence"
            )
        bounded(e["time_s"], 0, case["seconds"] - 0.01, "time_s")
        bounded(e["duration_s"], 0.12, 3, "duration_s")
        bounded(e["gain_db"], -8, 6, "gain_db")
        if type(e["sample_id"]) is not int or e["sample_id"] not in ids:
            raise ValueError("Use a qualified sample ID from inspect_scene")
        if e["confidence"] not in ("uncertain", "likely"):
            raise ValueError(
                "Confidence: uncertain or likely; never verified automatically"
            )
        if not isinstance(e["evidence"], str) or not 1 <= len(e["evidence"]) <= 400:
            raise ValueError("Short temporal evidence required")
    times = [e["time_s"] for e in plan]
    if times != sorted(times) or any(b - a < 0.05 for a, b in zip(times, times[1:])):
        raise ValueError("Sort events, at least 50ms apart")
    return plan


def render(case, plan, folder, target=-22, mode="balanced"):
    validate_plan(plan, case)
    bounded(target, -28, -16, "target")
    if mode not in ("balanced", "recorded"):
        raise ValueError("Invalid mode")
    source = media.read_audio(case["sfx_path"])
    rows = {r["id"]: r for r in bank(case)}
    out = np.zeros(round(case["seconds"] * RATE))
    parts = []
    metrics = []
    for e in plan:
        peak = round(rows[e["sample_id"]]["peak_s"] * RATE)
        lo = max(0, peak - round(0.06 * RATE))
        hi = min(len(source), lo + round(e["duration_s"] * RATE))
        a = source[lo:hi].copy()
        n = len(a)
        a *= np.maximum(
            0,
            np.minimum(
                1,
                np.minimum(
                    np.arange(n) / (RATE * 0.005),
                    (n - 1 - np.arange(n)) / (RATE * 0.015),
                ),
            ),
        )
        before = media.body_level(a)
        if before < -50:
            raise ValueError(
                "Chosen segment is too weak after trimming; choose another sample or longer duration"
            )
        boost = 0
        if mode == "balanced":
            body = 10 ** (before / 20)
            knee = body * 1.25
            mag = np.abs(a)
            # Strictly increasing compression retains peak ordering. A saturated tanh
            # plateau made the strongest decoded AAC peak drift to another equal peak.
            a = np.sign(a) * np.where(
                mag > knee, knee * np.power(mag / knee, 0.35), mag
            )
            boost = min(24, max(-30, target - media.body_level(a)))
            a *= 10 ** (boost / 20)
        a *= 10 ** (e["gain_db"] / 20)
        idx = int(np.argmax(np.abs(a)))
        start = round(e["time_s"] * RATE) - idx
        sl = max(0, -start)
        dest = max(start, 0)
        length = min(len(a) - sl, len(out) - dest)
        if length <= 0:
            raise ValueError("Event outside output")
        out[dest : dest + length] += a[sl : sl + length]
        body = media.body_level(a[sl : sl + length])
        metrics.append(
            {
                "time_s": e["time_s"],
                "sample_id": e["sample_id"],
                "body_dbfs": body,
                "crest_db": media.db(np.max(np.abs(a))) - media.body_level(a),
                "normalisation_db": boost,
                "truncated": length < len(a),
                "output_start_s": dest / RATE,
                "output_end_s": (dest + length) / RATE,
            }
        )
        parts.append({"scheduled_peak_s": e["time_s"]})
    attenuation = min(0, -3 - media.db(np.max(np.abs(out))))
    out *= 10 ** (attenuation / 20)
    rid = uuid.uuid4().hex[:12]
    wav = folder / (rid + ".wav")
    video = folder / (rid + ".mp4")
    for retry in range(3):
        with wave.open(str(wav), "wb") as w:
            w.setparams((1, 2, RATE, len(out), "NONE", "not compressed"))
            w.writeframes(np.round(out * 32767).astype("<i2").tobytes())
        ff(
            "-i",
            case["video_path"],
            "-i",
            wav,
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-t",
            case["seconds"],
            "-movflags",
            "+faststart",
            video,
        )
        encoded = media.measure_export(video)
        if encoded["true_peak_dbtp"] <= -1:
            break
        adjustment = -1.5 - encoded["true_peak_dbtp"]
        out *= 10 ** (adjustment / 20)
        attenuation += adjustment
    else:
        raise ValueError("Encoded true peak protection failed")
    for m in metrics:
        m["body_dbfs"] = round(m["body_dbfs"] + attenuation, 2)
    decoded = np.frombuffer(
        subprocess.check_output(
            [
                "ffmpeg",
                "-v",
                "error",
                "-i",
                str(video),
                "-vn",
                "-ar",
                "48000",
                "-ac",
                "1",
                "-f",
                "f32le",
                "-",
            ],
            timeout=120,
        ),
        dtype="<f4",
    )
    for m in metrics:
        window = decoded[
            round(m["output_start_s"] * RATE) : round(m["output_end_s"] * RATE)
        ]
        m["decoded_window_body_dbfs"] = round(media.body_level(window), 2)
        m["decoded_window_peak_dbfs"] = round(media.db(np.max(np.abs(window))), 2)
        m["decoded_window_note"] = (
            "Includes any overlapping events; body_dbfs is the isolated pre-AAC event body."
        )
    levels = [m["body_dbfs"] for m in metrics]
    crest = max(m["crest_db"] for m in metrics)
    timing = media.encoded_timing(video, parts)
    for m, t in zip(metrics, timing["events"]):
        m["decoded_peak_s"] = t["measured_peak_s"]
        m["decoded_peak_error_ms"] = t["peak_error_ms"]
    flags = []
    if min(levels) < -30:
        flags.append("weak_event_body")
    if max(levels) - min(levels) > 8:
        flags.append("uneven_event_bodies")
    if crest > 18:
        flags.append("sharp_transients")
    if encoded["integrated_lufs"] < -30:
        flags.append("quiet_mix")
    if encoded["integrated_lufs"] > -16:
        flags.append("loud_mix")
    if any(m["truncated"] for m in metrics):
        flags.append("truncated_event")
    if timing["max_abs_peak_error_ms"] is None or timing["max_abs_peak_error_ms"] > 25:
        flags.append("encoded_peak_shift")
    clipped = int(np.sum(np.abs(decoded) >= 1))
    if clipped:
        flags.append("decoded_clipping")
    picture = media.picture_hash(video) == media.picture_hash(case["video_path"])
    if not picture:
        raise ValueError("Picture preservation failed")
    receipt = {
        "id": rid,
        "video": video.name,
        "wav": wav.name,
        "plan": plan,
        "target": target,
        "mode": mode,
        "audio_sha256": hashlib.sha256(wav.read_bytes()).hexdigest(),
        "metrics": {
            **encoded,
            "body_spread_db": round(max(levels) - min(levels), 2),
            "min_body_dbfs": min(levels),
            "max_crest_db": round(crest, 2),
            "event_count": len(plan),
            "picture_unchanged": picture,
            "clipped_samples": clipped,
            "encoded_peak_error_ms": timing["max_abs_peak_error_ms"],
        },
        "event_metrics": metrics,
        "flags": flags,
        "engineering_pass": not flags,
        "warning": "Complete soundtrack replacement. Model cannot listen. Event plan is a fallible visual/audio hypothesis, not verified truth.",
    }
    atomic(folder / (rid + ".json"), receipt)
    return receipt
