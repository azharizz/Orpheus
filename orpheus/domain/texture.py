"""Continuous source intervals; no transient peak alignment or hidden time stretch."""

import hashlib
import subprocess
import uuid
import wave

import numpy as np

from . import media
from .fitting import RATE, bounded
from .projects import atomic, ff


def assemble(source, duration_s, crossfade_s, repeat):
    bounded(duration_s, 0.12, 30, "duration_s")
    bounded(crossfade_s, 0.01, 0.5, "crossfade_s")
    if type(repeat) is not bool:
        raise ValueError("repeat must be boolean")
    if not len(source) or not np.all(np.isfinite(source)):
        raise ValueError("Invalid source")
    count = round(duration_s * RATE)
    fade = round(crossfade_s * RATE)
    if 2 * fade >= len(source):
        raise ValueError("Source must exceed twice the crossfade length")
    if count > len(source) and not repeat:
        raise ValueError(
            "Source is shorter than target; choose another range or explicitly enable repeat"
        )
    out = source[:count].copy()
    seams = []
    while len(out) < count:
        start = len(out) - fade
        ramp = np.linspace(0, 1, fade)
        out[-fade:] = out[-fade:] * (1 - ramp) + source[:fade] * ramp
        out = np.concatenate((out, source[fade:]))
        seams.append(start / RATE)
    return out[:count], seams


def render(
    case,
    folder,
    start_s,
    end_s,
    source_start_s,
    source_end_s,
    target_body_dbfs,
    repeat,
    crossfade_s,
):
    bounded(start_s, 0, case["seconds"] - 0.12, "start_s")
    bounded(end_s, start_s + 0.12, case["seconds"], "end_s")
    bounded(target_body_dbfs, -28, -16, "target_body_dbfs")
    source = media.read_audio(case["sfx_path"])
    source_seconds = len(source) / RATE
    bounded(source_start_s, 0, source_seconds - 0.12, "source_start_s")
    bounded(source_end_s, source_start_s + 0.12, source_seconds, "source_end_s")
    segment = source[round(source_start_s * RATE) : round(source_end_s * RATE)]
    body = media.body_level(segment)
    if body < -50:
        raise ValueError("Chosen source region too weak")
    bed, seams = assemble(segment, end_s - start_s, crossfade_s, repeat)
    gain = min(24, max(-30, target_body_dbfs - media.body_level(bed)))
    bed *= 10 ** (gain / 20)
    edge = min(round(0.01 * RATE), len(bed) // 2)
    bed[:edge] *= np.linspace(0, 1, edge)
    bed[-edge:] *= np.linspace(1, 0, edge)
    out = np.zeros(round(case["seconds"] * RATE))
    start = round(start_s * RATE)
    out[start : start + len(bed)] = bed
    attenuation = min(0, -3 - media.db(np.max(np.abs(out))))
    out *= 10 ** (attenuation / 20)
    rid = uuid.uuid4().hex[:12]
    wav = folder / (rid + ".wav")
    video = folder / (rid + ".mp4")
    for attempt in range(3):
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
        raise ValueError("Encoded peak protection failed")
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
                str(RATE),
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
    active = decoded[start : start + len(bed)]
    # Fixed 20ms RMS windows: gaps are measured, not inferred from placement metadata.
    windows = [
        active[i : i + 960]
        for i in range(0, len(active), 960)
        if len(active[i : i + 960]) == 960
    ]
    levels = np.array([media.db(np.sqrt(np.mean(w * w))) for w in windows])
    floor = max(-60, float(np.percentile(levels, 90)) - 30)
    quiet = levels < floor
    longest = run = 0
    for q in quiet:
        run = run + 1 if q else 0
        longest = max(longest, run)
    picture = media.picture_hash(video) == media.picture_hash(case["video_path"])
    if not picture:
        raise ValueError("Picture preservation failed")
    clipped = int(np.sum(np.abs(decoded) >= 1))
    flags = []
    if clipped:
        flags.append("decoded_clipping")
    if longest * 0.02 > 0.1:
        flags.append("texture_dropout")
    if encoded["integrated_lufs"] < -30:
        flags.append("quiet_mix")
    if encoded["integrated_lufs"] > -16:
        flags.append("loud_mix")
    seam_levels = []
    for t in seams:
        i = round(t * RATE)
        a = active[max(0, i - 4800) : i]
        b = active[i : min(len(active), i + 4800)]
        if len(a) and len(b):
            seam_levels.append(
                abs(
                    media.db(np.sqrt(np.mean(a * a)))
                    - media.db(np.sqrt(np.mean(b * b)))
                )
            )
    seam_delta = max(seam_levels, default=0)
    if seam_delta > 6:
        flags.append("texture_seam_level_change")
    receipt = {
        "id": rid,
        "video": video.name,
        "wav": wav.name,
        "render_mode": "texture",
        "plan": [
            {
                "time_s": start_s,
                "duration_s": end_s - start_s,
                "sample_id": "source interval",
                "gain_db": round(gain + attenuation, 2),
                "confidence": "uncertain",
                "evidence": f"Continuous source {source_start_s:.3f}–{source_end_s:.3f}s, repeat={repeat}, crossfade={crossfade_s}s. Start-anchored, not contact timing.",
            }
        ],
        "source_interval_s": [source_start_s, source_end_s],
        "target_interval_s": [start_s, end_s],
        "repeat": repeat,
        "crossfade_s": crossfade_s,
        "seams_s": [round(start_s + t, 6) for t in seams],
        "audio_sha256": hashlib.sha256(wav.read_bytes()).hexdigest(),
        "metrics": {
            **encoded,
            "picture_unchanged": picture,
            "clipped_samples": clipped,
            "interval_duration_s": end_s - start_s,
            "uncovered_timeline_s": round(case["seconds"] - (end_s - start_s), 6),
            "max_dropout_s": round(longest * 0.02, 3),
            "active_window_coverage_pct": round(100 * float(np.mean(~quiet)), 2),
            "max_seam_level_change_db": round(seam_delta, 2),
        },
        "event_metrics": [],
        "flags": flags,
        "engineering_pass": not flags,
        "warning": "Whole soundtrack replaced. Crossfaded repetition can repeat mechanical cycles or alter timbre. Coverage is not action sync; model cannot listen. No denoising or non-target preservation.",
    }
    atomic(folder / (rid + ".json"), receipt)
    return receipt
