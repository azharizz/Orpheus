from google.adk.tools import ToolContext
from . import arrangement
import hashlib
import json
from .projects import media
from .workflow_common import MAX_BATCH_MAPPING_ROWS


class MappingTools:
    def save_arrangement(self, rows_json: str, tool_context: ToolContext) -> dict:
        """Save or replace the COMPLETE mixed arrangement before source fitting/render_arrangement; retain rows you still need. rows_json is a non-empty JSON array, <=100 rows. Required row keys: id,target_id,source_id,target_range_s,source_range_s,kind,anchor,disposition,confidence,evidence. Optional: target_anchor_s,source_anchor_s,gain_db,fade_in_s,fade_out_s,repeat,crossfade_s,reuse_reason,after,shape,target_body_dbfs. Copy current audio inventory IDs, not detector/sample IDs. Ranges are independent global target/source seconds. Used impacts remain provisional until fit and temporal receipts exist. Returns saved arrangement id/rows or error; a successful fit later updates these rows automatically."""
        try:
            if not isinstance(rows_json, str) or not rows_json.strip():
                tool_context.state["empty_arrangement_attempts"] = (
                    tool_context.state.get("empty_arrangement_attempts", 0) + 1
                )
                current = tool_context.state.get("arrangement")
                if isinstance(current, dict) and current.get("rows"):
                    ids = [r["id"] for r in current["rows"] if r.get("id")]
                    return {
                        "error": "rows_json is empty; existing arrangement is unchanged.",
                        "existing_arrangement_id": current.get("id"),
                        "mapping_ids": ids[:20],
                        "mapping_context": self.mapping_context(tool_context),
                        "next_step": "Call inspect_mapping_source with a mapping_id, then fit_mapping_impact for a discrete impact; or render_arrangement if no fitting change is supported.",
                        "recovery": "Do not repeat this empty call.",
                    }
                return {
                    "error": "rows_json is empty. Supply a JSON array of mapping objects, not an empty string.",
                    "existing_arrangement": tool_context.state.get("arrangement"),
                    "recovery": 'For unchanged mapping use render_arrangement directly. To change gain copy existing rows and edit gain_db. If unable, finish unsuitable with candidate_id="".',
                }
            rows = json.loads(rows_json)
            result = arrangement.bind(
                rows, self.case, tool_context.state.get("audio_evidence", {})
            )
        except (ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            return {"error": str(exc)[:400]}
        self.retain_evidence_receipts(tool_context.state, result)
        tool_context.state["arrangement"] = result
        from .projects import atomic

        atomic(self.folder / ("arrangement-" + result["id"] + ".json"), result)
        self.log("arrangement_saved", arrangement=result)
        return result

    def stage_action(
        self, mapping_id: str, phases_json: str, tool_context: ToolContext
    ) -> dict:
        """Split ONE saved used composite into 2..12 independently anchored phases, retaining other rows. Call when a composite has distinct attack/body/transition stages, not for every peak. phases_json objects require exactly kind (impact/texture/composite), target_range_s, source_range_s, target_anchor_s, source_anchor_s, evidence. Ranges must stay inside parent ranges. Explicit chronology, no global stretch. Atomic validation/save; then inspect_mapping_sources and fit_mapping_impacts for new impact rows and review temporal evidence before render. Returns context with generated row IDs; does not render or approve."""
        try:
            rows = arrangement.stage_rows(
                tool_context.state.get("arrangement", {}).get("rows", []),
                mapping_id,
                json.loads(phases_json),
            )
            result = self.save_arrangement(json.dumps(rows), tool_context)
            if "error" in result:
                return result
            return self.mapping_context(tool_context)
        except (ValueError, TypeError, KeyError) as exc:
            return {"error": str(exc)[:400]}

    def render_arrangement(self, hypothesis: str, tool_context: ToolContext) -> dict:
        """Render the saved mixed arrangement only after every used impact has current contact/source anchors, fit receipt, delivered frames and target/uncertain review. MUST use for a mapped candidate; hypothesis describes the supported change (1..1000 characters). One render per cycle. Returns candidate id and measurements, not artistic approval. MUST call measure_candidate with that id at the next opportunity; on gate error repair named rows before retrying."""
        s = tool_context.state
        if not isinstance(hypothesis, str) or not 1 <= len(hypothesis) <= 1000:
            return {"error": "Hypothesis 1..1000 characters required"}
        if s.get("rendered"):
            return {"error": "Already rendered this cycle; end response to advance"}
        if not s.get("arrangement"):
            return {"error": "Save arrangement first using current inventory IDs"}
        gate = self.impact_gate(s)
        if gate:
            return gate
        try:
            bound = arrangement.bind(
                s["arrangement"]["rows"],
                self.case,
                s.get("audio_evidence", {}),
                require_impact_anchors=True,
            )
            r = arrangement.render(self.case, bound, self.folder)
        except (ValueError, TypeError, KeyError) as exc:
            return {"error": str(exc)[:400]}
        return self.record_candidate(r, hypothesis, tool_context)

    def _inspect_mapping_source(self, mapping_id, tool_context):
        current = tool_context.state.get("arrangement", {})
        try:
            row = next((r for r in current.get("rows", []) if r["id"] == mapping_id))
            arrangement.bind(
                current["rows"], self.case, tool_context.state.get("audio_evidence", {})
            )
            result = arrangement.source_options(
                media.read_audio(self.case["sfx_path"]), *row["source_range_s"]
            )
            receipt_id = hashlib.sha256(
                json.dumps(
                    {
                        "mapping_id": mapping_id,
                        "source_signature": self.source_signature(row),
                        "options": result["options"],
                    },
                    sort_keys=True,
                ).encode()
            ).hexdigest()[:20]
            reviews = dict(tool_context.state.get("source_option_reviews", {}))
            reviews[mapping_id] = {
                "receipt_id": receipt_id,
                "mapping_id": mapping_id,
                "arrangement_id": current.get("id"),
                "source_signature": self.source_signature(row),
                "source_file_sha256": hashlib.sha256(
                    self.case["sfx_path"].read_bytes()
                ).hexdigest(),
                "source_range_s": row["source_range_s"],
                "options": result["options"],
            }
            tool_context.state["source_option_reviews"] = reviews
            return {**result, "inspection_receipt_id": receipt_id}
        except StopIteration:
            return {
                "error": "Unknown mapping ID; use a row ID, not arrangement ID",
                "valid_mapping_ids": [
                    r.get("id") for r in current.get("rows", []) if r.get("id")
                ],
                "arrangement_id": current.get("id"),
            }
        except (ValueError, KeyError, TypeError) as exc:
            return {"error": str(exc) or "Unknown mapping ID"}

    def inspect_mapping_source(
        self, mapping_id: str, tool_context: ToolContext
    ) -> dict:
        """Inspect source snippets for ONE saved mapping row ID before fitting that impact. Use for single-row work/recovery; prefer inspect_mapping_sources for several rows. Returns measured options with integer index, source anchor, body level and weak flag plus receipt. No fit is performed and suitability is not verified."""
        return self._inspect_mapping_source(mapping_id, tool_context)

    def inspect_mapping_sources(
        self, mapping_ids: list[str], tool_context: ToolContext
    ) -> dict:
        """Batch source inspection for 1..12 saved mapping row IDs before impact fitting. MUST inspect each used impact's current source range using this or inspect_mapping_source. Returns per-row options/receipts, succeeded, failed and mapping_context. Fit successful rows using their own option indices; repair failed rows separately."""
        if (
            not isinstance(mapping_ids, list)
            or not 1 <= len(mapping_ids) <= MAX_BATCH_MAPPING_ROWS
        ):
            return {
                "error": f"mapping_ids must contain 1..{MAX_BATCH_MAPPING_ROWS} row IDs"
            }
        if any(
            (
                not isinstance(mapping_id, str) or not mapping_id
                for mapping_id in mapping_ids
            )
        ):
            return {"error": "mapping_ids must contain non-empty row ID strings"}
        results = []
        succeeded = []
        failed = []
        seen = set()
        for mapping_id in mapping_ids:
            if mapping_id in seen:
                result = {"error": "Duplicate mapping ID in batch"}
            else:
                seen.add(mapping_id)
                result = self._inspect_mapping_source(mapping_id, tool_context)
            results.append({"mapping_id": mapping_id, **result})
            (failed if "error" in result else succeeded).append(mapping_id)
        return {
            "arrangement_id": self.mapping_context(tool_context).get("arrangement_id"),
            "results": results,
            "succeeded": succeeded,
            "failed": failed,
            "mapping_context": self.mapping_context(tool_context),
        }

    def _fit_mapping_impact(
        self, mapping_id, source_option, target_contact_s, reason, tool_context
    ):
        current = tool_context.state.get("arrangement")
        if not current:
            return {"error": "No saved arrangement"}
        if not isinstance(reason, str) or not 1 <= len(reason) <= 500:
            return {"error": "Reason 1..500 characters required"}
        try:
            row = next((r for r in current["rows"] if r["id"] == mapping_id))
            source_review = tool_context.state.get("source_option_reviews", {}).get(
                mapping_id
            )
            if not source_review or source_review.get(
                "source_signature"
            ) != self.source_signature(row):
                raise ValueError(
                    "Call inspect_mapping_source for this mapping before fit_mapping_impact"
                )
            fitted = arrangement.prepare_impact(
                row,
                media.read_audio(self.case["sfx_path"]),
                source_option,
                target_contact_s,
            )
            rows = [fitted if r["id"] == mapping_id else r for r in current["rows"]]
            result = self.save_arrangement(json.dumps(rows), tool_context)
            if "error" not in result:
                fitted_row = next((r for r in result["rows"] if r["id"] == mapping_id))
                fits = dict(tool_context.state.get("impact_fit_receipts", {}))
                fits[mapping_id] = {
                    "mapping_id": mapping_id,
                    "arrangement_id": result["id"],
                    "fit_signature": self.impact_signature(fitted_row),
                    "source_review_id": source_review["receipt_id"],
                    "source_option": source_option,
                    "target_contact_s": fitted_row["target_anchor_s"],
                    "source_landmark_s": fitted_row["source_anchor_s"],
                    "input_hashes": result["input_hashes"],
                }
                tool_context.state["impact_fit_receipts"] = fits
                self.log(
                    "mapping_revision",
                    previous_id=current["id"],
                    current_id=result["id"],
                    mapping_id=mapping_id,
                    reason=reason,
                    operation="automatic_impact_fit",
                    target_contact_s=fitted_row["target_anchor_s"],
                    source_landmark_s=fitted_row["source_anchor_s"],
                )
            return result
        except StopIteration:
            return {
                "error": "Unknown mapping ID; use a row ID, not arrangement ID",
                "valid_mapping_ids": [
                    r.get("id") for r in current.get("rows", []) if r.get("id")
                ],
                "arrangement_id": current.get("id"),
            }
        except (ValueError, KeyError, TypeError) as exc:
            return {"error": str(exc) or "Unknown mapping ID"}

    def fit_mapping_impact(
        self,
        mapping_id: str,
        source_option: int,
        target_contact_s: float,
        reason: str,
        tool_context: ToolContext,
    ) -> dict:
        """Fit ONE saved used-impact row after source inspection. mapping_id is a row ID; source_option is its inspected integer option index; target_contact_s is an independently supported target time; reason is 1..500 characters. Updates saved crop/anchors, balances body and records fit evidence. Use fit_mapping_impacts for several rows. Success is a saved arrangement, not a rendered candidate."""
        return self._fit_mapping_impact(
            mapping_id, source_option, target_contact_s, reason, tool_context
        )

    def fit_mapping_impacts(self, fits_json: str, tool_context: ToolContext) -> dict:
        """Batch-fit 1..12 saved used impacts after their source inspections. fits_json is a JSON array with exactly mapping_id,source_option,target_contact_s,reason per object. MUST fit each used impact via this or fit_mapping_impact before rendering. Returns per-row fit_recorded, succeeded/failed and current context; successful rows are already saved. Do not overwrite them with provisional rows or assume failed rows were fitted."""
        try:
            specs = json.loads(fits_json)
            if (
                not isinstance(specs, list)
                or not 1 <= len(specs) <= MAX_BATCH_MAPPING_ROWS
            ):
                return {
                    "error": f"fits_json must be a JSON array of 1..{MAX_BATCH_MAPPING_ROWS} fit specs"
                }
        except (TypeError, json.JSONDecodeError) as exc:
            return {"error": "fits_json must be valid JSON: " + str(exc)[:160]}
        results = []
        succeeded = []
        failed = []
        seen = set()
        required = {"mapping_id", "source_option", "target_contact_s", "reason"}
        for spec in specs:
            mapping_id = spec.get("mapping_id") if isinstance(spec, dict) else None
            if (
                not isinstance(spec, dict)
                or set(spec) != required
                or (not isinstance(mapping_id, str))
                or (not mapping_id)
            ):
                result = {
                    "error": "Each fit spec needs exactly mapping_id, source_option, target_contact_s, reason"
                }
            elif mapping_id in seen:
                result = {"error": "Duplicate mapping ID in batch"}
            else:
                seen.add(mapping_id)
                result = self._fit_mapping_impact(
                    spec["mapping_id"],
                    spec["source_option"],
                    spec["target_contact_s"],
                    spec["reason"],
                    tool_context,
                )
            if "error" in result:
                results.append({"mapping_id": mapping_id, **result})
                failed.append(mapping_id)
            else:
                row = next(
                    (
                        r
                        for r in tool_context.state["arrangement"]["rows"]
                        if r["id"] == mapping_id
                    )
                )
                results.append(
                    {
                        "mapping_id": mapping_id,
                        "arrangement_id": result["id"],
                        "target_anchor_s": row.get("target_anchor_s"),
                        "source_anchor_s": row.get("source_anchor_s"),
                        "source_review_id": tool_context.state["impact_fit_receipts"][
                            mapping_id
                        ].get("source_review_id"),
                        "fit_recorded": True,
                    }
                )
                succeeded.append(mapping_id)
        return {
            "arrangement_id": self.mapping_context(tool_context).get("arrangement_id"),
            "results": results,
            "succeeded": succeeded,
            "failed": failed,
            "mapping_context": self.mapping_context(tool_context),
        }

    def revise_mapping_gain(
        self, mapping_id: str, gain_db: float, reason: str, tool_context: ToolContext
    ) -> dict:
        """Optionally change gain (-30..24 dB) for one saved mapping row after measurements show a level defect. reason is 1..500 characters. Preserves its timing/source evidence and saves the arrangement; does not render. Next render_arrangement and measure_candidate. Gain cannot fix missing actions, wrong source or timing."""
        current = tool_context.state.get("arrangement")
        if not current:
            return {"error": "No saved arrangement"}
        if not isinstance(reason, str) or not 1 <= len(reason) <= 500:
            return {"error": "Revision reason 1..500 characters required"}
        if mapping_id not in [r["id"] for r in current["rows"]]:
            return {
                "error": "Unknown mapping ID",
                "valid_ids": [r["id"] for r in current["rows"]],
            }
        rows = [
            {**r, "gain_db": gain_db} if r["id"] == mapping_id else r
            for r in current["rows"]
        ]
        result = self.save_arrangement(json.dumps(rows), tool_context)
        if "error" not in result:
            self.log(
                "mapping_revision",
                previous_id=current["id"],
                current_id=result["id"],
                mapping_id=mapping_id,
                reason=reason,
            )
        return result
