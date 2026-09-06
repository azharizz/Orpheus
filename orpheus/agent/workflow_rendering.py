import re

from google.adk.tools import ToolContext

from ..domain import arrangement, fitting, media, texture
from ..ops import observability as obs
from .workflow_common import perception_gate


class RenderingTools:
    def save_event_plan(self, events_json: str, tool_context: ToolContext) -> dict:
        """Save the COMPLETE signal-fallback discrete plan before render_plan; not the mixed-arrangement path. events_json is 1..100 objects with exactly time_s,duration_s,sample_id,gain_db,confidence,evidence. Use usable INTEGER source_bank IDs, duration 0.12..3s, gain -8..6, confidence likely/uncertain, evidence 1..400 chars. Sort target times >=0.05s apart. Every event needs review_moments within 0.2s this turn plus a delivered qualifying verdict. Returns saved plan or error."""
        import json

        s = tool_context.state
        try:
            if not s.get("inspected"):
                raise ValueError("Inspect scene first")
            plan = fitting.validate_plan(json.loads(events_json), self.case)
            if any(
                not any(abs(e["time_s"] - t) <= 0.2 for t in s.get("reviewed", []))
                for e in plan
            ):
                raise ValueError(
                    "Every proposed event needs review_moments within 0.2s this turn"
                )
            reviews = s.get("event_reviews", [])
            for e in plan:
                nearby = [r for r in reviews if abs(e["time_s"] - r["center_s"]) <= 0.2]
                if not nearby:
                    raise ValueError("Every planned event needs an event review")
                nearest = min(nearby, key=lambda r: abs(e["time_s"] - r["center_s"]))[
                    "center_s"
                ]
                latest = next(r for r in reversed(nearby) if r["center_s"] == nearest)
                if latest["verdict"] == "non_target":
                    raise ValueError("Nearest reviewed event is non_target")
                if latest["verdict"] == "uncertain" and e["confidence"] != "uncertain":
                    raise ValueError(
                        "Uncertain review requires uncertain plan confidence"
                    )
        except (ValueError, TypeError, KeyError) as exc:
            return {"error": str(exc)[:400]}
        s["plan"] = plan
        self.log("plan_saved", plan=plan)
        return {"saved_events": len(plan), "plan": plan}

    def render_plan(
        self,
        target_body_dbfs: float,
        mode: str,
        hypothesis: str,
        tool_context: ToolContext,
    ) -> dict:
        """Render a saved reviewed signal-fallback discrete plan, once per cycle. Requires inspect_scene and, when audio access is enabled, attempts for BOTH target/source. target_body_dbfs -28..-16; mode balanced/recorded; hypothesis 1..1000 characters. Returns candidate id and measurements. MUST measure_candidate next; mixed inventory mappings use render_arrangement instead."""
        s = tool_context.state
        if not isinstance(hypothesis, str) or not 1 <= len(hypothesis) <= 1000:
            return {
                "error": "Hypothesis must be 1..1000 characters; not silently truncated."
            }
        if s.get("rendered"):
            return {"error": "Already rendered this cycle; end response to move on"}
        if not s.get("inspected"):
            return {"error": "Inspect this project before rendering"}
        if not s.get("plan"):
            return {"error": "Save a reviewed plan first"}
        gate = perception_gate(s, self.audio.enabled)
        if gate:
            return gate
        try:
            r = fitting.render(
                self.case, s["plan"], self.folder, target_body_dbfs, mode
            )
        except (ValueError, TypeError) as exc:
            return {"error": str(exc)[:400]}
        return self.record_candidate(r, hypothesis, tool_context)

    def record_candidate(self, r, hypothesis, tool_context):
        s = tool_context.state
        r["hypothesis"] = hypothesis[:1000]
        r["cycle"] = s.get("cycle", 0)
        r["strategy"] = self.strategy_fingerprint(r)
        prior_keys = {
            c.get("strategy", {}).get("key")
            for c in s.get("candidates", [])
            if c.get("strategy", {}).get("key")
        }
        r["strategy"]["distinct_from_prior"] = r["strategy"]["key"] not in prior_keys
        r["perception_warnings"] = {
            "unresolved_evidence_ids": [
                key
                for key, report in s.get("audio_reconciliations", {}).items()
                if report["status"] == "unresolved"
            ],
            "audio_attempt_status": dict(s.get("audio_attempts", {})),
            "notice": "Best-effort preview; semantic uncertainty does not block rendering or constitute user approval.",
        }
        r["identical_to"] = [
            p["id"]
            for p in s.get("candidates", [])
            if p["audio_sha256"] == r["audio_sha256"]
        ]
        s["candidates"] = [*s.get("candidates", []), r]
        s["rendered"] = True
        s["turn_renders"] = s.get("turn_renders", 0) + 1
        self.log("candidate", **r)
        if s.get("cycle", 0) < 5:
            tool_context.actions.skip_summarization = True
        return r

    def render_texture(
        self,
        start_s: float,
        end_s: float,
        source_start_s: float,
        source_end_s: float,
        target_body_dbfs: float,
        repeat: bool,
        crossfade_s: float,
        hypothesis: str,
        tool_context: ToolContext,
    ) -> dict:
        """Render ONE sustained interval in signal fallback after delivered target/uncertain reviews near target start/middle/end. Requires inspect_scene and both inspect_audio attempts if enabled. Target/source ranges use independent global seconds; target_body_dbfs -28..-16, crossfade_s 0.01..0.5, repeat explicit. Source must exceed twice the crossfade. Start-anchored, no impact fitting or combined layers. Returns candidate id; MUST measure_candidate next and check dropouts/seams, not impact timing."""
        s = tool_context.state
        if not isinstance(hypothesis, str) or not 1 <= len(hypothesis) <= 1000:
            return {
                "error": "Hypothesis must be 1..1000 characters; not silently truncated."
            }
        if s.get("rendered"):
            return {"error": "Already rendered this cycle"}
        if not s.get("inspected"):
            return {"error": "Inspect scene first"}
        gate = perception_gate(s, self.audio.enabled)
        if gate:
            return gate
        try:
            fitting.bounded(start_s, 0, self.case["seconds"] - 0.12, "start_s")
            fitting.bounded(end_s, start_s + 0.12, self.case["seconds"], "end_s")
            for t in [
                start_s,
                (start_s + end_s) / 2,
                min(end_s, self.case["seconds"] - 0.01),
            ]:
                if not any(abs(t - x) <= 0.2 for x in s.get("delivered_centers", [])):
                    raise ValueError(
                        "Review and record target interval start, middle and end first"
                    )
                reviews = [
                    r
                    for r in s.get("event_reviews", [])
                    if abs(t - r["center_s"]) <= 0.2
                ]
                if not reviews or reviews[-1]["verdict"] == "non_target":
                    raise ValueError("Interval review must be target or uncertain")
            r = texture.render(
                self.case,
                self.folder,
                start_s,
                end_s,
                source_start_s,
                source_end_s,
                target_body_dbfs,
                repeat,
                crossfade_s,
            )
        except (ValueError, TypeError) as exc:
            return {"error": str(exc)[:400]}
        return self.record_candidate(r, hypothesis, tool_context)

    def remember_decision(self, note: str, tool_context: ToolContext) -> dict:
        """Save a concise project lesson after a measured revision, resolved error or important remaining uncertainty. note is 1..500 characters; include relevant row/candidate, evidence, change and outcome. Last 12 notes remain in state. Use hypothesis language, never claim human approval or perfect verification. Optional when there is no useful new lesson."""
        if not 1 <= len(note) <= 500:
            return {"error": "Note 1..500 characters"}
        assertion = re.sub(
            "\\b(?:not|never|no)\\b[^.;:]{0,40}\\b(?:verified|confirmed|perfect|ground truth)\\b",
            "",
            note,
            flags=re.IGNORECASE,
        )
        if re.search(
            "\\b(verified|confirmed|perfect|ground truth)\\b", assertion, re.IGNORECASE
        ):
            return {
                "error": "Use hypothesis/uncertainty language, not verification claims. No human approval has been supplied to this tool."
            }
        s = tool_context.state
        s["notes"] = [*s.get("notes", []), note][-12:]
        self.log("memory_saved", note=note)
        return {
            "saved": True,
            "notes": s["notes"],
            "scope": "Last 12 notes only; earlier memory_saved events remain in the project log. Not verified facts.",
        }

    async def review_candidate_audio(
        self, candidate_id: str, start_s: float, end_s: float, tool_context: ToolContext
    ) -> dict:
        """Inspect actual decoded MP4 audio after measure_candidate, before final comparison when audio-model budget permits. Use a registered candidate ID and <=30s window. Shares six audio requests/turn with input inspection; reserve calls. Observer hears only this render, not inputs or plan. Hypotheses cannot verify sync or suitability. Saves separate candidate evidence; never adds it to target/source inventory. Failed/budget-exhausted is unresolved, not approval."""
        candidate = next(
            (
                c
                for c in tool_context.state.get("candidates", [])
                if c["id"] == candidate_id
            ),
            None,
        )
        if candidate is None:
            return {"error": "Unknown candidate"}
        if not re.fullmatch("[a-f0-9]{12}", candidate_id):
            return {"error": "Invalid candidate ID"}
        result = await self.audio.inspect(
            "candidate",
            start_s,
            end_s,
            {**self.case, "candidate_path": self.folder / (candidate_id + ".mp4")},
        )
        report = {
            k: v
            for k, v in result.items()
            if k not in ("raw_observation", "measurements")
        }
        reports = dict(tool_context.state.get("candidate_audio_reviews", {}))
        reports[candidate_id] = report
        tool_context.state["candidate_audio_reviews"] = reports
        from ..domain.projects import atomic

        atomic(self.folder / (candidate_id + "-audio-review.json"), report)
        self.log("candidate_audio_review", candidate_id=candidate_id, **report)
        return {"candidate_id": candidate_id, **report}

    def measure_candidate(self, candidate_id: str, tool_context: ToolContext) -> dict:
        """MUST inspect each successful render at the next controller opportunity, before selecting it or another revision. candidate_id is the render's returned id, never arrangement_id/mapping_id. Returns metrics and per-impact timing/missing-row checks as applicable; textures have no impact-timing metric. Errors measure alignment against the proposed schedule, not visual truth. Does not edit or approve audio."""
        c = next(
            (
                c
                for c in tool_context.state.get("candidates", [])
                if c["id"] == candidate_id
            ),
            None,
        )
        if c is None:
            return {"error": "Unknown candidate"}
        if c.get("render_mode") == "texture":
            return {
                "candidate_id": candidate_id,
                "metrics": c["metrics"],
                "event_metrics": c.get("event_metrics", []),
                "timing_status": "not_applicable_for_start_anchored_texture",
                "warning": "Decoded signal checks are not semantic or listening approval.",
            }
        if c.get("render_mode") == "arrangement":
            rows = [
                r
                for r in c.get("arrangement", {}).get("rows", [])
                if r.get("kind") == "impact" and r.get("disposition") == "use"
            ]
            metrics = list(c.get("event_metrics", []))
            encoded = media.encoded_timing(
                self.folder / (candidate_id + ".mp4"),
                [{"scheduled_peak_s": r.get("target_anchor_s")} for r in rows],
            )
            fitted = []
            for row, measurement in zip(rows, encoded.get("events", [])):
                fitted.append(
                    {
                        "mapping_id": row.get("id"),
                        "target_anchor_s": row.get("target_anchor_s"),
                        "source_anchor_s": row.get("source_anchor_s"),
                        "rendered_peak_s": measurement.get("measured_peak_s"),
                        "timing_error_ms": measurement.get("peak_error_ms"),
                    }
                )
            event_ids = {m.get("mapping_id") for m in metrics}
            missing = [r.get("id") for r in rows if r.get("id") not in event_ids]
            result = {
                "candidate_id": candidate_id,
                "metrics": c["metrics"],
                "event_metrics": metrics,
                "fitted_impacts": fitted,
                "missing_fitted_impacts": missing,
                "timing": encoded,
                "timing_status": "measured",
                "coverage": arrangement.coverage(
                    c,
                    arrangement.catalog(
                        self.case, tool_context.state.get("audio_evidence", {})
                    )["target"],
                    tool_context.state.get("event_reviews", []),
                ),
                "warning": "Timing is measured against the arrangement anchors, not visual ground truth or listening approval.",
            }
            from ..domain.projects import atomic

            atomic(self.folder / (candidate_id + "-measurement.json"), result)
            self.log("candidate_timing_measured", **result)
            return result
        result = media.encoded_timing(
            self.folder / (candidate_id + ".mp4"),
            [{"scheduled_peak_s": e["time_s"]} for e in c["plan"]],
        )
        self.log("candidate_timing_measured", candidate_id=candidate_id, **result)
        return result

    def finish(
        self,
        candidate_id: str,
        decision: str,
        comparison: str,
        unresolved: list[str],
        tool_context: ToolContext,
    ) -> dict:
        """MUST conclude once comparison is complete or useful progress is impossible; success ends the loop. decision is needs_human_review/unsuitable. Review requires a real candidate_id, >=2 distinct project waveforms and >=1 current-turn render; measure the chosen render first. For unsuitable with no usable candidate pass candidate_id empty string. comparison 1..3000 chars, unresolved <=15 strings of 1..500 chars. Do not invent approval; check errors instead of assuming the run ended."""
        s = tool_context.state
        cs = s.get("candidates", [])
        if decision == "unsuitable" and candidate_id.strip().lower() in (
            "none",
            "null",
            "",
        ):
            candidate_id = ""
        if not isinstance(comparison, str) or not 1 <= len(comparison) <= 3000:
            return {
                "error": "Comparison must be 1..3000 characters; not silently truncated."
            }
        if (
            not isinstance(unresolved, list)
            or len(unresolved) > 15
            or any(not isinstance(x, str) or not 1 <= len(x) <= 500 for x in unresolved)
        ):
            return {
                "error": "Provide at most 15 unresolved items, each 1..500 characters; consolidate without hiding unresolved issues."
            }
        if decision not in ("needs_human_review", "unsuitable"):
            return {"error": "Invalid decision"}
        if decision != "unsuitable":
            if obs.config() and "sound:" + candidate_id not in s.get(
                "grafana_receipts", {}
            ):
                return {
                    "error": "Query Grafana sound evidence for this candidate after measuring it before final comparison. Report an unavailable query honestly."
                }
            if len({c["audio_sha256"] for c in cs}) < 2:
                return {"error": "Compare two different waveforms first"}
            if not s.get("turn_renders"):
                return {"error": "Render at least one candidate addressing this turn"}
        if candidate_id and candidate_id not in [c["id"] for c in cs]:
            return {"error": "Unknown candidate"}
        if not candidate_id and decision != "unsuitable":
            return {"error": "Candidate required"}
        selected = next((c for c in cs if c["id"] == candidate_id), None)
        strategy_count = len(
            {
                c.get("strategy", {}).get("key")
                for c in cs
                if c.get("strategy", {}).get("key")
            }
        )
        s["selection"] = {
            "candidate_id": candidate_id,
            "decision": decision,
            "comparison": comparison[:3000],
            "unresolved": unresolved[:15],
            "engineering_pass": selected["engineering_pass"] if selected else False,
            "distinct_strategy_count": strategy_count,
        }
        tool_context.actions.escalate = True
        tool_context.actions.skip_summarization = True
        self.log("selection", **s["selection"])
        return s["selection"]
