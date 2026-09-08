"""Persist human judgments for rendered family candidates."""

import json
import re
import time
import uuid

from ..ops import observability as obs
from . import projects


def candidate(case, candidate_id, *, allow_audition=False):
    if not isinstance(candidate_id, str) or not re.fullmatch(
        r"[a-f0-9]{12}", candidate_id
    ):
        raise ValueError("Choose a rendered candidate.")
    folder = projects.project_dir(case["id"])
    result = json.loads((folder / (candidate_id + ".json")).read_text())
    audio = folder / (candidate_id + ".wav")
    if (
        result.get("schema") != "family-render.v1"
        or result.get("id") != candidate_id
        or result.get("project_id") != case["id"]
        or result.get("wav") != audio.name
        or result.get("render_mode") not in (
            "selective_duck_overlay",
            "agent_fitted_selective_duck_overlay",
        )
    ):
        raise ValueError("Choose the latest rendered family candidate.")
    from . import families

    family = families.get(case["id"], result.get("family_id"))
    if family.get("latest_render_id") != candidate_id and not (
        allow_audition and result.get("preview_kind") == "match_audition"
    ):
        raise ValueError("Choose the latest rendered family candidate.")
    if projects.digest(audio) != result["audio_sha256"]:
        raise ValueError(
            "Candidate audio has changed. Render a new alternative before review."
        )
    return result


def save_review(data):
    case = projects.load(data["project_id"])
    rendered = candidate(case, data["candidate_id"])
    verdict = data["verdict"]
    note = data.get("note", "")
    if verdict not in ("approve", "reject"):
        raise ValueError("Choose approve or reject.")
    if not isinstance(note, str) or len(note) > 500:
        raise ValueError("Review notes must be at most 500 characters.")
    record = {
        "candidate_id": rendered["id"],
        "audio_sha256": rendered["audio_sha256"],
        "verdict": verdict,
        "note": note,
        "provenance": "human_ui",
        "created_at": time.time(),
    }
    projects.atomic(
        projects.project_dir(case["id"]) / (uuid.uuid4().hex[:12] + "-human.json"),
        record,
    )
    if rendered.get("family_id"):
        from . import families

        families.record_render_review(
            case["id"], rendered["family_id"], rendered["id"], verdict
        )
    obs.emit(
        case["id"],
        "human_review",
        {
            **record,
            "parent_project_id": case.get("take_parent_project_id", case["id"]),
            **{
                key: rendered[key]
                for key in ("part_start_s", "part_end_s", "family_id")
                if key in rendered
            },
        },
    )
    return record
