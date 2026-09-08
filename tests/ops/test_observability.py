from tests.support import load_case

"Offline boundary checks; ORPHEUS_LIVE_MCP=1 additionally tests real local MCP in ADK."
import asyncio
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import httpx

from orpheus.domain import families, family_agent, projects, takes
from orpheus.ops import observability as o


class EvidenceChecks(unittest.TestCase):
    def test_part_contract_is_exact_and_events_carry_context(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(o, "STORE", Path(tmp)),
            patch.object(o, "DB", Path(tmp) / "db"),
            patch.object(o, "config", return_value={"enabled": True}),
        ):
            context = o.part_context("1234567890abcdef", family_id="abcdef123456", part_start_s=12, part_end_s=27)
            o.emit("1234567890abcdef", "candidate", {"id": "0123456789ab", **context, "metrics": {"clipped_samples": 0}})
            with o.connect() as db:
                row = json.loads(db.execute("SELECT payload FROM events").fetchone()[0])
            self.assertEqual(row["evidence_contract"], o.EVIDENCE_CONTRACT_SCHEMA)
            self.assertEqual(row["family_id"], "abcdef123456")
            self.assertEqual(row["part_start_s"], 12)
            with self.assertRaises(ValueError):
                o.part_context("1234567890abcdef", part_start_s=3, part_end_s=3)

    def test_config_repairs_legacy_dashboard_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            path = folder / "local.json"
            path.write_text(json.dumps({"dashboard_url": "http://127.0.0.1:13000/d/orpheus/foley-evidence"}))
            with patch.object(o, "CONFIG", path), patch.dict(os.environ, {}, clear=False):
                value = o.config()
            self.assertTrue(value["dashboard_url"].endswith("/d/orpheus/agentic-foley-control-room"))

    def test_project_metrics_compare_baseline_agent_and_review_state(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(o, "STORE", Path(tmp)),
            patch.object(o, "DB", Path(tmp) / "db"),
            patch.object(o, "config", return_value={"enabled": True}),
        ):
            pid = "1234567890abcdef"
            o.emit(pid, "deterministic_baseline", {"metrics": {
                "integrated_lufs": -26.2, "true_peak_dbtp": -0.5,
                "picture_unchanged": True, "clipped_samples": 0,
            }, "measurements": {"accepted_events": 9}}, timestamp=1000)
            o.emit(pid, "candidate", {"metrics": {
                "integrated_lufs": -28.4, "true_peak_dbtp": -4.3,
                "picture_unchanged": True, "clipped_samples": 0,
            }, "measurements": {"accepted_events": 9}})
            o.emit(pid, "selection", {"decision": "needs_human_review"})
            o.emit(pid, "human_review", {"verdict": "approve"})
            o.emit(pid, "tool_result", {"name": "render_arrangement", "response": {"status": "ok"}})
            o.emit(pid, "session_saved", {}, timestamp=1012.5)
            o.emit(pid, "movie_analysis", {"status": "review_required", "measurements": {"progress": 100, "events": 42, "suggestions": 3, "noise_regions": 2, "duration_s": 1800}})
            o.emit(pid, "family_movie_search", {"family_id": "footsteps", "matches": 20})
            metrics = o.metrics_text()
            self.assertIn(f'orpheus_baseline_integrated_lufs{{project_id="{pid}"}} -26.2', metrics)
            self.assertIn(f'orpheus_candidate_integrated_lufs{{project_id="{pid}"}} -28.4', metrics)
            self.assertIn(f'orpheus_project_candidate_state{{project_id="{pid}"}} 1', metrics)
            self.assertIn(f'orpheus_project_review_state{{project_id="{pid}"}} 1', metrics)
            self.assertIn(f'orpheus_project_run_state{{project_id="{pid}"}} 1', metrics)
            self.assertIn(f'orpheus_project_tool_events_total{{project_id="{pid}",tool="render_arrangement",outcome="completed"}} 1', metrics)
            self.assertIn(f'orpheus_movie_progress{{project_id="{pid}"}} 100', metrics)
            self.assertIn(f'orpheus_movie_events{{project_id="{pid}"}} 42', metrics)
            self.assertIn(f'orpheus_movie_suggestions{{project_id="{pid}"}} 3', metrics)

    def test_redaction_idempotence_outage_and_signal(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(o, "STORE", Path(tmp)),
            patch.object(o, "DB", Path(tmp) / "db"),
            patch.object(
                o,
                "config",
                return_value={
                    "loki_url": "http://127.0.0.1:1",
                    "tempo_url": "http://127.0.0.1:1",
                },
            ),
        ):
            fields = {
                "requested_model": "test/model",
                "prompt": "secret-credential",
                "response": {"error": "secret-credential"},
                "metrics": {"integrated_lufs": -23, "invalid": float("nan")},
                "source_path": "private.wav",
            }
            one = o.emit("1234567890abcdef", "tool_result", fields, "turn", 1000)
            self.assertEqual(
                one, o.emit("1234567890abcdef", "tool_result", fields, "turn", 1000)
            )
            self.assertEqual(o.pending(), 1)
            with o.connect() as db:
                raw = db.execute("SELECT payload FROM events").fetchone()[0]
            self.assertNotIn("secret", raw)
            self.assertNotIn("private", raw)
            self.assertNotIn("NaN", raw)
            self.assertTrue(json.loads(raw)["tool_error"])
            self.assertEqual(json.loads(raw)["outcome"], "failed")
            self.assertTrue(o.flush()["errors"])
            self.assertEqual(o.pending(), 1)
            profile = o.sound_profile(load_case()["sfx_path"])
            self.assertLessEqual(len(profile["envelope"]), 120)
            self.assertGreater(profile["duration_s"], 0)
            with self.assertRaises(ValueError):
                o.enqueue("../", "bad")
            with patch.object(
                httpx.Client,
                "post",
                return_value=httpx.Response(
                    204, request=httpx.Request("POST", "http://local")
                ),
            ):
                self.assertEqual(o.flush()["pending"], 0)

    @unittest.skipUnless(
        os.environ.get("ORPHEUS_LIVE_MCP") == "1",
        "Opt-in real local services; no paid model",
    )
    def test_real_adk_mcp_take_experiment(self):
        from google.adk.models.base_llm import BaseLlm
        from google.adk.models.llm_response import LlmResponse
        from google.adk.runners import Runner
        from google.adk.sessions import DatabaseSessionService
        from google.genai import types

        from orpheus.agent import workflow

        calls = []
        results = []
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch.object(projects, "PROJECTS", Path(tmp)),
        ):
            doc = projects.create(
                load_case()["video_path"],
                context="Synthetic controller integration; not a recorded human performance",
            )
            pid = doc["id"]
            families.build_index(pid)
            family = families.create(pid, "synthetic steps", [0.7, 1.1])
            source = load_case()["sfx_path"]
            before = hashlib.sha256(source.read_bytes()).hexdigest()
            first = takes.add_take(
                pid, source, "Imported existing SFX, validation fixture",
                family_id=family["id"],
            )
            takes.add_take(
                pid,
                source,
                "Same recording, storage comparison fixture; not an independent take",
                family_id=family["id"],
            )
            self.assertEqual(hashlib.sha256(source.read_bytes()).hexdigest(), before)
            proposal = {
                "take_id": first["id"],
                "change": "Move microphone farther away in the NEXT human recording",
                "expected_effect": "Test whether body level decreases; maintain recorder gain",
                "reason": "Controlled test proposal; identical fixture takes cannot establish perceptual improvement",
            }

            class Scripted(BaseLlm):
                model: str = "scripted-local-mcp-integration-no-provider"

                async def generate_content_async(self, llm_request, stream=False):
                    n = len(calls)
                    calls.append(n)
                    actions = [
                        ("query_grafana", {"topic": "takes", "candidate_id": ""}),
                        (
                            "propose_take_experiment",
                            {"proposal_json": json.dumps(proposal)},
                        ),
                        ("query_grafana", {"topic": "runtime", "candidate_id": ""}),
                    ]
                    if n < len(actions):
                        name, args = actions[n]
                        part = types.Part(
                            function_call=types.FunctionCall(
                                name=name, args=args, id=str(n)
                            )
                        )
                    else:
                        part = types.Part(
                            text="Integration complete. No sound-quality judgment."
                        )
                    yield LlmResponse(content=types.Content(role="model", parts=[part]))

            async def run():
                folder = projects.project_dir(pid)
                case = family_agent.load_case(pid, family["id"])
                service = DatabaseSessionService(
                    db_url="sqlite+aiosqlite:///" + str(Path(tmp) / "sessions.sqlite")
                )
                await service.create_session(
                    app_name="test",
                    user_id="local",
                    session_id="mcp",
                    state={"cycle": 0, "notes": []},
                )
                with patch.object(workflow, "ControllerModel", return_value=Scripted()):
                    agent = workflow.build(case, folder, lambda *a, **kw: None)
                runner = Runner(app_name="test", agent=agent, session_service=service)
                async for ev in runner.run_async(
                    user_id="local",
                    session_id="mcp",
                    new_message=types.Content(
                        role="user",
                        parts=[
                            types.Part(text="Verify MCP and one take proposal only.")
                        ],
                    ),
                ):
                    for part in ev.content.parts if ev.content else []:
                        if part.function_response:
                            results.append(
                                {
                                    "name": part.function_response.name,
                                    "response": part.function_response.response,
                                }
                            )
                session = await service.get_session(
                    app_name="test", user_id="local", session_id="mcp"
                )
                self.assertEqual(
                    session.state["grafana_receipts"]["takes:"]["status"], "ok"
                )
                self.assertGreaterEqual(
                    session.state["grafana_receipts"]["takes:"]["evidence_count"], 2
                )
                self.assertEqual(
                    session.state["grafana_receipts"]["runtime:"]["status"], "ok"
                )
                self.assertEqual(
                    len(list(projects.project_dir(pid).glob("*-experiment.json"))), 1
                )
                self.assertTrue(
                    all(("error" not in r["response"] for r in results)), results
                )
                await runner.close()
                await service.close()

            asyncio.run(run())
            (projects.ROOT / "diagnostics").mkdir(parents=True, exist_ok=True)
            projects.atomic(
                projects.ROOT / "diagnostics/LOCAL_GRAFANA_ADK_VERIFICATION.json",
                {
                    "controller": "scripted; no paid inference or quality claim",
                    "real_adk": True,
                    "real_official_mcp": True,
                    "family_scoped_fitting": True,
                    "original_preserved": True,
                    "tool_results": results,
                },
            )


if __name__ == "__main__":
    unittest.main()
