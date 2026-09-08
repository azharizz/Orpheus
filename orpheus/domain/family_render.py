"""Stream reviewed sound-family events into a full-duration mix."""

import math
import wave

import numpy as np

from ..config import SAMPLE_RATE as RATE


def _source(replacement, row, default_gain_db, families):
    if not row:
        peak = int(np.argmax(np.abs(replacement)))
        start = max(0, peak - round(families.PRE_ONSET_S * RATE))
        return (
            replacement[start : start + round(families.WINDOW_S * RATE)].copy()
            * 10 ** (default_gain_db / 20),
            peak - start,
        )
    start, end = (round(families._finite(x, "source range") * RATE) for x in row["source_range_s"])
    anchor = round(families._finite(row["source_anchor_s"], "source anchor") * RATE)
    if not 0 <= start < anchor < end <= len(replacement):
        raise ValueError("Learned source range outside replacement take")
    return (
        replacement[start:end].copy() * 10 ** ((default_gain_db + float(row.get("gain_db", 0))) / 20),
        anchor - start,
    )


def _events(original_path, replacement, matches, ramp_s, gain_db, variants, timeline_offset_s, families):
    frames, _ = families._wav_shape(original_path)
    duration = frames / RATE
    learned = [r for r in variants or [] if r.get("disposition") == "use" and r.get("kind") == "impact"]
    events, dialogue = [], []

    def add(item, row=None, target_range=None, target_anchor=None):
        start_s, end_s = families._range(target_range or item["range_s"], duration, "match range")
        anchor_s = families._finite(target_anchor if target_anchor is not None else item["refined_anchor_s"], "refined anchor")
        if not start_s <= anchor_s <= end_s:
            raise ValueError("Refined anchor outside match")
        part, source_anchor = _source(replacement, row, gain_db, families)
        start, end = round(start_s * RATE), round(end_s * RATE)
        destination = round(anchor_s * RATE) - source_anchor
        skip = max(0, -destination)
        destination = max(0, destination)
        count = min(len(part) - skip, end - destination, frames - destination)
        if count < 1:
            raise ValueError("Replacement falls outside accepted match")
        events.append({
            "id": item["id"], "start": start, "end": end, "destination": destination,
            "source_skip": skip, "count": count,
            "ramp": min(round(ramp_s * RATE), (end - start) // 2, count // 2), "part": part,
        })
        if families._possible_dialogue_or_music(families._read_range(original_path, start, end - start)):
            dialogue.append(item["id"])

    ordered = sorted(matches, key=lambda item: item["refined_anchor_s"])
    cycle = 0
    for item in ordered:
        if learned and item.get("kind") == "example":
            for row in learned:
                add(
                    item, row,
                    [timeline_offset_s + x for x in row["target_range_s"]],
                    timeline_offset_s + row["target_anchor_s"],
                )
        else:
            add(item, learned[cycle % len(learned)] if learned else None)
            cycle += 1
    return events, dialogue, len(learned)


def _components(original, offset, events, duck_db):
    stop = offset + len(original)
    envelope = np.ones(len(original), dtype=np.float32)
    layer = np.zeros_like(original, dtype=np.float32)
    floor = 10 ** (duck_db / 20)
    for event in events:
        left, right = max(offset, event["start"]), min(stop, event["end"])
        if left < right:
            length = event["end"] - event["start"]
            curve = np.full(length, floor, dtype=np.float32)
            ramp = event["ramp"]
            if ramp:
                curve[:ramp] = np.linspace(1, floor, ramp, endpoint=False)
                curve[-ramp:] = np.linspace(floor, 1, ramp, endpoint=False)
            a, b, c = left - offset, right - offset, left - event["start"]
            envelope[a:b] = np.minimum(envelope[a:b], curve[c : c + b - a])
        left = max(offset, event["destination"])
        right = min(stop, event["destination"] + event["count"])
        if left >= right:
            continue
        source = event["source_skip"] + left - event["destination"]
        placed = event["part"][source : source + right - left].copy()
        positions = np.arange(left - event["destination"], right - event["destination"])
        if event["ramp"]:
            placed *= np.minimum(1, np.minimum(positions / event["ramp"], (event["count"] - 1 - positions) / event["ramp"]))
        a, b = left - offset, right - offset
        layer[a:b] += placed[:, None] if original.ndim == 2 else placed
    return original * (envelope[:, None] if original.ndim == 2 else envelope), layer


def write_selective_wav(original_path, output_path, replacement, matches, duck_db, ramp_s, gain_db, *, variants=None, timeline_offset_s=0, on_progress=None):
    from . import families

    frames, channels = families._wav_shape(original_path)
    events, dialogue, variant_count = _events(
        original_path, replacement, matches, ramp_s, gain_db, variants, timeline_offset_s, families
    )
    def report(phase, percent, message):
        if on_progress:
            on_progress(phase, percent, message)

    scale = 1.0
    report("headroom", 5, "Checking replacement headroom")
    for offset, original in families._pcm_chunks(original_path):
        ducked, layer = _components(original, offset, events, duck_db)
        positive, negative = layer > 1e-9, layer < -1e-9
        if np.any(positive):
            scale = min(scale, float(np.min((0.999 - ducked[positive]) / layer[positive])))
        if np.any(negative):
            scale = min(scale, float(np.min((-0.999 - ducked[negative]) / layer[negative])))
        report("headroom", 5 + 43 * (offset + len(original)) / frames, "Checking replacement headroom")
    scale = min(1.0, max(0.0, scale))
    peak = 0.0
    report("mixing", 48, "Writing the selective replacement mix")
    with wave.open(str(output_path), "wb") as output:
        output.setparams((channels, 2, RATE, frames, "NONE", "not compressed"))
        for offset, original in families._pcm_chunks(original_path):
            ducked, layer = _components(original, offset, events, duck_db)
            mixed = ducked + layer * scale
            peak = max(peak, float(np.max(np.abs(mixed))))
            output.writeframes(np.clip(np.round(mixed * 32768), -32768, 32767).astype("<i2").tobytes())
            report("mixing", 48 + 34 * (offset + len(original)) / frames, "Writing the selective replacement mix")
    if peak >= 1:
        output_path.unlink(missing_ok=True)
        raise ValueError("Replacement mix clips; lower the replacement gain")
    return {
        "duck_db": duck_db, "ramp_s": ramp_s, "replacement_gain_db": gain_db,
        "replacement_peak_protection_db": round(20 * math.log10(max(scale, 1e-9)), 3),
        "ranges_s": [[e["start"] / RATE, e["end"] / RATE] for e in events],
        "learned_source_variants": variant_count,
        "possible_dialogue_or_music_overlap_ids": dialogue,
        "warning": "Only accepted windows were ducked; approved agent source crops were reused without time stretching.",
    }
