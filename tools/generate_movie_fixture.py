#!/usr/bin/env python3
"""Generate a deterministic long-form picture, soundtrack, SFX takes and truth."""

import argparse
import json
import math
import subprocess
import wave
from pathlib import Path

import numpy as np

RATE = 48_000


def pulse(t, at, frequency, decay, gain):
    age = t - at
    active = (age >= 0) & (age < decay)
    return active * gain * np.sin(2 * np.pi * frequency * age) * np.exp(-age * 12 / decay)


def write_pcm(path, duration, render):
    with wave.open(str(path), "wb") as output:
        output.setparams((1, 2, RATE, round(duration * RATE), "NONE", "not compressed"))
        for second in range(math.ceil(duration)):
            count = min(RATE, round(duration * RATE) - second * RATE)
            t = second + np.arange(count, dtype=np.float64) / RATE
            samples = np.clip(render(t), -0.95, 0.95)
            output.writeframes(np.round(samples * 32767).astype("<i2").tobytes())


def generate(folder, duration):
    folder.mkdir(parents=True, exist_ok=True)
    thirds = [0, duration / 3, duration * 2 / 3, duration]
    grass = np.arange(2, thirds[1], 1.4)
    hard = np.arange(thirds[1] + 1, thirds[2], 1.05)
    cloth = np.arange(thirds[2] + .5, duration - 1, 2.2)
    doors = np.arange(max(8, duration * .12), duration, max(30, duration / 10))
    noise_ranges = [[round(duration * .28, 3), round(duration * .28 + min(12, duration * .04), 3)], [round(duration * .72, 3), round(duration * .72 + min(18, duration * .05), 3)]]
    voice_ranges = [[round(duration * .44, 3), round(duration * .44 + min(20, duration * .06), 3)]]

    def soundtrack(t):
        data = .008 * np.sin(2 * np.pi * 73 * t)
        for at in grass[(grass >= t[0] - .3) & (grass <= t[-1] + .3)]:
            data += pulse(t, at, 170, .22, .22)
        for at in hard[(hard >= t[0] - .3) & (hard <= t[-1] + .3)]:
            data += pulse(t, at, 520, .13, .28)
        for at in cloth[(cloth >= t[0] - .3) & (cloth <= t[-1] + .3)]:
            data += pulse(t, at, 1850, .18, .12)
        for at in doors[(doors >= t[0] - .5) & (doors <= t[-1] + .5)]:
            data += pulse(t, at, 85, .48, .38)
        for start, end in noise_ranges:
            active = (t >= start) & (t < end)
            # Deterministic broadband-like hum; enough crest stability for noise review.
            data += active * (.045 * np.sin(2 * np.pi * 997 * t) + .035 * np.sin(2 * np.pi * 1231 * t))
        for start, end in voice_ranges:
            active = (t >= start) & (t < end)
            data += active * .035 * (np.sin(2 * np.pi * 180 * t) + .6 * np.sin(2 * np.pi * 360 * t))
        return data

    audio = folder / "synthetic-30-minute.wav"
    write_pcm(audio, duration, soundtrack)
    replacements = {
        "grass-step.wav": lambda t: pulse(t, 0.08, 145, .3, .34),
        "hard-step.wav": lambda t: pulse(t, 0.08, 610, .18, .3),
        "cloth.wav": lambda t: pulse(t, 0.08, 2200, .22, .18),
        "door.wav": lambda t: pulse(t, 0.08, 72, .55, .42),
    }
    for name, render in replacements.items():
        write_pcm(folder / name, 1.0, render)
    picture = folder / "synthetic-30-minute.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-nostdin", "-y",
        "-f", "lavfi", "-i", f"testsrc2=size=480x270:rate=12:duration={duration}",
        "-i", str(audio), "-map", "0:v:0", "-map", "1:a:0",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "29",
        "-g", "48", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart", "-shortest", str(picture),
    ], check=True, timeout=max(300, duration * 2))
    truth = {
        "schema": "orpheus-synthetic-movie.v1",
        "duration_s": duration,
        "picture": picture.name,
        "soundtrack": audio.name,
        "sections": [
            {"range_s": [0, thirds[1]], "family": "grass_steps", "events_s": grass.round(3).tolist()},
            {"range_s": [thirds[1], thirds[2]], "family": "hard_floor_steps", "events_s": hard.round(3).tolist()},
            {"range_s": [thirds[2], duration], "family": "cloth_props", "events_s": cloth.round(3).tolist()},
        ],
        "door_events_s": doors.round(3).tolist(),
        "noise_ranges_s": noise_ranges,
        "voice_like_ranges_s": voice_ranges,
        "replacement_sfx": list(replacements),
        "rights": "Deterministically generated test signals and FFmpeg test pattern; no third-party media.",
    }
    (folder / "ground-truth.json").write_text(json.dumps(truth, indent=2))
    return truth


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=float, default=1800)
    parser.add_argument("--output", type=Path, default=Path("data/fixtures/synthetic-30-minute"))
    args = parser.parse_args()
    if not 10 <= args.duration <= 7200:
        parser.error("duration must be 10..7200 seconds")
    print(json.dumps(generate(args.output, args.duration), indent=2))
