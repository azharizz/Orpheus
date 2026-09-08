import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from orpheus.domain import projects


class Foundation(unittest.TestCase):
    def test_preparation_preserves_full_video_and_discloses_no_audio(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            video = folder / "target.mp4"
            projects.ff(
                "-f",
                "lavfi",
                "-i",
                "color=s=64x64:r=5",
                "-t",
                0.6,
                "-c:v",
                "libx264",
                video,
            )
            with patch.object(projects, "PROJECTS", folder / "projects"):
                p = projects.create(video)
            self.assertFalse(p["preparation"]["video_truncated"])
            self.assertIn("no_original_audio", p["input_warnings"])
            self.assertIn("mono_analysis_copy", p["input_warnings"])
            original = folder / "projects" / p["id"] / p["preparation"]["original_files"]["video"]
            self.assertEqual(original.read_bytes(), video.read_bytes())

    def test_initialization_failure_is_persisted(self):
        import asyncio
        import json

        from orpheus.server import worker

        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            doc = {"id": "a" * 16, "status": "ready", "turns": []}
            projects.atomic(folder / "project.json", doc)
            with (
                patch.object(worker, "load", return_value=doc),
                patch.object(worker.family_agent, "load_case", return_value=doc),
                patch.object(worker, "project_dir", return_value=folder),
                patch.object(
                    worker, "session_service", side_effect=RuntimeError("secret")
                ),
            ):
                result = asyncio.run(worker.run_turn("a" * 16, "b" * 12, "test"))
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["failure"]["phase"], "session_initialization")
            self.assertEqual(
                json.loads((folder / "project.json").read_text())["status"], "failed"
            )
            self.assertNotIn("secret", (folder / "events.jsonl").read_text())

    def test_orphaned_turn_recovery(self):
        import json

        from orpheus.server import worker

        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            doc = {"id": "a" * 16, "status": "running", "turns": ["b" * 12]}
            projects.atomic(folder / "project.json", doc)
            with (
                patch.object(worker, "load", return_value=doc),
                patch.object(worker, "project_dir", return_value=folder),
            ):
                worker.recover_orphaned_turns("a" * 16)
            self.assertEqual(
                json.loads((folder / ("b" * 12 + "-turn.json")).read_text())["status"],
                "interrupted",
            )
            self.assertEqual(
                json.loads((folder / "project.json").read_text())["status"],
                "interrupted",
            )

    def test_cleanup_failure_is_persisted(self):
        import asyncio
        import json
        from unittest.mock import AsyncMock

        from orpheus.server import worker

        service = AsyncMock()
        service.get_session.side_effect = ValueError("secret")
        service.close.side_effect = RuntimeError("secret")
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            doc = {
                "id": "a" * 16,
                "status": "ready",
                "turns": [],
                "prepared_hashes": {},
            }
            projects.atomic(folder / "project.json", doc)
            with (
                patch.object(worker, "load", return_value=doc),
                patch.object(worker.family_agent, "load_case", return_value=doc),
                patch.object(worker, "project_dir", return_value=folder),
                patch.object(worker, "session_service", return_value=service),
            ):
                result = asyncio.run(worker.run_turn("a" * 16, "b" * 12, "test"))
            self.assertEqual(result["failure"]["phase"], "cleanup")
            self.assertEqual(result["status"], "failed")
            self.assertEqual(
                json.loads((folder / "project.json").read_text())["status"], "failed"
            )
            self.assertNotIn("secret", str(result))

    def test_oversized_summaries_are_rejected_before_work(self):
        from types import SimpleNamespace

        from orpheus.agent.workflow import build

        with tempfile.TemporaryDirectory() as d:
            agent = build({}, Path(d), lambda *a, **k: None)
            tools = {t.__name__: t for t in agent.sub_agents[0].tools}
            ctx = SimpleNamespace(state={})
            self.assertIn(
                "error", tools["render_plan"](-22, "balanced", "x" * 1001, ctx)
            )
            self.assertIn(
                "error", tools["finish"]("", "unsuitable", "x" * 3001, [], ctx)
            )
            self.assertIn(
                "error", tools["finish"]("", "unsuitable", "reason", ["x"] * 16, ctx)
            )

    def test_agent_render_and_selection_require_grafana_evidence(self):
        from types import SimpleNamespace

        from orpheus.agent.workflow import EditorTools

        runtime = EditorTools({}, Path(tempfile.gettempdir()), lambda *a, **k: None)
        state = {
            "grafana_receipts": {},
            "candidates": [{
                "id": "b" * 12,
                "audio_sha256": "c" * 64,
                "engineering_pass": True,
                "strategy": {"key": "one"},
            }],
            "turn_renders": 1,
            "deterministic_baseline": {"id": "d" * 12},
            "candidate_measurements": {"b" * 12: {"timing_status": "measured"}},
        }
        context = SimpleNamespace(
            state=state,
            actions=SimpleNamespace(escalate=False, skip_summarization=False),
        )
        render = SimpleNamespace(name="render_arrangement")
        self.assertIn("error", runtime.before_tool(render, {}, context))
        state["grafana_receipts"]["history:"] = {
            "status": "ok", "evidence_count": 1, "receipt_id": "history"
        }
        self.assertIsNone(runtime.before_tool(render, {}, context))
        self.assertIn(
            "error",
            runtime.finish("b" * 12, "needs_human_review", "Compared", [], context),
        )
        state["grafana_receipts"]["sound:" + "b" * 12] = {
            "status": "ok", "evidence_count": 1, "receipt_id": "sound"
        }
        result = runtime.finish(
            "b" * 12, "needs_human_review", "Compared", [], context
        )
        self.assertEqual(result["baseline_candidate_id"], "d" * 12)
        self.assertEqual(result["grafana_evidence"]["sound"], "sound")

    def test_failure_categories_do_not_include_exception_text(self):
        from google.adk.agents.invocation_context import LlmCallsLimitExceededError

        from orpheus.server.worker import failure_info

        for exc, phase, expected in [
            (LlmCallsLimitExceededError("secret"), "agent", "model_call_budget"),
            (TimeoutError("secret"), "agent", "turn_timeout"),
            (subprocess.TimeoutExpired("secret", 1), "overview", "media_timeout"),
            (subprocess.CalledProcessError(1, "secret"), "agent", "media_processing"),
            (RuntimeError("secret"), "agent", "unexpected_failure"),
        ]:
            result = failure_info(exc, phase)
            self.assertEqual(result["category"], expected)
            self.assertNotIn("secret", str(result))
        self.assertEqual(
            failure_info(RuntimeError("secret"), "agent", True)["category"],
            "provider_failure",
        )

    def test_agent_progress_reports_a_real_phase_without_a_fake_percent(self):
        from orpheus.server.worker import progress_for_event

        turn = {"status": "running", "cycles": 2, "candidates": [{}]}
        progress = progress_for_event("tool_call", {"name": "inspect_grafana"}, turn)
        self.assertEqual(progress["phase"], "grafana")
        self.assertEqual(progress["candidate_count"], 1)
        self.assertNotIn("progress", progress)

    def test_inspection_discloses_limits(self):
        from orpheus.agent.workflow_common import inspection_scope

        result = inspection_scope(180, 180, 12, 9)
        self.assertTrue(result["candidate_cap_may_have_omitted_events"])
        self.assertEqual(result["audio_event_cap"], 100)
        self.assertEqual(result["source_option_cap"], 24)
        self.assertEqual(result["plan_row_limit"], 100)
        self.assertEqual(result["review_centers_per_cycle"], 20)
        self.assertEqual(result["review_centers_per_turn"], 100)
        self.assertEqual(result["previous_candidates_omitted_from_view"], 4)
        self.assertEqual(result["project_notes_in_view"], 9)
        self.assertFalse(
            inspection_scope(2, 3, 1, 0)["candidate_cap_may_have_omitted_events"]
        )


if __name__ == "__main__":
    unittest.main()
