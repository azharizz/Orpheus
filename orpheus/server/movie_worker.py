"""One-click movie coordinator over deterministic analysis and family agents."""

import argparse
import asyncio
import json
import time

from .. import config
from ..domain import movie, projects
from ..ops import observability as obs
from ..agent.movie import coordinate
from . import worker


async def execute(pid, feedback):
    started = time.time()
    analysis = await asyncio.to_thread(movie.analyze, pid)
    eligible = movie.eligible_families(pid)
    receipt = {
        "schema": "movie-agent-run.v1",
        "project_id": pid,
        "started_at": started,
        "status": "review_required",
        "analysis": {"events": len(analysis["events"]), "families": len(analysis["families"]), "noise_regions": len(analysis["noise_regions"])},
        "family_runs": [],
        "agent_role": "movie_coordinator",
    }
    obs.emit(pid, "movie_agent_started", {"status": "running", "measurements": receipt["analysis"]})
    history = await obs.investigate(pid, "history")
    obs.emit(pid, "movie_grafana_evidence", {"status": history.get("status"), "evidence_count": history.get("evidence_count", 0)})
    def log(event, **fields):
        obs.emit(pid, event, fields, "movie")
    try:
        receipt["coordination"] = await coordinate(pid, analysis, history, log)
    except Exception as exc:
        receipt["coordination"] = {"status": "failed", "error_type": type(exc).__name__, "warning": "No model recommendation accepted; deterministic evidence remains available for human review."}
    for row in [*receipt["coordination"].get("families", []), *receipt["coordination"].get("noise", [])]:
        obs.emit(pid, "movie_agent_decision", {
            "family_id": row.get("id") if row.get("id") in {family["id"] for family in analysis["families"]} else None,
            "event_id": row.get("id"),
            "decision": row.get("action"),
            "reason": row.get("reason"),
        })
    advice = {row["id"]: row for row in receipt["coordination"].get("families", [])}
    for family in eligible[:config.MAX_MOVIE_FAMILY_RUNS]:
        recommendation = advice.get(family["id"], {})
        if recommendation.get("action") not in (None, "run_family_agent"):
            receipt["family_runs"].append({"family_id": family["id"], "status": "deferred", "reason": recommendation.get("reason")})
            continue
        obs.emit(pid, "movie_agent_decision", {"family_id": family["id"], "decision": "delegate_family_agent", "reason": "Reviewed ranges and an assigned take are available."})
        result = await worker.execute(pid, family["id"], feedback)
        receipt["family_runs"].append({"family_id": family["id"], "status": result["status"], "turn_id": result["id"], "selection": result.get("selection")})
    for family in eligible[config.MAX_MOVIE_FAMILY_RUNS:]:
        receipt["family_runs"].append({"family_id": family["id"], "status": "deferred", "reason": "Movie paid-run limit reached; review and run this family separately."})
    if eligible and any(row["status"] == "review_required" for row in receipt["family_runs"]):
        try:
            receipt["draft"] = movie.render_draft(pid)
        except ValueError as exc:
            receipt["draft_error"] = str(exc)
    if not eligible:
        receipt["agent_gate"] = "No family-fitting model called: the paid coordinator reviewed evidence, but replacement SFX must be assigned first."
    receipt["finished_at"] = time.time()
    projects.atomic(projects.project_dir(pid) / "movie-agent-run.json", receipt)
    analysis = movie.status(pid)
    analysis["agent"] = {"role": "coordinator", "stage": "human_review", "last_run": receipt}
    movie._save(pid, analysis)
    obs.emit(pid, "movie_agent_finished", {"status": receipt["status"], "elapsed_s": receipt["finished_at"] - started, "families_run": len(receipt["family_runs"])})
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("project")
    parser.add_argument("--feedback", default="Coordinate reviewed sound families across this movie using deterministic and Grafana evidence.")
    args = parser.parse_args()
    print(json.dumps(asyncio.run(execute(args.project, args.feedback))))
