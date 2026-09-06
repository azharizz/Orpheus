"""PCM analysis and encoded-export measurement primitives."""

import math
import re
import struct
import subprocess
import wave

import numpy as np

from ..config import SAMPLE_RATE as RATE


def read_audio(path):
    with wave.open(str(path), "rb") as w:
        if (w.getframerate(), w.getnchannels(), w.getsampwidth()) != (RATE, 1, 2):
            raise ValueError("Expected 48kHz mono PCM16 WAV")
        return (
            np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(float)
            / 32768
        )


def db(x):
    return float(20 * np.log10(max(float(x), 1e-09)))


def envelope(samples):
    hop = RATE // 100
    padded = np.pad(samples, (0, -len(samples) % hop))
    return np.sqrt(np.mean(padded.reshape(-1, hop) ** 2, axis=1))


def body_level(samples):
    n = min(len(samples), RATE // 10)
    if n < 1:
        return -180.0
    energy = np.r_[0.0, np.cumsum(samples**2)]
    return db(np.sqrt(np.max(energy[n:] - energy[:-n]) / n))


def detect(samples, sensitivity_db=12.0, min_gap_s=0.25):
    if not 4 <= sensitivity_db <= 30 or not 0.06 <= min_gap_s <= 1.0:
        raise ValueError("Detector bounds exceeded")
    env = envelope(samples)
    if not len(env) or np.max(env) < 1e-07:
        return []
    floor = max(np.percentile(env, 20), 1e-07)
    threshold = max(floor * 10 ** (sensitivity_db / 20), np.max(env) * 10 ** (-30 / 20))
    peaks = [
        i
        for i in range(len(env))
        if env[i] >= threshold
        and env[i] >= (env[i - 1] if i else -1)
        and (env[i] > (env[i + 1] if i + 1 < len(env) else -1))
    ]
    chosen = []
    for i in sorted(peaks, key=lambda i: float(env[i]), reverse=True):
        if all(abs(i - j) * 0.01 >= min_gap_s for j in chosen):
            chosen.append(i)
    events = []
    for i in sorted(chosen):
        lo = max(0, int((i * 0.01 - 0.01) * RATE))
        hi = min(len(samples), int((i * 0.01 + 0.02) * RATE))
        peak = lo + int(np.argmax(np.abs(samples[lo:hi])))
        events.append(
            {
                "id": len(events) + 1,
                "time_s": round(peak / RATE, 6),
                "body_dbfs": round(db(env[i]), 2),
                "origin": "audio energy candidate; NOT visual/semantic ground truth",
            }
        )
    return events[:180]


def analyse(path):
    a = read_audio(path)
    env = envelope(a)
    bins = np.array_split(env, min(120, len(env)))
    return {
        "duration_s": round(len(a) / RATE, 6),
        "rms_dbfs": round(db(np.sqrt(np.mean(a * a))), 2),
        "peak_dbfs": round(db(np.max(np.abs(a))), 2),
        "body_dbfs": round(body_level(a), 2),
        "clipped_samples": int(np.sum(np.abs(a) >= 32760 / 32768)),
        "energy_floor_p20_dbfs": round(db(np.percentile(env, 20)), 2),
        "full_window_envelope_dbfs": [round(db(np.max(x)), 1) for x in bins],
        "bin_duration_s": round(len(a) / RATE / len(bins), 4),
        "candidate_counts": [
            {"sensitivity_db": s, "gap_s": g, "count": len(detect(a, s, g))}
            for s, g in [(8, 0.12), (12, 0.25), (18, 0.4)]
        ],
        "limitations": [
            "Energy-floor statistic is not isolated background noise.",
            "No semantic or visual interpretation.",
        ],
    }


def picture_hash(path):
    return subprocess.check_output(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-map",
            "0:v:0",
            "-an",
            "-f",
            "hash",
            "-hash",
            "sha256",
            "-",
        ],
        timeout=180,
        text=True,
    ).strip()


def measure_export(path):
    proc = subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-nostats",
            "-i",
            str(path),
            "-vn",
            "-af",
            "ebur128=peak=true",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=45,
    )
    summary = proc.stderr.rsplit("Summary:", 1)[-1]

    def metric(pattern):
        match = re.search(pattern, summary)
        if not match:
            raise ValueError("Could not measure encoded audio")
        value = float(match.group(1))
        if not math.isfinite(value):
            raise ValueError("Encoded audio measurement is not finite")
        return value

    return {
        "integrated_lufs": metric("I:\\s+(-?[\\d.]+) LUFS"),
        "true_peak_dbtp": metric("Peak:\\s+(-?[\\d.]+) dBFS"),
        "method": "FFmpeg EBU R128 / oversampled true peak of decoded exported AAC; not a listening test.",
    }


def encoded_timing(path, placements):
    raw = subprocess.check_output(
        [
            "ffmpeg",
            "-v",
            "error",
            "-i",
            str(path),
            "-vn",
            "-ar",
            str(RATE),
            "-ac",
            "1",
            "-f",
            "f32le",
            "-",
        ],
        timeout=45,
    )
    pcm = struct.unpack(f"<{len(raw) // 4}f", raw)
    rows = []
    for i, p in enumerate(placements):
        target = p["scheduled_peak_s"]
        lo = max(
            0,
            target - 0.1,
            (placements[i - 1]["scheduled_peak_s"] + target) / 2 if i else 0,
        )
        hi = min(
            len(pcm) / RATE,
            target + 0.1,
            (placements[i + 1]["scheduled_peak_s"] + target) / 2
            if i + 1 < len(placements)
            else len(pcm) / RATE,
        )
        start, end = (round(lo * RATE), round(hi * RATE))
        if end <= start:
            rows.append(
                {"contact": i + 1, "measured_peak_s": None, "peak_error_ms": None}
            )
            continue
        peak = max(range(start, end), key=lambda j: abs(pcm[j]))
        rows.append(
            {
                "contact": i + 1,
                "measured_peak_s": round(peak / RATE, 6),
                "peak_error_ms": round((peak / RATE - target) * 1000, 3),
            }
        )
    errors = [abs(r["peak_error_ms"]) for r in rows if r["peak_error_ms"] is not None]
    return {
        "events": rows,
        "max_abs_peak_error_ms": max(errors) if errors else None,
        "method": "Strongest decoded AAC sample within ±100ms of scheduled impact, bounded by neighboring midpoints. Checks encoded peak timing, not visual contact accuracy or onset perception; blend may detect original audio.",
    }
