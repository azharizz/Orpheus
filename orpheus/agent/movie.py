"""Single-call movie coordinator before bounded family-level agent runs."""

import json
import re

from google.adk.models.llm_request import LlmRequest
from google.genai import types

from ..domain import projects
from .provider import ControllerModel
from .workflow_common import frame_parts


def _json(text):
    match = re.search(r"\{.*\}", text, re.S)
    if not match:
        raise ValueError("Coordinator returned no JSON object")
    return json.loads(match.group())


async def coordinate(pid, analysis, grafana, log):
    """Inspect representative picture moments and return bounded review advice."""
    case = projects.load(pid)
    representatives = []
    for band in ("low", "mid", "bright"):
        event = next((row for row in analysis["events"] if row["acoustic_band"] == band), None)
        if event:
            representatives.append(event["anchor_s"])
    representatives.extend(row["range_s"][0] for row in analysis["noise_regions"][:3])
    images = projects.frames(case, sorted(set(representatives))[:6], projects.project_dir(pid) / "movie-frames")
    family_ids = [row["id"] for row in analysis["families"]]
    noise_ids = [row["id"] for row in analysis["noise_regions"]]
    prompt = {
        "task": "Coordinate review of a long-form Foley movie from deterministic evidence and representative frames.",
        "rules": [
            "Return JSON only.",
            "Do not claim sound identity from a picture or acoustic band.",
            "Recommend run_family_agent only when a family has a replacement take; otherwise needs_sfx or human_review.",
            "Noise is a hypothesis and must never be removed automatically.",
            "Use Grafana evidence before every recommendation.",
        ],
        "response_schema": {"families": [{"id": "allowed id", "working_label": "short cautious label", "action": "run_family_agent|needs_sfx|human_review", "reason": "short"}], "noise": [{"id": "allowed id", "action": "human_review|dismiss", "reason": "short"}], "summary": "short"},
        "families": analysis["families"],
        "noise_regions": analysis["noise_regions"],
        "event_counts": {band: sum(row["acoustic_band"] == band for row in analysis["events"]) for band in ("low", "mid", "bright")},
        "grafana": {key: grafana.get(key) for key in ("status", "evidence_count", "receipt_id")},
    }
    request = LlmRequest(
        contents=[types.Content(role="user", parts=[types.Part(text=json.dumps(prompt)), *frame_parts(images)])],
        config=types.GenerateContentConfig(temperature=0.1, response_mime_type="application/json"),
    )
    text = ""
    async for response in ControllerModel(log).generate_content_async(request):
        text += "".join(part.text or "" for part in response.content.parts if response.content)
    result = _json(text)
    allowed_actions = {"run_family_agent", "needs_sfx", "human_review"}
    families = []
    for row in result.get("families", []):
        if row.get("id") not in family_ids or row.get("action") not in allowed_actions:
            continue
        families.append({"id": row["id"], "working_label": str(row.get("working_label", "Unconfirmed family"))[:60], "action": row["action"], "reason": str(row.get("reason", ""))[:240]})
    noise = []
    for row in result.get("noise", []):
        if row.get("id") in noise_ids and row.get("action") in ("human_review", "dismiss"):
            noise.append({"id": row["id"], "action": row["action"], "reason": str(row.get("reason", ""))[:240]})
    return {"status": "completed", "families": families, "noise": noise, "summary": str(result.get("summary", ""))[:400]}
