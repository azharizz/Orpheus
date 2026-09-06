from google.adk.tools import ToolContext
from .projects import ff
from . import fitting
from .projects import frames
import hashlib
import json
from .projects import media
from . import perception
import subprocess
from .workflow_common import MAX_ADAPTIVE_FRAMES_PER_CALL, MAX_ADAPTIVE_FRAMES_PER_TURN, MAX_AUDIO_REVIEWS, MAX_REVIEW_BATCH_CENTERS, MAX_REVIEW_CENTERS_PER_CYCLE, MAX_REVIEW_CENTERS_PER_TURN, MAX_WAVEFORM_CALLS, inspection_scope


class PerceptionTools:
    async def inspect_audio(
        self, role: str, start_s: float, end_s: float, tool_context: ToolContext
    ) -> dict:
        """Independently analyze one audio window via the separate audio model. When enabled, MUST attempt target and source after initial visual review and before planning a new replacement. role is target/source; start_s/end_s use that file's global seconds, <=30s available. Returns status and inventory IDs with global ranges; do not add the window offset again. On failure, use disclosed signal fallback rather than invented IDs."""
        result = await self.audio.inspect(role, start_s, end_s)
        s = tool_context.state
        if role in ("target", "source"):
            s["audio_attempts"] = {
                **s.get("audio_attempts", {}),
                role: result["status"],
            }
        if result["status"] == "ok":
            evidences = dict(s.get("audio_evidence", {}))
            ident = result["evidence_id"]
            previous = list(evidences.values())
            evidences[ident] = result
            s["audio_evidence"] = evidences
            report = perception.reconcile(
                result, [], [x for x in previous if x["evidence_id"] != ident]
            )
            s["audio_reconciliations"] = {
                **s.get("audio_reconciliations", {}),
                ident: report,
            }
            self.log("audio_reconciliation", **report)
            return {
                k: v
                for k, v in result.items()
                if k not in ("measurements", "raw_observation")
            } | {"reconciliation": report}
        return result

    def inventory_status(self, tool_context: ToolContext) -> dict:
        """Read available audio inventories, their exact IDs, and uninspected ranges. Use when IDs/coverage are unclear or stale, not repeatedly when inspect_audio already returned the needed evidence. Historical inventories may need refreshing before binding. Gaps are unresolved, not silence."""
        s = tool_context.state
        out = {}
        for role, path in [
            ("target", self.case["original_path"]),
            ("source", self.case["sfx_path"]),
        ]:
            sha = hashlib.sha256(path.read_bytes()).hexdigest()
            available = min(30, len(media.read_audio(path)) / media.RATE)
            duration = self.case["seconds"] if role == "target" else available
            current = [
                x
                for x in s.get("audio_evidence", {}).values()
                if x["receipt"]["role"] == role and x["receipt"]["file_sha256"] == sha
            ]
            out[role] = {
                "file_sha256": sha,
                "duration_s": duration,
                "available_audio_duration_s": available,
                "evidence_ids": [x["evidence_id"] for x in current],
                "uninspected_ranges_s": perception.gaps(
                    [(x["receipt"]["start_s"], x["receipt"]["end_s"]) for x in current],
                    0,
                    duration,
                ),
                "inventories": [x["inventory"] for x in current],
                "warning": "Overlapping revisions retained, not merged into verified events. Uninspected and unknown regions are not silence.",
            }
        return {"audio": self.audio.availability(), "roles": out}

    def inspect_signal(
        self, role: str, start_s: float, end_s: float, tool_context: ToolContext
    ) -> dict:
        """Measure one target OR source audio window to resolve a specific signal question. Optional; start_s/end_s are global seconds in the selected role's file, with duration 0.02..3s and six windows per turn. Returns file identity and measured levels/envelope; no semantic classification or edits."""
        s = tool_context.state
        try:
            if s.get("signal_calls", 0) >= 6:
                raise ValueError("Six signal windows per turn maximum")
            perception.finite(end_s - start_s, 0.02, 3)
            receipt, _, samples = perception.window(self.case, role, start_s, end_s)
            result = {
                "receipt": receipt,
                "measurements": perception.measurements(samples, receipt),
            }
            s["signal_calls"] = s.get("signal_calls", 0) + 1
            self.log("signal_window", **result)
            return result
        except (ValueError, TypeError) as exc:
            return {"error": str(exc)[:200]}

    def review_window(
        self,
        start_s: float,
        end_s: float,
        step_s: float,
        crop: list[float],
        tool_context: ToolContext,
    ) -> dict:
        """Queue target frames with original-audio envelope, overlapping rows and current mapping receipts in one local review packet. MUST request initial visual review after inspect_scene and receive frames on the NEXT model request before defining mappings; also use for ambiguous transitions. crop=[] or normalized [x,y,width,height]. step_s 1/120..0.5, <=24 frames/call,96/turn; end_s <= duration-0.001. A receipt means queued images, not completed interpretation. Original-audio levels do not measure rendered output."""
        s = tool_context.state
        try:
            perception.finite(start_s, 0, self.case["seconds"] - 0.01)
            perception.finite(end_s, start_s + 0.001, self.case["seconds"] - 0.001)
            perception.finite(step_s, 1 / 120, 0.5)
            if crop:
                if len(crop) != 4:
                    raise ValueError("Crop needs x,y,width,height")
                for v in crop:
                    perception.finite(v, 0, 1)
                if (
                    crop[2] <= 0
                    or crop[3] <= 0
                    or crop[0] + crop[2] > 1
                    or (crop[1] + crop[3] > 1)
                ):
                    raise ValueError("Invalid crop bounds")
            count = int((end_s - start_s) / step_s) + 1
            if (
                not 1 <= count <= MAX_ADAPTIVE_FRAMES_PER_CALL
                or s.get("adaptive_frames", 0) + count > MAX_ADAPTIVE_FRAMES_PER_TURN
            ):
                raise ValueError(
                    f"{MAX_ADAPTIVE_FRAMES_PER_CALL} frames/call,{MAX_ADAPTIVE_FRAMES_PER_TURN}/turn maximum"
                )
            images = frames(
                self.case,
                [start_s + i * step_s for i in range(count)],
                self.folder / "frames",
            )
            if crop:
                cropped = []
                for t, path in images:
                    x, y, cw, ch = crop
                    dest = path.with_name(
                        path.stem
                        + "-"
                        + hashlib.sha256(json.dumps(crop).encode()).hexdigest()[:8]
                        + ".jpg"
                    )
                    ff(
                        "-i",
                        path,
                        "-vf",
                        f"crop=iw*{cw}:ih*{ch}:iw*{x}:ih*{y}",
                        "-frames:v",
                        1,
                        "-threads",
                        1,
                        dest,
                    )
                    cropped.append((t, dest))
                images = cropped
            receipt = {
                "video_sha256": hashlib.sha256(
                    self.case["video_path"].read_bytes()
                ).hexdigest(),
                "requested_window_s": [start_s, end_s],
                "step_s": step_s,
                "crop": crop,
                "frames": [
                    {"time_s": t, "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
                    for t, p in images
                ],
            }
            receipt["id"] = hashlib.sha256(
                json.dumps(receipt, sort_keys=True).encode()
            ).hexdigest()[:20]
            self.pending.extend(images)
            self.pending_receipts.append(receipt)
            s["adaptive_frames"] = s.get("adaptive_frames", 0) + count
            self.log("adaptive_frames", **receipt)
            local = None
            if end_s - start_s >= 0.02:
                try:
                    signal_receipt, _, samples = perception.window(
                        self.case, "target", start_s, end_s
                    )
                    local = perception.measurements(samples, signal_receipt)
                except (ValueError, OSError) as exc:
                    local = {"status": "unavailable", "error_type": type(exc).__name__}
            overlapping = [
                r
                for r in s.get("arrangement", {}).get("rows", [])
                if r["target_range_s"][0] < end_s and r["target_range_s"][1] > start_s
            ]
            return {
                "receipt": receipt,
                "target_signal": local,
                "overlapping_rows": overlapping,
                "mapping_context": self.mapping_context(tool_context),
                "warning": "Frames delivered next model call. Signal is original target audio, not a rendered candidate. Cropped target picture only; no source picture. Frame spacing is not timing certainty.",
            }
        except ValueError as exc:
            return {
                "error": str(exc)[:200],
                "recovery": f"Use 0 <= start < end <= {self.case['seconds'] - 0.001:.3f}, step .008334..0.5, at most {MAX_ADAPTIVE_FRAMES_PER_CALL} frames/call and {MAX_ADAPTIVE_FRAMES_PER_TURN}/turn. Split a long clip into windows <= {MAX_ADAPTIVE_FRAMES_PER_CALL - 1}*step seconds. crop=[] or normalized [x,y,w,h], not pixels.",
            }
        except (OSError, subprocess.SubprocessError) as exc:
            return {
                "error": type(exc).__name__,
                "warning": "Frame extraction failed; use current evidence provisionally or finish unsuitable.",
            }

    def reconcile_audio(
        self, evidence_id: str, reviews_json: str, tool_context: ToolContext
    ) -> dict:
        """Optionally compare audio hypotheses with cited observations; unresolved conflicts do not block previews. reviews_json is a JSON array (<=20) with exactly event_id,kind,onset_range_s,observation plus frame_receipt_id for target OR audio_evidence_id for source. Cite delivered target frames or inspected same-source audio. Ranges are global within the citation; [] recomputes only. Does not satisfy the impact fit/review gate."""
        s = tool_context.state
        try:
            evidence = s.get("audio_evidence", {}).get(evidence_id)
            if not evidence:
                raise ValueError("Unknown evidence ID")
            r = evidence["receipt"]
            path = (
                self.case["original_path"]
                if r["role"] == "target"
                else self.case["sfx_path"]
            )
            if hashlib.sha256(path.read_bytes()).hexdigest() != r["file_sha256"]:
                raise ValueError("Stale audio evidence")
            rows = json.loads(reviews_json)
            if not isinstance(rows, list) or len(rows) > MAX_AUDIO_REVIEWS:
                raise ValueError(f"At most {MAX_AUDIO_REVIEWS} reviews")
            records = []
            event_ids = {e["id"] for e in evidence["inventory"]["events"]}
            for row in rows:
                citation = (
                    "audio_evidence_id" if r["role"] == "source" else "frame_receipt_id"
                )
                if not isinstance(row, dict) or set(row) != {
                    "event_id",
                    citation,
                    "kind",
                    "onset_range_s",
                    "observation",
                }:
                    raise ValueError(
                        "Review requires event_id,kind,onset_range_s,observation and "
                        + citation
                    )
                if row["event_id"] not in event_ids:
                    raise ValueError("Unknown event for this evidence ID")
                if r["role"] == "source":
                    cited = s.get("audio_evidence", {}).get(row[citation])
                    if (
                        not cited
                        or cited["receipt"]["role"] != "source"
                        or cited["receipt"]["file_sha256"] != r["file_sha256"]
                    ):
                        raise ValueError(
                            "Source review requires inspected same-source audio evidence"
                        )
                    times = [cited["receipt"]["start_s"], cited["receipt"]["end_s"]]
                    provenance = "controller_audio_hypothesis"
                else:
                    frame = next(
                        (
                            x
                            for x in s.get("delivered_frame_receipts", [])
                            if x["id"] == row[citation]
                        ),
                        None,
                    )
                    if (
                        not frame
                        or frame["video_sha256"]
                        != hashlib.sha256(
                            self.case["video_path"].read_bytes()
                        ).hexdigest()
                    ):
                        raise ValueError("Undelivered/stale frame citation")
                    times = [x["time_s"] for x in frame["frames"]]
                    provenance = "controller_visual_hypothesis"
                if row["kind"] not in (
                    "impulse",
                    "texture",
                    "composite",
                    "transition",
                    "pause",
                    "unknown",
                ):
                    raise ValueError("Invalid kind")
                v = row["onset_range_s"]
                if not isinstance(v, list) or len(v) != 2:
                    raise ValueError("Onset interval required")
                perception.finite(v[0], min(times), max(times))
                perception.finite(v[1], v[0], max(times))
                if (
                    not isinstance(row["observation"], str)
                    or not 1 <= len(row["observation"]) <= 500
                ):
                    raise ValueError("Invalid observation")
                records.append(
                    {
                        **row,
                        "id": hashlib.sha256(
                            json.dumps(row, sort_keys=True).encode()
                        ).hexdigest()[:20],
                        "provenance": provenance,
                        "verified": False,
                    }
                )
            s["inventory_reviews"] = [*s.get("inventory_reviews", []), *records]
            report = perception.reconcile(
                evidence,
                s["inventory_reviews"],
                [x for k, x in s["audio_evidence"].items() if k != evidence_id],
            )
            old = s.get("audio_reconciliations", {}).get(evidence_id)
            self.log(
                "reconciliation_revision",
                previous=old,
                visual_observations=[
                    v
                    for v in records
                    if v["provenance"] == "controller_visual_hypothesis"
                ],
                audio_observations=[
                    v
                    for v in records
                    if v["provenance"] == "controller_audio_hypothesis"
                ],
                current=report,
            )
            s["audio_reconciliations"] = {
                **s.get("audio_reconciliations", {}),
                evidence_id: report,
            }
            return report
        except (ValueError, TypeError, KeyError) as exc:
            return {"error": str(exc)[:200]}

    def inspect_scene(self, tool_context: ToolContext) -> dict:
        """MUST call at the start of a turn before choosing edits. Read duration, full-window audio measurements, acoustic candidates, integer source_bank IDs, motion statistics, and saved project context. These are candidate signals, not verified actions. Next request review_window and wait for its frames before defining events."""
        tool_context.state["inspected"] = True
        events = fitting.candidates(self.case)
        source_bank = fitting.bank(self.case)
        target_ids = [e["id"] for e in events]
        source_ids = [str(e["id"]) for e in source_bank]
        return {
            "duration_s": self.case["seconds"],
            "context": self.case["context"],
            "desired_sound": self.case["style"],
            "original": media.analyse(self.case["original_path"]),
            "source": media.analyse(self.case["sfx_path"]),
            "audio_perception": self.audio.availability(),
            "events": events,
            "motion_evidence": fitting.motion_evidence(self.case),
            "source_bank": source_bank,
            "inspection_scope": inspection_scope(
                len(events),
                len(source_bank),
                len(tool_context.state.get("candidates", [])),
                len(tool_context.state.get("notes", [])),
            ),
            "input_warnings": self.case.get("input_warnings", []),
            "target_event_ids": target_ids,
            "source_sample_ids": source_ids,
            "saved_arrangement": tool_context.state.get("arrangement", []),
            "saved_plan": tool_context.state.get("plan", []),
            "memory": tool_context.state.get("notes", []),
            "mapping_context": self.mapping_context(tool_context),
            "previous_candidates": [
                {
                    k: c.get(k)
                    for k in (
                        "id",
                        "render_mode",
                        "audio_sha256",
                        "metrics",
                        "flags",
                        "hypothesis",
                    )
                }
                for c in tool_context.state.get("candidates", [])[-8:]
            ],
        }

    def review_moments(self, centers_s: list[float], tool_context: ToolContext) -> dict:
        """Queue before/at/after target frames and attack profiles for 1..5 centers_s. REQUIRED for fallback discrete-plan events; optional alternative local review for mapped impacts. Frames arrive next model request. Then record_review_batch or record_event_review for ALL pending centers before another batch. Limits: 20 centers/cycle,100/turn. Request success is not a recorded verdict."""
        s = tool_context.state
        if s.get("pending_verdicts"):
            return {
                "error": "Record verdicts for the previous batch first",
                "centers": s["pending_verdicts"],
            }
        if not 1 <= len(centers_s) <= MAX_REVIEW_BATCH_CENTERS:
            return {"error": f"1..{MAX_REVIEW_BATCH_CENTERS} centers per call"}
        if s.get("cycle_reviews", 0) + len(centers_s) > MAX_REVIEW_CENTERS_PER_CYCLE:
            return {
                "error": "Cycle inspection budget reached. Save a provisional reviewed plan and render now; disclose incomplete coverage."
            }
        if len(s.get("reviewed", [])) + len(centers_s) > MAX_REVIEW_CENTERS_PER_TURN:
            return {
                "error": f"{MAX_REVIEW_CENTERS_PER_TURN}-center per-turn budget exhausted"
            }
        try:
            for t in centers_s:
                fitting.bounded(t, 0, self.case["seconds"] - 0.01, "center")
            times = sorted(
                {
                    round(max(0, min(self.case["seconds"] - 0.01, t + d)), 4)
                    for t in centers_s
                    for d in (-0.1, 0, 0.1)
                }
            )
            images = frames(self.case, times, self.folder / "frames")
            self.pending.extend(images)
        except (ValueError, OSError, subprocess.SubprocessError) as exc:
            return {"error": "Frame extraction failed: " + type(exc).__name__}
        s["reviewed"] = [*s.get("reviewed", []), *centers_s]
        s["cycle_reviews"] = s.get("cycle_reviews", 0) + len(centers_s)
        s["pending_verdicts"] = list(centers_s)
        actual = [t for t, p in images]
        self.log("temporal_review", centers=centers_s, frames=actual)
        return {
            "centers": centers_s,
            "timestamps": actual,
            "attack_profiles": [
                fitting.waveform_profile(self.case, t) for t in centers_s
            ],
            "warning": "Actual decoded-frame timestamps. Describe temporal transitions, not isolated poses. Ambiguity remains.",
        }

    def waveform_profile(self, center_s: float, tool_context: ToolContext) -> dict:
        """Optionally inspect a 300ms TARGET audio attack profile around center_s to refine a specific event. At most 20 calls/cycle; reuse attack profiles returned by review_moments when adequate. Returns measured peaks with target file identity, not physical-contact labels. For source use inspect_signal(role=source)."""
        s = tool_context.state
        if s.get("waveform_calls", 0) >= MAX_WAVEFORM_CALLS:
            return {
                "error": "Use attack profiles already returned with frame reviews; save and render a provisional plan."
            }
        s["waveform_calls"] = s.get("waveform_calls", 0) + 1
        try:
            return fitting.waveform_profile(self.case, center_s) | {
                "role": "target",
                "file_sha256": hashlib.sha256(
                    self.case["original_path"].read_bytes()
                ).hexdigest(),
                "warning": "TARGET original audio only. For source use inspect_signal(role=source). Not a semantic classifier.",
            }
        except ValueError as exc:
            return {"error": str(exc)}

    def record_event_review(
        self, center_s: float, verdict: str, observation: str, tool_context: ToolContext
    ) -> dict:
        """Record ONE verdict only AFTER relevant frames were delivered. center_s must be within 0.05s of a delivered center; verdict is target/non_target/uncertain, observation 1..400 characters. REQUIRED for used mapped impacts and fallback planned events, individually or via record_review_batch. Returns saved review; uncertainty remains a hypothesis and non_target cannot justify a rendered impact."""
        if verdict not in ("target", "non_target", "uncertain"):
            return {"error": "verdict must be target, non_target or uncertain"}
        if not isinstance(observation, str) or not 1 <= len(observation) <= 400:
            return {"error": "observation 1..400 chars"}
        s = tool_context.state
        try:
            fitting.bounded(center_s, 0, self.case["seconds"] - 0.01, "center_s")
        except ValueError as exc:
            return {"error": str(exc)}
        if not any((abs(center_s - t) <= 0.05 for t in s.get("delivered_centers", []))):
            return {"error": "Review images must be delivered to the model first"}
        s["event_reviews"] = [
            *s.get("event_reviews", []),
            {"center_s": center_s, "verdict": verdict, "observation": observation},
        ]
        s["pending_verdicts"] = [
            t for t in s.get("pending_verdicts", []) if abs(t - center_s) > 0.05
        ]
        self.log(
            "event_review", center_s=center_s, verdict=verdict, observation=observation
        )
        return {"saved": True, "review": s["event_reviews"][-1]}

    def record_review_batch(self, reviews_json: str, tool_context: ToolContext) -> dict:
        """Record 1..5 event verdicts AFTER frames arrive; complete all pending review_moments centers before another batch. reviews_json is an array with exactly center_s,verdict,observation per object. Calls record_event_review for each; MUST inspect every returned result because some rows can fail. Also usable to batch mapped-impact verdicts."""
        import json

        try:
            rows = json.loads(reviews_json)
            if (
                not isinstance(rows, list)
                or not 1 <= len(rows) <= MAX_REVIEW_BATCH_CENTERS
            ):
                raise ValueError(f"Provide 1..{MAX_REVIEW_BATCH_CENTERS} reviews")
            if any(
                (
                    not isinstance(r, dict)
                    or set(r) != {"center_s", "verdict", "observation"}
                    for r in rows
                )
            ):
                raise ValueError("Each review needs center_s, verdict, observation")
            return {
                "results": [
                    self.record_event_review(**r, tool_context=tool_context)
                    for r in rows
                ]
            }
        except (ValueError, TypeError) as exc:
            return {"error": str(exc)[:400]}
