import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from google.adk.events import Event, EventActions
from google.adk.sessions import DatabaseSessionService

from orpheus.domain import fitting
from orpheus.domain.projects import create, ff, frames, project_dir
from tests.support import load_case


class Checks(unittest.TestCase):
    def test_expanded_plan_limit(self):
        self.assertEqual(fitting.MAX_PLAN_ROWS, 100)

    def test_paths(self):
        for name in ["../secret", "shoes", "a" * 17]:
            with self.assertRaises(ValueError):
                project_dir(name)

    def test_last_frame_boundary(self):
        case = load_case("shoes")
        with tempfile.TemporaryDirectory() as d:
            result = frames(case, [case["seconds"] - 0.001], Path(d))
            self.assertTrue(result[0][1].stat().st_size > 100)
            self.assertLess(result[0][0], case["seconds"])

    def test_ingest_bounds_and_silent_source(self):
        from orpheus.domain import projects

        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            video = folder / "long.mp4"
            quiet = folder / "quiet.wav"
            ff(
                "-f",
                "lavfi",
                "-i",
                "color=c=blue:s=64x64:r=5",
                "-t",
                31,
                "-c:v",
                "libx264",
                video,
            )
            ff("-f", "lavfi", "-i", "anullsrc=r=48000:cl=mono", "-t", 1, quiet)
            with patch.object(projects, "PROJECTS", folder / "projects"):
                with self.assertRaisesRegex(ValueError, "too quiet"):
                    create(video, quiet)
                p = create(video, load_case()["sfx_path"])
                self.assertEqual(p["seconds"], 30)
                self.assertFalse(p["has_original_audio"])
                self.assertEqual(p["input_duration_s"], 31)

    def test_agent_gates(self):
        from types import SimpleNamespace

        from orpheus.agent.workflow import build

        case = {**load_case("shoes"), "context": "test", "style": "test"}
        with tempfile.TemporaryDirectory() as d:
            agent = build(case, Path(d), lambda *a, **k: None)
            tools = {t.__name__: t for t in agent.sub_agents[0].tools}
            ctx = SimpleNamespace(
                state={},
                actions=SimpleNamespace(escalate=False, skip_summarization=False),
            )
            self.assertIn("error", tools["render_plan"](-22, "balanced", "test", ctx))
            self.assertIn(
                "error",
                tools["render_texture"](0, 6, 0, 3, -22, True, 0.1, "test", ctx),
            )
            self.assertIn(
                "error",
                tools["finish"]("madeup", "needs_human_review", "test", [], ctx),
            )
            sample = next((r["id"] for r in fitting.bank(case) if r["usable"]))
            plan = [
                dict(
                    time_s=1,
                    duration_s=0.3,
                    sample_id=sample,
                    gain_db=0,
                    confidence="likely",
                    evidence="test",
                )
            ]
            ctx.state["inspected"] = True
            self.assertIn(
                "error",
                tools["render_texture"](0, 6, 0, 3, -22, True, 0.1, "unreviewed", ctx),
            )
            self.assertIn("error", tools["save_event_plan"](json.dumps(plan), ctx))
            ctx.state["reviewed"] = [1]
            self.assertIn(
                "error",
                tools["record_event_review"](1, "target", "Not delivered yet", ctx),
            )
            ctx.state["delivered_centers"] = [1]
            self.assertEqual(
                tools["record_event_review"](
                    1, "target", "Visible transition and local onset", ctx
                )["saved"],
                True,
            )
            self.assertEqual(
                tools["save_event_plan"](json.dumps(plan), ctx)["saved_events"], 1
            )
            tools["record_review_batch"](
                json.dumps(
                    [
                        dict(
                            center_s=1,
                            verdict="non_target",
                            observation="Corrected interpretation",
                        )
                    ]
                ),
                ctx,
            )
            self.assertIn("error", tools["save_event_plan"](json.dumps(plan), ctx))
            tools["record_event_review"](1, "uncertain", "Contact unclear", ctx)
            self.assertIn("error", tools["save_event_plan"](json.dumps(plan), ctx))
            plan[0]["confidence"] = "uncertain"
            self.assertEqual(
                tools["save_event_plan"](json.dumps(plan), ctx)["saved_events"], 1
            )
            ctx.state["cycle_reviews"] = 20
            self.assertIn("error", tools["review_moments"]([2], ctx))
            ctx.state["waveform_calls"] = 20
            self.assertIn("error", tools["waveform_profile"](2, ctx))
            tools["remember_decision"]("Needs human listening", ctx)
            self.assertEqual(ctx.state["notes"], ["Needs human listening"])

    def test_persistent_session(self):

        async def check(folder):
            url = "sqlite+aiosqlite:///" + str(Path(folder) / "session.sqlite")
            one = DatabaseSessionService(db_url=url)
            s = await one.create_session(
                app_name="test", user_id="u", session_id="p", state={"notes": []}
            )
            await one.append_event(
                s,
                Event(
                    author="system",
                    actions=EventActions(
                        state_delta={"notes": ["keep subtle"], "plan": [{"time_s": 1}]}
                    ),
                ),
            )
            await one.close()
            two = DatabaseSessionService(db_url=url)
            loaded = await two.get_session(app_name="test", user_id="u", session_id="p")
            self.assertEqual(loaded.state["notes"], ["keep subtle"])
            self.assertEqual(loaded.state["plan"][0]["time_s"], 1)
            self.assertGreater(len(loaded.events), 0)
            await two.close()

        with tempfile.TemporaryDirectory() as d:
            asyncio.run(check(d))

    def test_source_bank_and_bounds(self):
        case = load_case("crackers")
        rows = fitting.bank(case)
        self.assertTrue(any((r["usable"] for r in rows)))
        self.assertTrue(any((not r["usable"] for r in rows)))
        bad = [
            {
                "time_s": 1,
                "duration_s": 0.3,
                "sample_id": -1,
                "gain_db": 0,
                "confidence": "likely",
                "evidence": "test",
            }
        ]
        with self.assertRaises(ValueError):
            fitting.validate_plan(bad, case)
        with self.assertRaises(ValueError):
            fitting.bounded(float("nan"), 0, 1, "test")

    def test_per_event_fit(self):
        case = load_case("shoes")
        ids = [r["id"] for r in fitting.bank(case) if r["usable"]]
        plan = [
            dict(
                time_s=t,
                duration_s=0.3,
                sample_id=ids[i % len(ids)],
                gain_db=-i,
                confidence="uncertain",
                evidence="Synthetic schedule test",
            )
            for i, t in enumerate([1.0, 2.0, 3.0])
        ]
        with tempfile.TemporaryDirectory() as d:
            r = fitting.render(case, plan, Path(d), -22)
            self.assertTrue(r["metrics"]["picture_unchanged"])
            self.assertLessEqual(r["metrics"]["true_peak_dbtp"], -1)
            self.assertEqual(r["metrics"]["clipped_samples"], 0)
            self.assertLess(r["metrics"]["body_spread_db"], 3)

    def test_cracker_peak_retained_after_compression(self):
        case = load_case("crackers")
        ids = [r["id"] for r in fitting.bank(case) if r["usable"]]
        plan = [
            dict(
                time_s=2.0 + i * 2,
                duration_s=0.6,
                sample_id=sid,
                gain_db=0,
                confidence="uncertain",
                evidence="Synthetic codec regression",
            )
            for i, sid in enumerate(ids)
        ]
        with tempfile.TemporaryDirectory() as d:
            r = fitting.render(case, plan, Path(d), -22)
            self.assertLessEqual(r["metrics"]["encoded_peak_error_ms"], 25)
            self.assertLessEqual(r["metrics"]["true_peak_dbtp"], -1)


if __name__ == "__main__":
    unittest.main()
