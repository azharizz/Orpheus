import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import httpx

from orpheus.agent import perception as p
from orpheus.domain.projects import media
from tests.support import load_case


class PerceptionTests(unittest.TestCase):
    def test_expanded_inventory_limit(self):
        self.assertEqual(p.MAX_INVENTORY_EVENTS, 100)

    def test_label_wording_is_not_a_conflict(self):
        r, _, a = p.window(load_case("shoes"), "source", 0, 1)

        def evidence(label, kind="texture"):
            doc = self.document(r)
            doc["events"][0].update(label=label, kind=kind)
            return {
                "evidence_id": label,
                "receipt": r,
                "inventory": p.validate_inventory(doc, r),
                "measurements": p.measurements(a, r),
            }

        old = evidence("motor humming")
        new = evidence("motor hum")
        row = p.reconcile(new, [], [old])["events"][0]
        self.assertEqual(row["conflicts"], [])
        self.assertTrue(row["prior_overlap_ids"])
        self.assertFalse(row["verified"])
        self.assertIn(
            "Overlapping prior hypothesis differs; correspondence unresolved",
            p.reconcile(new, [], [evidence("motor hum", "composite")])["events"][0][
                "conflicts"
            ],
        )

    def test_source_reviews_use_source_audio_not_target_frames(self):
        from orpheus.agent.workflow import build

        case = {**load_case("shoes"), "context": "", "style": ""}
        r, _, a = p.window(case, "source", 0.5, 1.5)
        ev = {
            "evidence_id": "source-evidence",
            "receipt": r,
            "inventory": p.validate_inventory(self.document(r), r),
            "measurements": p.measurements(a, r),
        }
        with tempfile.TemporaryDirectory() as d:
            tools = {
                t.__name__: t
                for t in build(case, Path(d), lambda *a, **k: None).sub_agents[0].tools
            }
            ctx = SimpleNamespace(
                state={"audio_evidence": {"source-evidence": ev}},
                actions=SimpleNamespace(),
            )
            row = {
                "event_id": ev["inventory"]["events"][0]["id"],
                "audio_evidence_id": "source-evidence",
                "kind": "impulse",
                "onset_range_s": [0.6, 0.7],
                "observation": "Provisional source attack",
            }
            result = tools["reconcile_audio"]("source-evidence", json.dumps([row]), ctx)
            self.assertNotIn("error", result)
            self.assertTrue(result["events"][0]["audio_review_ids"])
            self.assertEqual(result["events"][0]["visual_review_ids"], [])
            self.assertFalse(result["events"][0]["verified"])
            self.assertEqual(
                ctx.state["inventory_reviews"][0]["provenance"],
                "controller_audio_hypothesis",
            )
            for bad in [
                dict(row, audio_evidence_id="madeup"),
                dict(row, onset_range_s=[0, 0.1]),
                dict(row, event_id="wrong"),
            ]:
                self.assertIn(
                    "error",
                    tools["reconcile_audio"]("source-evidence", json.dumps([bad]), ctx),
                )
            visual = dict(row)
            visual["frame_receipt_id"] = visual.pop("audio_evidence_id")
            self.assertIn(
                "error",
                tools["reconcile_audio"]("source-evidence", json.dumps([visual]), ctx),
            )
            ctx.state["audio_evidence"]["other"] = {
                **ev,
                "receipt": {**r, "role": "target"},
            }
            self.assertIn(
                "error",
                tools["reconcile_audio"](
                    "source-evidence",
                    json.dumps([dict(row, audio_evidence_id="other")]),
                    ctx,
                ),
            )
            self.assertEqual(len(ctx.state["inventory_reviews"]), 1)

    def test_arrangement_tool_rejects_invented_correspondence(self):
        from types import SimpleNamespace

        from orpheus.agent.workflow import build

        case = {**load_case("shoes"), "context": "", "style": ""}
        with tempfile.TemporaryDirectory() as d:
            tools = {
                t.__name__: t
                for t in build(case, Path(d), lambda *a, **k: None).sub_agents[0].tools
            }
            ctx = SimpleNamespace(state={}, actions=SimpleNamespace())
            sample = str(
                next(
                    iter(
                        __import__("orpheus.domain.fitting", fromlist=["bank"]).bank(
                            case
                        )
                    )
                )["id"]
            )
            row = {
                "id": "m1",
                "target_id": "not-real",
                "source_id": sample,
                "target_range_s": [1, 1.2],
                "source_range_s": [0.1, 0.3],
                "kind": "impact",
                "anchor": "contact",
                "disposition": "use",
                "confidence": "uncertain",
                "evidence": "provisional",
            }
            self.assertIn("error", tools["save_arrangement"](json.dumps([row]), ctx))

    def setUp(self):
        self.case = load_case("shoes")

    def test_exact_window_and_schema(self):
        receipt, data, samples = p.window(self.case, "source", 0.5, 1.5)
        self.assertEqual(receipt["duration_s"], 1)
        doc = self.document(receipt)
        result = p.validate_inventory(doc, receipt)
        self.assertEqual(result["events"][0]["onset_range_s"], [0.6, 0.7])
        self.assertEqual(result["events"][0]["status"], "hypothesis")
        for key, value in [("media_id", "wrong"), ("duration_s", 21)]:
            with self.assertRaises(ValueError):
                p.validate_inventory({**doc, key: value}, receipt)
        for bad in [float("nan"), True, -1]:
            with self.assertRaises(ValueError):
                p.window(self.case, "target", bad, 1)

    def test_window_clamps_rounded_end_to_decoded_audio(self):
        requested = self.case["seconds"] + 0.1
        actual = len(media.read_audio(self.case["original_path"])) / media.RATE
        receipt, _, _ = p.window(self.case, "target", 0, requested)
        self.assertAlmostEqual(receipt["end_s"], actual, places=6)
        self.assertEqual(receipt["requested_end_s"], requested)
        self.assertEqual(receipt["end_clamped_to_audio_s"], actual)

    @staticmethod
    def document(r):
        return {
            "media_id": r["media_id"],
            "duration_s": r["duration_s"],
            "audio_access": "available",
            "events": [
                {
                    "kind": "impulse",
                    "label": "short impact",
                    "onset_range_s": [0.1, 0.2],
                    "offset_range_s": [0.3, 0.4],
                    "evidence": "brief acoustic attack",
                }
            ],
        }

    def test_transport_cache_disabled_and_failure(self):

        async def check(folder):
            logs = []
            engine = p.Perception(self.case, folder, lambda e, **k: logs.append((e, k)))
            calls = []

            async def request(receipt, data):
                calls.append(receipt)
                return {
                    "model": "google/gemini-2.5-flash-lite",
                    "provider": "test-provider",
                    "usage": {"prompt_tokens": 5},
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {"content": json.dumps(self.document(receipt))},
                        }
                    ],
                }

            with patch.object(engine, "request", side_effect=request):
                a = await engine.inspect("target", 0, 1)
                b = await engine.inspect("target", 0, 1)
                self.assertEqual(len(calls), 1)
                self.assertTrue(b["cache_hit"])
                self.assertEqual(a["inventory"], b["inventory"])
                self.assertNotIn("base64", json.dumps(logs))
                with patch.object(engine, "enabled", False):
                    self.assertEqual(
                        (await engine.inspect("target", 0, 1))["status"], "disabled"
                    )
            with patch.object(
                engine, "request", side_effect=RuntimeError("secret payload")
            ):
                failed = await engine.inspect("source", 0, 1)
                self.assertEqual(failed["status"], "failed")
                self.assertNotIn("secret", json.dumps(logs))

        with tempfile.TemporaryDirectory() as d:
            asyncio.run(check(Path(d)))

    def test_unknown_coverage_and_unavailable(self):
        r, _, _ = p.window(self.case, "target", 0, 1)
        doc = self.document(r)
        doc["events"] = []
        result = p.validate_inventory(doc, r)
        self.assertEqual(result["unresolved_ranges_s"], [[0, 1]])
        doc["audio_access"] = "unavailable"
        with self.assertRaises(ValueError):
            p.validate_inventory(doc, r)

    def test_transport_payload_is_independent(self):

        async def check(folder):
            engine = p.Perception(self.case, folder, lambda *a, **k: None)
            r, data, _ = p.window(self.case, "source", 1, 2)
            captured = []

            def handler(request):
                body = json.loads(request.content)
                captured.append(body)
                return httpx.Response(200, json={"ok": True})

            original = httpx.AsyncClient
            with (
                patch.object(
                    p,
                    "provider_config",
                    return_value=("https://openrouter.ai/api/v1", "private-key"),
                ),
                patch.object(
                    p.httpx,
                    "AsyncClient",
                    side_effect=lambda **kw: original(
                        transport=httpx.MockTransport(handler), **kw
                    ),
                ),
            ):
                await engine.request(r, data)
            body = captured[0]
            self.assertEqual(len(body["messages"]), 2)
            self.assertEqual(body["max_tokens"], p.AUDIO_MAX_TOKENS)
            payload = body["messages"][1]["content"]
            self.assertEqual(json.loads(payload[0]["text"])["role"], "source")
            self.assertEqual(
                p.base64.b64decode(payload[1]["input_audio"]["data"]), data
            )
            self.assertNotIn("private-key", json.dumps(body))
            self.assertNotIn("context", json.loads(payload[0]["text"]))

        with tempfile.TemporaryDirectory() as d:
            asyncio.run(check(Path(d)))

    def test_signal_conflict_and_metric_units(self):
        r, _, a = p.window(self.case, "target", 0, 1)
        inv = p.validate_inventory(self.document(r), r)
        evidence = {
            "evidence_id": "test",
            "receipt": r,
            "inventory": inv,
            "measurements": p.measurements(a * 0, r),
        }
        report = p.reconcile(evidence, [], [])
        self.assertEqual(report["status"], "unresolved")
        self.assertFalse(report["events"][0]["verified"])
        self.assertNotIn("integrated_lufs", evidence["measurements"])
        self.assertIn("digital silence", str(report))
        self.assertTrue(evidence["measurements"]["digital_silence"])

    def test_reconciliation_citations_and_conflicts(self):
        from orpheus.agent.workflow import build

        case = {**self.case, "context": "test", "style": "test"}
        with tempfile.TemporaryDirectory() as d:
            agent = build(case, Path(d), lambda *a, **k: None)
            tools = {t.__name__: t for t in agent.sub_agents[0].tools}
            r, _, a = p.window(case, "target", 0, 1)
            ev = {
                "evidence_id": "test",
                "receipt": r,
                "inventory": p.validate_inventory(self.document(r), r),
                "measurements": p.measurements(a, r),
            }
            ctx = SimpleNamespace(
                state={"audio_evidence": {"test": ev}}, actions=SimpleNamespace()
            )
            row = {
                "event_id": ev["inventory"]["events"][0]["id"],
                "frame_receipt_id": "fake",
                "kind": "transition",
                "onset_range_s": [0.6, 0.7],
                "observation": "hypothesis",
            }
            self.assertIn(
                "error", tools["reconcile_audio"]("test", json.dumps([row]), ctx)
            )
            ctx.state["delivered_frame_receipts"] = [
                {
                    "id": "fake",
                    "video_sha256": p.digest(case["video_path"].read_bytes()),
                    "frames": [{"time_s": 0}, {"time_s": 1}],
                }
            ]
            result = tools["reconcile_audio"]("test", json.dumps([row]), ctx)
            self.assertIn(
                "Visual and acoustic onset ranges disagree",
                result["events"][0]["conflicts"],
            )
            self.assertFalse(result["events"][0]["verified"])
            self.assertEqual(ev["inventory"]["events"][0]["onset_range_s"], [0.1, 0.2])
            row["event_id"] = "source-madeup"
            self.assertIn(
                "error", tools["reconcile_audio"]("test", json.dumps([row]), ctx)
            )
            ctx.state["audio_evidence"]["test"]["receipt"]["file_sha256"] = "stale"
            self.assertIn("error", tools["reconcile_audio"]("test", "[]", ctx))

    def test_budget_malformed_and_no_source_audio(self):

        async def check(folder):
            logs = []
            engine = p.Perception(self.case, folder, lambda e, **k: logs.append((e, k)))
            with patch.object(
                engine,
                "request",
                return_value={
                    "model": p.MODEL,
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {"content": "not json secret"},
                        }
                    ],
                },
            ):
                result = await engine.inspect("target", 0, 1)
                self.assertEqual(result["status"], "failed")
                self.assertNotIn("secret", json.dumps(logs))
                self.assertEqual(list((folder / "perception").glob("*.json")), [])
                engine.calls = 6
                self.assertEqual(
                    (await engine.inspect("source", 0, 1))["status"], "budget_exhausted"
                )
            engine.case = {**self.case, "has_original_audio": False}
            self.assertEqual(
                (await engine.inspect("target", 0, 1))["status"], "unavailable"
            )

        with tempfile.TemporaryDirectory() as d:
            asyncio.run(check(Path(d)))

    def test_frame_window_bounds_and_delivery(self):
        from orpheus.agent.workflow import build

        case = {**self.case, "context": "test", "style": "test"}
        with tempfile.TemporaryDirectory() as d:
            agent = build(case, Path(d), lambda *a, **k: None)
            tools = {t.__name__: t for t in agent.sub_agents[0].tools}
            ctx = SimpleNamespace(state={}, actions=SimpleNamespace())
            result = tools["review_window"](0, 0.5, 0.25, [0, 0, 0.5, 0.5], ctx)
            self.assertIn("receipt", result)
            self.assertNotIn("delivered_frame_receipts", ctx.state)
            self.assertEqual(len(result["receipt"]["frames"]), 3)
            self.assertIn("error", tools["review_window"](0, 8, 0.01, [], ctx))
            self.assertIn(
                "error", tools["review_window"](0, 0.5, 0.25, [0.8, 0, 0.5, 1], ctx)
            )

    def test_regular_hypotheses_and_no_verification_bypass(self):
        from orpheus.agent.workflow import build
        from orpheus.agent.workflow_common import perception_gate

        r, _, a = p.window(self.case, "target", 0, 3)
        doc = self.document(r)
        doc["events"] = [
            {
                **doc["events"][0],
                "onset_range_s": [t, t + 0.02],
                "offset_range_s": [t + 0.04, t + 0.08],
            }
            for t in [0.1, 0.6, 1.1, 1.6]
        ]
        ev = {
            "evidence_id": "test",
            "receipt": r,
            "inventory": p.validate_inventory(doc, r),
            "measurements": p.measurements(a, r),
        }
        report = p.reconcile(ev, [], [])
        self.assertTrue(
            all(("Highly regular" in str(e["conflicts"]) for e in report["events"]))
        )
        state = {
            "audio_attempts": {"target": "ok", "source": "ok"},
            "audio_reconciliations": {"test": report},
        }
        self.assertIsNone(perception_gate(state, True))
        self.assertIsNone(perception_gate(state, False))
        with tempfile.TemporaryDirectory() as d:
            agent = build(
                {**self.case, "context": "", "style": ""}, Path(d), lambda *a, **k: None
            )
            tools = {t.__name__: t for t in agent.sub_agents[0].tools}
            ctx = SimpleNamespace(state={}, actions=SimpleNamespace())
            self.assertIn(
                "error",
                tools["remember_decision"]("Verified continuous operation", ctx),
            )
            self.assertEqual(ctx.state, {})
        doc["events"][0]["evidence"] = "It measures -24 LUFS"
        with self.assertRaises(ValueError):
            p.validate_inventory(doc, r)

    def test_cache_invalidation_and_http_failure(self):

        async def check(folder):
            engine = p.Perception(self.case, folder, lambda *a, **k: None)

            async def request(r, data):
                return {
                    "model": p.MODEL,
                    "choices": [
                        {
                            "finish_reason": "stop",
                            "message": {"content": json.dumps(self.document(r))},
                        }
                    ],
                }

            with patch.object(engine, "request", side_effect=request) as call:
                await engine.inspect("target", 0, 1)
                with patch.object(p, "PROMPT", p.PROMPT + " Different prompt."):
                    self.assertFalse(
                        (await engine.inspect("target", 0, 1))["cache_hit"]
                    )
                await engine.inspect("source", 0, 1)
                self.assertEqual(call.call_count, 3)
            resp = httpx.Response(
                403,
                request=httpx.Request(
                    "POST", "https://openrouter.ai/api/v1/chat/completions"
                ),
            )
            with patch.object(
                engine,
                "request",
                side_effect=httpx.HTTPStatusError(
                    "secret", request=resp.request, response=resp
                ),
            ):
                result = await engine.inspect("source", 1, 2)
                self.assertEqual(result["status_code"], 403)
            with patch.object(engine, "request", side_effect=TimeoutError("secret")):
                self.assertEqual(
                    (await engine.inspect("source", 1, 2))["error_type"], "TimeoutError"
                )

        with tempfile.TemporaryDirectory() as d:
            asyncio.run(check(Path(d)))

    def test_conflicting_evidence_reaches_both_renderers(self):
        from orpheus.agent.workflow import build

        case = {**self.case, "context": "", "style": ""}
        for renderer in ("render_plan", "render_texture"):
            with tempfile.TemporaryDirectory() as d:
                agent = build(case, Path(d), lambda *a, **k: None)
                tools = {t.__name__: t for t in agent.sub_agents[0].tools}
                state = {
                    "cycle": 1,
                    "inspected": True,
                    "plan": [{"test": "render boundary"}],
                    "audio_attempts": {"target": "ok", "source": "ok"},
                    "audio_reconciliations": {"conflict": {"status": "unresolved"}},
                    "delivered_centers": [0, 1, 2],
                    "event_reviews": [
                        {"center_s": t, "verdict": "uncertain"} for t in [0, 1, 2]
                    ],
                }
                ctx = SimpleNamespace(state=state, actions=SimpleNamespace())
                module = (
                    "orpheus.domain.fitting.render"
                    if renderer == "render_plan"
                    else "orpheus.domain.texture.render"
                )
                with patch(
                    module,
                    return_value={"id": "real-render-id", "audio_sha256": "test-hash"},
                ) as render:
                    result = (
                        tools[renderer](-22, "balanced", "Provisional", ctx)
                        if renderer == "render_plan"
                        else tools[renderer](
                            0, 2, 0, 2, -22, False, 0.1, "Provisional", ctx
                        )
                    )
                render.assert_called_once()
                self.assertEqual(
                    result["perception_warnings"]["unresolved_evidence_ids"],
                    ["conflict"],
                )
                self.assertEqual(state["candidates"][0]["id"], "real-render-id")

    def test_signal_role_identity_and_failure_codes(self):
        from orpheus.agent.workflow import build

        with tempfile.TemporaryDirectory() as d:
            agent = build(
                {**self.case, "context": "", "style": ""}, Path(d), lambda *a, **k: None
            )
            tools = {t.__name__: t for t in agent.sub_agents[0].tools}
            ctx = SimpleNamespace(state={}, actions=SimpleNamespace())
            result = tools["inspect_signal"]("source", 0.5, 1.5, ctx)
            self.assertEqual(result["receipt"]["role"], "source")
            self.assertEqual(
                result["receipt"]["file_sha256"],
                p.digest(self.case["sfx_path"].read_bytes()),
            )
            target = tools["waveform_profile"](1, ctx)
            self.assertEqual(target["role"], "target")
            self.assertNotEqual(target["file_sha256"], result["receipt"]["file_sha256"])
            self.assertIn("error", tools["inspect_signal"]("source", 0, 4, ctx))
            self.assertTrue(
                tools["remember_decision"](
                    "This is not verified; timing remains uncertain.", ctx
                )["saved"]
            )
        self.assertEqual(
            p.failure_code(ValueError("Wrong media identity")), "wrong_media"
        )
        self.assertEqual(
            p.failure_code(ValueError("Audio modality unavailable")),
            "audio_unavailable",
        )


if __name__ == "__main__":
    unittest.main()
