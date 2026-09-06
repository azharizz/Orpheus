"""Versioned, evidence-backed target/source arrangement validation.

This is deliberately a small contract layer: it prevents invented correspondence
before the existing renderers are called. It does not decide whether a sound is
artistically correct.
"""

from __future__ import annotations
import math
import hashlib
import json
import uuid
import wave
import subprocess
import numpy as np
from .projects import media, atomic, ff
from .texture import assemble as repeat_audio

RATE = 48000
MAX_ROWS = 100
MAX_SOURCE_OPTIONS = 24

SCHEMA = "arrangement.v1"
KINDS = {"impact", "texture", "composite", "pause"}
ANCHORS = {"start", "contact", "transition"}
DISPOSITIONS = {"use", "omit", "unmatched"}


def _finite(v, label):
    if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
        raise ValueError(f"{label} must be finite")
    return float(v)


def validate(
    rows,
    *,
    target_duration_s,
    source_duration_s,
    target_ids=None,
    source_ids=None,
    require_impact_anchors=False,
):
    """Validate explicit mappings; return sorted canonical rows.

    IDs/ranges are mandatory for used mappings. Omitted and unmatched rows are
    allowed so the agent can represent intentional gaps instead of fabricating SFX.
    """
    if not isinstance(rows, list) or len(rows) > MAX_ROWS:
        raise ValueError(f"arrangement must contain 0..{MAX_ROWS} rows")
    _finite(target_duration_s, "target duration")
    _finite(source_duration_s, "source duration")
    target_ids = set(target_ids or ())
    source_ids = set(source_ids or ())
    out = []
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("arrangement rows must be objects")
        required = {
            "id",
            "target_id",
            "source_id",
            "target_range_s",
            "source_range_s",
            "kind",
            "anchor",
            "disposition",
            "confidence",
            "evidence",
        }
        optional = {
            "schema",
            "target_anchor_s",
            "source_anchor_s",
            "gain_db",
            "fade_in_s",
            "fade_out_s",
            "repeat",
            "crossfade_s",
            "reuse_reason",
            "after",
            "shape",
            "target_body_dbfs",
        }
        if not required <= set(row) or set(row) - required - optional:
            raise ValueError("arrangement row schema mismatch")
        if row.get("schema", SCHEMA) != SCHEMA:
            raise ValueError("Unsupported arrangement schema")
        if (
            row["kind"] not in KINDS
            or row["anchor"] not in ANCHORS
            or row["disposition"] not in DISPOSITIONS
        ):
            raise ValueError("invalid kind, anchor, or disposition")
        if (
            require_impact_anchors
            and row["kind"] == "impact"
            and row["disposition"] == "use"
            and (
                row["anchor"] != "contact"
                or not {"target_anchor_s", "source_anchor_s"} <= set(row)
            )
        ):
            raise ValueError(
                "Used impact requires explicit contact and source landmarks"
            )
        if row["confidence"] not in ("uncertain", "likely"):
            raise ValueError("confidence must remain uncertain or likely")
        if not isinstance(row["evidence"], str) or not 1 <= len(row["evidence"]) <= 500:
            raise ValueError("evidence must be 1..500 chars")
        if not isinstance(row["id"], str) or not row["id"]:
            raise ValueError("row id required")
        if any(not isinstance(row[k], str) for k in ("target_id", "source_id")):
            raise ValueError("Inventory IDs must be strings")
        tr, sr = row["target_range_s"], row["source_range_s"]
        if (
            not isinstance(tr, list)
            or len(tr) != 2
            or not isinstance(sr, list)
            or len(sr) != 2
        ):
            raise ValueError("ranges must be [start,end]")
        ta, tb = (_finite(x, "target range") for x in tr)
        sa, sb = (_finite(x, "source range") for x in sr)
        if not (
            0 <= ta <= tb <= target_duration_s and 0 <= sa <= sb <= source_duration_s
        ):
            raise ValueError("mapping range outside media")
        if row["disposition"] == "use":
            if row["target_id"] not in target_ids or row["source_id"] not in source_ids:
                raise ValueError("used mapping must cite known target and source IDs")
            if tb - ta < 0.02 or sb - sa < 0.02 or row["kind"] == "pause":
                raise ValueError(
                    "Used sounds need positive >=20ms ranges; pause is omit"
                )
        elif row["target_id"] not in target_ids:
            raise ValueError("Omitted/unmatched requirements need a known target ID")
        r = {
            **row,
            "target_range_s": [ta, tb],
            "source_range_s": [sa, sb],
            "schema": SCHEMA,
            "target_anchor_s": row.get("target_anchor_s", ta),
            "source_anchor_s": row.get("source_anchor_s", sa),
            "gain_db": row.get("gain_db", 0),
            "fade_in_s": row.get("fade_in_s", 0.005),
            "fade_out_s": row.get("fade_out_s", 0.015),
            "repeat": row.get("repeat", False),
            "crossfade_s": row.get("crossfade_s", 0.03),
            "reuse_reason": row.get("reuse_reason", ""),
            "after": row.get("after", []),
            "shape": row.get("shape", "recorded"),
        }
        for k, lo, hi in [
            ("target_anchor_s", ta, tb),
            ("source_anchor_s", sa, sb),
            ("gain_db", -30, 24),
            ("fade_in_s", 0, 0.5),
            ("fade_out_s", 0, 0.5),
            ("crossfade_s", 0.01, 0.5),
        ]:
            if not lo <= _finite(r[k], k) <= hi:
                raise ValueError(k + " outside bounds")
        if type(r["repeat"]) is not bool or r["shape"] not in ("recorded", "soften"):
            raise ValueError("Invalid repeat or shape")
        if (
            r.get("target_body_dbfs") is not None
            and not -32 <= _finite(r["target_body_dbfs"], "target_body_dbfs") <= -14
        ):
            raise ValueError("target_body_dbfs outside bounds")
        if not isinstance(r["after"], list) or any(
            not isinstance(x, str) for x in r["after"]
        ):
            raise ValueError("after must list mapping IDs")
        if not isinstance(r["reuse_reason"], str) or len(r["reuse_reason"]) > 500:
            raise ValueError("reuse_reason <=500 characters")
        if r["anchor"] == "start" and (
            r["target_anchor_s"] != ta or r["source_anchor_s"] != sa
        ):
            raise ValueError("Start anchor must equal range starts")
        out.append(r)
    used = [r for r in out if r["disposition"] == "use"]
    if any(
        used[i]["target_range_s"][0] > used[i + 1]["target_range_s"][0]
        for i in range(len(used) - 1)
    ):
        raise ValueError("used mappings must preserve target order")
    by_id = {r["id"]: r for r in out}
    if len(by_id) != len(out):
        raise ValueError("Duplicate mapping IDs")
    seen = set()
    for r in out:
        for parent in r["after"]:
            if (
                parent not in seen
                or by_id[parent]["target_anchor_s"] > r["target_anchor_s"]
            ):
                raise ValueError(
                    "after must cite an earlier mapping with earlier anchor"
                )
        seen.add(r["id"])
    for i, r in enumerate(used):
        if (
            any(p["source_id"] == r["source_id"] for p in used[:i])
            and not r["reuse_reason"]
        ):
            raise ValueError("Repeated source ID needs reuse_reason")
    return out


def suitability(rows):
    """Return a conservative summary; loudness alone never makes a source suitable."""
    used = [r for r in rows if r["disposition"] == "use"]
    return {
        "schema": SCHEMA,
        "used_count": len(used),
        "unmatched_count": sum(r["disposition"] == "unmatched" for r in rows),
        "omitted_count": sum(r["disposition"] == "omit" for r in rows),
        "status": "provisional" if used else "unsuitable",
    }


def identities(case):
    return {
        role: hashlib.sha256(case[key].read_bytes()).hexdigest()
        for role, key in [
            ("target", "original_path"),
            ("source", "sfx_path"),
            ("video", "video_path"),
        ]
    }


def catalog(case, evidence):
    """Only current-file, current-model window inventories can support new mappings."""
    from . import perception

    hashes = identities(case)
    out = {"target": {}, "source": {}}
    for ev in evidence.values():
        r = ev["receipt"]
        role = r["role"]
        if role not in out or r["file_sha256"] != hashes[role]:
            continue
        if ev.get("served_model") != perception.MODEL:
            continue
        expected = perception.digest(
            json.dumps(
                {
                    "receipt": r,
                    "model": perception.MODEL,
                    "prompt": perception.PROMPT,
                    "version": 1,
                },
                sort_keys=True,
            ).encode()
        )
        if ev.get("evidence_id") != expected:
            continue
        for e in ev["inventory"]["events"]:
            out[role][e["id"]] = {
                "event": e,
                "evidence_id": ev["evidence_id"],
                "range_s": [r["start_s"], r["end_s"]],
                "file_sha256": r["file_sha256"],
            }
    return out


def bind(rows, case, evidence, *, require_impact_anchors=False):
    c = catalog(case, evidence)
    rows = validate(
        rows,
        target_duration_s=case["seconds"],
        source_duration_s=len(media.read_audio(case["sfx_path"])) / RATE,
        target_ids=c["target"],
        source_ids=c["source"],
        require_impact_anchors=require_impact_anchors,
    )
    refs = {}
    for r in rows:
        for role in ("target", "source"):
            if role == "source" and r["disposition"] != "use":
                continue
            ref = c[role][r[role + "_id"]]
            lo, hi = r[role + "_range_s"]
            a, b = ref["range_s"]
            if lo < a or hi > b:
                raise ValueError("Mapping crop exceeds inspected " + role + " window")
            event = ref["event"]
            if hi < event["onset_range_s"][0] or lo > event["offset_range_s"][1]:
                raise ValueError(
                    "Mapping range does not overlap cited " + role + " event"
                )
            refs[role + ":" + r[role + "_id"]] = ref
    return {
        "schema": SCHEMA,
        "rows": rows,
        "input_hashes": identities(case),
        "references": refs,
        "id": hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()[
            :20
        ],
        "summary": suitability(rows),
        "provenance": "agent_hypothesis",
        "human_approved": False,
    }


def source_options(source, start, end):
    """Measured transient candidates, never semantic labels. No strongest-peak fallback on noise/silence."""
    if not np.all(np.isfinite(source)):
        raise ValueError("Nonfinite source")
    if not 0 <= _finite(start, "start") < _finite(end, "end") <= len(source) / RATE:
        raise ValueError("Source window outside media")
    lo, hi = round(start * RATE), round(end * RATE)
    events = media.detect(source[lo:hi], 6, 0.12)
    peaks = [lo + round(e["time_s"] * RATE) for e in events]
    options = []
    for i, p in enumerate(peaks):
        left = max(lo, p - round(0.06 * RATE), (peaks[i - 1] + p) // 2 if i else lo)
        right = min(
            hi,
            p + round(0.24 * RATE),
            (p + peaks[i + 1]) // 2 if i + 1 < len(peaks) else hi,
        )
        if right - left < round(0.02 * RATE):
            continue
        part = source[left:right]
        body = media.body_level(part)
        options.append(
            {
                "index": len(options),
                "source_range_s": [left / RATE, right / RATE],
                "source_anchor_s": p / RATE,
                "body_dbfs": body,
                "weak": body < -50,
            }
        )
    # Preserve baseline indices; add tails only in spare slots, never displace other attacks.
    variants = []
    for option in options:
        option["variant"] = "standard"
        p = round(option["source_anchor_s"] * RATE)
        following = next((q for q in peaks if q > p), hi)
        right = min(
            hi, p + round(0.8 * RATE), (p + following) // 2 if following < hi else hi
        )
        left = round(option["source_range_s"][0] * RATE)
        if right > round(option["source_range_s"][1] * RATE) + round(0.03 * RATE):
            tail = source[round(option["source_range_s"][1] * RATE) : right]
            tail_level = media.db(np.sqrt(np.mean(tail * tail)))
            if tail_level < -50:
                continue
            body = media.body_level(source[left:right])
            variants.append(
                {
                    **option,
                    "source_range_s": [left / RATE, right / RATE],
                    "body_dbfs": body,
                    "weak": body < -50,
                    "variant": "extended_tail",
                    "tail_rms_dbfs": tail_level,
                }
            )
    options += variants
    for index, option in enumerate(options):
        option["index"] = index
    return {
        "options": options[:MAX_SOURCE_OPTIONS],
        "total": len(options),
        "truncated": len(options) > MAX_SOURCE_OPTIONS,
        "warning": "Acoustic peaks may be scrapes/echoes/noise. Choose a localized source window; no semantic suitability is implied.",
    }


def coverage(candidate, targets, reviews=()):
    """Compare declared hypotheses with saved rows and actual layer extents, not semantic truth."""
    from .perception import gaps

    rows = candidate.get("arrangement", {}).get("rows", [])
    outputs = {
        m["mapping_id"]: m["output_range_s"]
        for m in candidate.get("event_metrics", [])
        if "mapping_id" in m
    }
    events = []
    for key, ref in targets.items():
        event = ref["event"]
        a, b = event["onset_range_s"][0], event["offset_range_s"][1]
        matched = [r for r in rows if r["target_id"] == key]
        used = [r for r in matched if r["disposition"] == "use"]
        intervals = [outputs[r["id"]] for r in used if r["id"] in outputs]
        clipped = [[max(a, x), min(b, y)] for x, y in intervals if x < b and y > a]
        events.append(
            {
                "target_id": key,
                "kind": event["kind"],
                "range_s": [a, b],
                "mapping_ids": [r["id"] for r in matched],
                "dispositions": sorted({r["disposition"] for r in matched}),
                "unmapped": not matched,
                "missing_output_ids": [r["id"] for r in used if r["id"] not in outputs],
                "uncovered_hypothesis_ranges_s": gaps(clipped, a, b),
            }
        )
    return {
        "events": events,
        "unmapped_target_ids": [e["target_id"] for e in events if e["unmapped"]],
        "missing_output_ids": [
            r["id"]
            for r in rows
            if r["disposition"] == "use" and r["id"] not in outputs
        ],
        "reviewed_contacts_without_output_s": [
            r["center_s"]
            for r in reviews
            if r.get("verdict") == "target"
            and not any(a <= r["center_s"] <= b for a, b in outputs.values())
        ],
        "warning": "Hypothesis interval coverage is not desired sound duration. Omit/unmatched and silence may be intentional; do not fill gaps automatically. Events absent from both inventories and reviews remain undetectable here.",
    }


def stage_rows(rows, mapping_id, phases):
    """Expand one composite into independently anchored phases; caller binds before saving."""
    parent = next((r for r in rows if r["id"] == mapping_id), None)
    if not parent or parent["kind"] != "composite" or parent["disposition"] != "use":
        raise ValueError("Choose a used composite row")
    if not isinstance(phases, list) or not 2 <= len(phases) <= 12:
        raise ValueError("Provide 2..12 explicit phases")
    staged = []
    keys = {
        "kind",
        "target_range_s",
        "source_range_s",
        "target_anchor_s",
        "source_anchor_s",
        "evidence",
    }
    for i, phase in enumerate(phases):
        if not isinstance(phase, dict) or set(phase) != keys:
            raise ValueError(
                "Each phase needs kind, independent target/source ranges and anchors, evidence"
            )
        if phase["kind"] not in ("impact", "texture", "composite"):
            raise ValueError("Invalid phase kind")
        for role in ("target", "source"):
            bounds = phase[role + "_range_s"]
            if not isinstance(bounds, list) or len(bounds) != 2:
                raise ValueError("Phase range requires two seconds")
            lo, hi = (_finite(v, "phase range") for v in bounds)
            a, b = parent[role + "_range_s"]
            if not a <= lo < hi <= b:
                raise ValueError("Phase outside inspected parent range")
        row = {
            **parent,
            **phase,
            "id": mapping_id + "-phase-" + str(i + 1),
            "anchor": "contact" if phase["kind"] == "impact" else "transition",
            "repeat": False,
            "reuse_reason": "Explicit phases of the same inspected composite recording",
            "after": [staged[-1]["id"]] if staged else parent.get("after", []),
        }
        staged.append(row)
    if any(
        a["target_anchor_s"] > b["target_anchor_s"] for a, b in zip(staged, staged[1:])
    ):
        raise ValueError("Phase anchors must follow target chronology")
    retained = [
        {
            **r,
            "after": [
                staged[-1]["id"] if x == mapping_id else x for x in r.get("after", [])
            ],
        }
        for r in rows
        if r["id"] != mapping_id
    ]
    return sorted(retained + staged, key=lambda r: r["target_range_s"][0])


def prepare_impact(row, source, index, target_contact):
    """Prepare one chosen impact, preserving independent target timing and source evidence bounds."""
    if row["kind"] != "impact" or row["disposition"] != "use":
        raise ValueError(
            "Only used impacts: texture/composite chronology must remain explicit"
        )
    ta, tb = row["target_range_s"]
    if not ta <= _finite(target_contact, "target contact") < tb:
        raise ValueError("Contact outside target window")
    options = source_options(source, *row["source_range_s"])["options"]
    if type(index) is not int or not 0 <= index < len(options):
        raise ValueError("Choose an available measured source option")
    option = options[index]
    if option["weak"]:
        raise ValueError("Source too weak to balance safely; choose another window")
    return {
        **row,
        "source_range_s": option["source_range_s"],
        "source_anchor_s": option["source_anchor_s"],
        "target_anchor_s": target_contact,
        "anchor": "contact",
        "repeat": False,
        "shape": "soften",
        "target_body_dbfs": row.get("target_body_dbfs")
        if row.get("target_body_dbfs") is not None
        else -22,
    }


def assemble(rows, source, seconds):
    """Source landmark aligns to target landmark. No strongest-peak substitution or stretch."""
    if not np.all(np.isfinite(source)):
        raise ValueError("Nonfinite source samples")
    out = np.zeros(round(seconds * RATE))
    metrics = []
    for r in rows:
        if r["disposition"] != "use":
            continue
        sa, sb = r["source_range_s"]
        ta, tb = r["target_range_s"]
        part = source[round(sa * RATE) : round(sb * RATE)].copy()
        source_peak = float(np.max(np.abs(part)))
        body = media.body_level(part)
        if r["shape"] == "soften":
            knee = max(10 ** (body / 20) * 1.25, 1e-6)
            mag = np.abs(part)
            part = np.sign(part) * np.where(mag > knee, knee * (mag / knee) ** 0.5, mag)
        # Explicit source-to-target anchor offset preserves attack/body/tail chronology.
        start = r["target_anchor_s"] - (r["source_anchor_s"] - sa)
        seams = []
        if r["repeat"]:
            if r["kind"] != "texture" or r["anchor"] != "start":
                raise ValueError("Repeat is explicit start-anchored texture only")
            part, seams = repeat_audio(part, tb - ta, r["crossfade_s"], True)
        elif r["kind"] == "texture" and len(part) / RATE + 1 / RATE < tb - ta:
            raise ValueError(
                "Source shorter than texture: shorten target or explicitly enable repeat; no stretch"
            )
        dest = max(round(ta * RATE), round(start * RATE), 0)
        skip = max(0, dest - round(start * RATE))
        count = min(len(part) - skip, round(tb * RATE) - dest, len(out) - dest)
        if count < 1:
            raise ValueError("Anchor places entire source outside target interval")
        part = part[skip : skip + count]
        for key, reverse in [("fade_in_s", False), ("fade_out_s", True)]:
            n = min(round(r[key] * RATE), len(part) // 2)
            if n:
                if reverse:
                    part[-n:] *= np.linspace(1, 0, n)
                else:
                    part[:n] *= np.linspace(0, 1, n)
        normalization = 0
        if r.get("target_body_dbfs") is not None:
            level = media.body_level(part)
            if level < -50:
                raise ValueError("Trimmed source too weak to balance safely")
            normalization = min(12, max(-18, r["target_body_dbfs"] - level))
            part *= 10 ** (normalization / 20)
        part *= 10 ** (r["gain_db"] / 20)
        out[dest : dest + count] += part
        metrics.append(
            {
                "mapping_id": r["id"],
                "output_range_s": [dest / RATE, (dest + count) / RATE],
                "normalization_db": normalization,
                "rendered_peak_s": (dest + int(np.argmax(np.abs(part)))) / RATE,
                "target_anchor_s": r["target_anchor_s"],
                "source_anchor_s": r["source_anchor_s"],
                "source_body_dbfs": body,
                "body_dbfs": media.body_level(part),
                "crest_db": media.db(np.max(np.abs(part))) - media.body_level(part),
                "source_near_full_scale": source_peak >= 0.999,
                "gain_db": r["gain_db"],
                "seams_s": [start + t for t in seams if ta <= start + t <= tb],
                "trimmed_samples": skip
                + max(0, round((sb - sa) * RATE) - skip - count),
            }
        )
        metrics[-1]["source_duration_s"] = sb - sa
        metrics[-1]["target_duration_s"] = tb - ta
        metrics[-1]["duration_mismatch_s"] = (tb - ta) - (sb - sa)
    for r in rows:
        if r["kind"] == "pause" and r["disposition"] == "omit":
            a, b = (round(x * RATE) for x in r["target_range_s"])
            if np.any(out[a:b]):
                raise ValueError(
                    "Intentional pause overlaps an active sound layer; revise ranges"
                )
    return out, metrics


def render(case, bound, folder):
    if bound["input_hashes"] != identities(case):
        raise ValueError("Stale arrangement media; rebind evidence")
    rows = bound["rows"]
    out, events = assemble(rows, media.read_audio(case["sfx_path"]), case["seconds"])
    if not events:
        raise ValueError("No used mappings; finish unsuitable without inventing output")
    gain = min(0, -3 - media.db(np.max(np.abs(out))))
    out *= 10 ** (gain / 20)
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
            video,
        )
        encoded = media.measure_export(video)
        if encoded["true_peak_dbtp"] <= -1:
            break
        adjustment = -1.5 - encoded["true_peak_dbtp"]
        out *= 10 ** (adjustment / 20)
        gain += adjustment
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
    picture = media.picture_hash(case["video_path"]) == media.picture_hash(video)
    if not picture:
        raise ValueError("Picture preservation failed")
    flags = []
    for e in events:
        a, b = (round(t * RATE) for t in e["output_range_s"])
        window = decoded[a:b]
        e["decoded_mix_body_dbfs"] = media.body_level(window)
        e["decoded_mix_peak_dbfs"] = media.db(np.max(np.abs(window)))
        e["body_dbfs"] += gain
        if e["source_near_full_scale"]:
            flags.append("source_near_full_scale")
        if e["body_dbfs"] < -50:
            flags.append("very_weak_layer")
    clipped = int(np.sum(np.abs(decoded) >= 1))
    if clipped:
        flags.append("decoded_clipping")
    result = {
        "id": rid,
        "video": video.name,
        "wav": wav.name,
        "render_mode": "arrangement",
        "arrangement": bound,
        "plan": [
            {
                "time_s": r["target_anchor_s"],
                "duration_s": r["target_range_s"][1] - r["target_range_s"][0],
                "sample_id": r["source_id"],
                "gain_db": r["gain_db"],
                "confidence": r["confidence"],
                "evidence": r["evidence"],
            }
            for r in rows
            if r["disposition"] == "use"
        ],
        "audio_sha256": hashlib.sha256(wav.read_bytes()).hexdigest(),
        "event_metrics": events,
        "metrics": {
            **encoded,
            "picture_unchanged": picture,
            "clipped_samples": clipped,
            "mix_attenuation_db": gain,
        },
        "flags": sorted(set(flags)),
        "engineering_pass": not flags,
        "warning": "Whole soundtrack replacement. Explicit source chronology, no time stretch. Technical checks do not establish correct actions or natural sound.",
    }
    atomic(folder / (rid + ".json"), result)
    return result
