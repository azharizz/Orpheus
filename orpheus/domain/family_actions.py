"""Small human-authorized mutations for sound families."""

import json
import time
import uuid

from ..ops import observability as obs
from . import families, takes
from .projects import atomic


def add_example(pid, family_id, range_s):
    case = families.load(pid)
    doc = families.get(pid, family_id)
    examples = [item for item in doc["accepted_ranges"] if item.get("kind") == "example" or item["id"] == "seed"]
    if len(examples) >= families.MAX_EXAMPLES:
        raise ValueError(f"A sound family supports at most {families.MAX_EXAMPLES} confirmed examples")
    bounds = families._range(range_s, float(case["seconds"]), "example range")
    if not families.MIN_SEED_S <= bounds[1] - bounds[0] <= families.MAX_SEED_S:
        raise ValueError(f"Example duration must be {families.MIN_SEED_S}..{families.MAX_SEED_S} seconds")
    if any(max(bounds[0], item["range_s"][0]) < min(bounds[1], item["range_s"][1]) for item in doc["accepted_ranges"]):
        raise ValueError("Confirmed example overlaps an existing family range")
    _, anchor = families._feature_at(case["original_path"], bounds)
    item = {
        "schema": families.MATCH_SCHEMA, "id": "example-" + uuid.uuid4().hex[:8],
        "kind": "example", "range_s": bounds, "refined_anchor_s": round(anchor, 6),
        "similarity_score": 1.0, "decision": "accepted",
        "evidence_summary": "Human-confirmed query example.",
    }
    doc["accepted_ranges"].append(item)
    doc["latest_render"] = {}
    doc["updated_at"] = time.time()
    atomic(families._family_path(pid, family_id), doc)
    obs.emit(pid, "family_example_confirmed", {
        "family_id": family_id, "mapping_id": item["id"], "start_s": bounds[0],
        "end_s": bounds[1], "decision": "accepted",
    })
    return doc


def assign_take(pid, family_id, take_id):
    takes.validated_audio(pid, family_id, take_id)
    doc = families.get(pid, family_id)
    doc["replacement_take_id"] = take_id
    doc["updated_at"] = time.time()
    atomic(families._family_path(pid, family_id), doc)
    return doc


def record_render_review(pid, family_id, render_id, verdict):
    family = families.get(pid, family_id)
    if family.get("latest_render_id") != render_id or verdict not in ("approve", "reject"):
        raise ValueError("Review does not match the latest family render")
    receipt_path = families.project_dir(pid) / f"{render_id}.json"
    receipt = json.loads(receipt_path.read_text())
    expected = {"schema": "family-render.v1", "project_id": pid, "family_id": family_id, "id": render_id}
    if any(receipt.get(key) != value for key, value in expected.items()):
        raise ValueError("Render receipt provenance mismatch")
    receipt["human_approved"] = verdict == "approve"
    receipt["human_verdict"] = verdict
    atomic(receipt_path, receipt)
    family["latest_render"]["human_approved"] = verdict == "approve"
    family["last_render_verdict"] = verdict
    family["updated_at"] = time.time()
    atomic(families._family_path(pid, family_id), family)
    return family
