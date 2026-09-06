#!/usr/bin/env python3
"""Score Orpheus query-by-example matching against reviewed event anchors."""

import argparse
import json
import shutil
import tempfile
import wave
from pathlib import Path

import numpy as np

from orpheus.domain import families


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("audio", type=Path, help="48 kHz mono/stereo PCM16 WAV")
    parser.add_argument("annotations", type=Path, help="JSON with contacts[].time_s")
    parser.add_argument("--seed", type=int, default=0, help="contact index used as query")
    parser.add_argument("--tolerance", type=float, default=0.1)
    args = parser.parse_args()
    reviewed = json.loads(args.annotations.read_text())["contacts"]
    truth = [float(item["time_s"]) for item in reviewed]
    interval = reviewed[args.seed].get("review_interval_s")
    seed = interval or [truth[args.seed] - 0.05, truth[args.seed] + 0.05]
    with wave.open(str(args.audio), "rb") as source:
        seconds = source.getnframes() / source.getframerate()
    with tempfile.TemporaryDirectory(prefix="orpheus-benchmark-") as tmp:
        folder = Path(tmp)
        shutil.copyfile(args.audio, folder / "original.wav")
        original_dir, original_load = families.project_dir, families.load
        families.project_dir = lambda _pid: folder
        families.load = lambda _pid: {
            "id": "0" * 16,
            "seconds": seconds,
            "original_path": folder / "original.wav",
        }
        try:
            family = families.create("0" * 16, "reviewed event", seed)
            found = [family["accepted_ranges"][0]["refined_anchor_s"]] + [
                item["refined_anchor_s"] for item in family["pending_matches"]
            ]
            true_positives = sum(
                any(abs(value - target) <= args.tolerance for target in truth)
                for value in found
            )
            errors = [min(abs(value - target) for value in found) for target in truth]
            precision = true_positives / len(found)
            recall = sum(error <= args.tolerance for error in errors) / len(truth)
            f2 = 5 * precision * recall / (4 * precision + recall)
            index_bytes = sum(
                path.stat().st_size for path in (folder / "similarity").glob("*.npy")
            )
        finally:
            families.project_dir, families.load = original_dir, original_load
    print(json.dumps({
        "method": families.INDEX_CONFIG["feature"],
        "annotations": len(truth),
        "queue_size_including_seed": len(found),
        "precision": precision,
        "recall": recall,
        "f2": f2,
        "median_onset_error_s": float(np.median(errors)),
        "index_bytes": index_bytes,
        "qualified": precision >= 0.75 and recall >= 0.9
        and float(np.median(errors)) <= 0.1,
    }, indent=2))


if __name__ == "__main__":
    main()
