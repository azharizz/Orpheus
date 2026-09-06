import tempfile
import unittest
from pathlib import Path

import numpy as np

from orpheus.domain import arrangement as a
from orpheus.domain.arrangement import suitability, validate
from tests.support import load_case


class ArrangementTests(unittest.TestCase):
    def test_tail_options_preserve_baseline_landmark_and_bounds(self):
        from unittest.mock import patch

        source = np.zeros(48000)
        source[9600:43200] = 0.04
        with patch.object(a.media, "detect", return_value=[{"time_s": 0.2}]):
            options = a.source_options(source, 0, 1)["options"]
        self.assertEqual([o["variant"] for o in options], ["standard", "extended_tail"])
        self.assertEqual([o["index"] for o in options], [0, 1])
        self.assertEqual(options[0]["source_anchor_s"], options[1]["source_anchor_s"])
        self.assertLess(
            options[0]["source_range_s"][1], options[1]["source_range_s"][1]
        )
        self.assertLessEqual(options[1]["source_range_s"][1], 1)

    def test_expanded_mapping_limits(self):
        self.assertEqual(a.MAX_ROWS, 100)
        self.assertEqual(a.MAX_SOURCE_OPTIONS, 24)

    def test_automatic_impact_preparation(self):
        source = np.zeros(96000)
        source[9600:10080] = np.hanning(480) * 0.1
        source[28800:29280] = np.hanning(480) * 0.6
        options = a.source_options(source, 0, 1)
        self.assertEqual(options["total"], 2)
        row = self.canonical(
            [self.row(source_range_s=[0, 1], target_range_s=[1, 1.8])]
        )[0]
        fitted = a.prepare_impact(row, source, 0, 1.3)
        self.assertFalse(fitted["repeat"])
        self.assertEqual(fitted["anchor"], "contact")
        self.assertLess(fitted["source_range_s"][1], 0.6)
        out, metrics = a.assemble([fitted], source, 4)
        self.assertLessEqual(abs(np.argmax(out) / 48000 - 1.3), 1 / 48000)
        self.assertLessEqual(metrics[0]["normalization_db"], 12)
        self.assertGreaterEqual(metrics[0]["normalization_db"], -18)
        with self.assertRaises(ValueError):
            a.prepare_impact({**row, "kind": "texture"}, source, 0, 1.3)
        with self.assertRaises(ValueError):
            a.prepare_impact({**row, "kind": "composite"}, source, 0, 1.3)
        self.assertEqual(a.source_options(np.zeros(96000), 0, 1)["total"], 0)
        with self.assertRaises(ValueError):
            a.prepare_impact(row, np.zeros(96000), 0, 1.3)

    def canonical(self, rows):
        return validate(
            rows,
            target_duration_s=4,
            source_duration_s=2,
            target_ids={"t1", "t2"},
            source_ids={"s1"},
        )

    def test_composite_chronology_and_balanced_strength(self):
        source = np.zeros(96000)
        source[9600:10560] = np.hanning(960) * 0.1
        source[19200:20160] = np.hanning(960) * 0.05
        row = self.canonical(
            [
                self.row(
                    kind="composite",
                    anchor="start",
                    source_range_s=[0, 0.6],
                    target_range_s=[1, 1.6],
                    target_body_dbfs=-22,
                )
            ]
        )[0]
        out, m = a.assemble([row], source, 4)
        quieter, _ = a.assemble([{**row, "gain_db": -6}], source, 4)
        self.assertEqual(m[0]["seams_s"], [])
        self.assertAlmostEqual(quieter.max() / out.max(), 10 ** (-6 / 20))
        self.assertAlmostEqual(out[round(1.41 * 48000)] / out[round(1.21 * 48000)], 0.5)
        with self.assertRaises(ValueError):
            self.canonical([{**row, "target_body_dbfs": float("nan")}])

    def test_mixed_anchor_overlap_and_pause(self):
        source = np.zeros(96000)
        source[9600] = 0.6
        rows = self.canonical(
            [
                self.row(
                    target_range_s=[0.5, 1],
                    source_range_s=[0.1, 0.4],
                    source_anchor_s=0.2,
                    target_anchor_s=0.7,
                    fade_in_s=0,
                    fade_out_s=0,
                ),
                self.row(
                    id="second",
                    target_range_s=[0.5, 1],
                    source_range_s=[0.1, 0.4],
                    source_anchor_s=0.2,
                    target_anchor_s=0.7,
                    fade_in_s=0,
                    fade_out_s=0,
                    reuse_reason="layer test",
                    gain_db=-6,
                ),
                self.row(
                    id="pause",
                    target_id="t2",
                    source_id="",
                    target_range_s=[2, 3],
                    source_range_s=[0, 0],
                    kind="pause",
                    disposition="omit",
                ),
            ]
        )
        audio, receipt = a.assemble(rows, source, 4)
        self.assertEqual(np.argmax(audio), round(0.7 * 48000))
        self.assertAlmostEqual(audio.max(), 0.6 * (1 + 10 ** (-6 / 20)))
        self.assertFalse(np.any(audio[96000:144000]))
        self.assertEqual(len(receipt), 2)
        np.testing.assert_array_equal(audio, a.assemble(rows, source, 4)[0])

    def test_texture_no_implicit_repeat_and_weak_dynamics(self):
        rows = self.canonical(
            [
                self.row(
                    kind="texture",
                    anchor="start",
                    target_range_s=[0, 1],
                    source_range_s=[0, 0.4],
                )
            ]
        )
        with self.assertRaisesRegex(ValueError, "Source shorter"):
            a.assemble(rows, np.ones(96000) * 0.01, 4)
        rows[0]["repeat"] = True
        audio, receipt = a.assemble(rows, np.ones(96000) * 0.01, 4)
        self.assertAlmostEqual(audio.max(), 0.01)
        self.assertTrue(receipt[0]["seams_s"])

    def test_spike_shape_variable_strength_and_source_eof(self):
        source = np.ones(96000) * 0.001
        source[9600] = 1
        raw = self.canonical(
            [
                self.row(
                    target_range_s=[0, 0.5],
                    source_range_s=[0, 0.5],
                    anchor="start",
                    fade_in_s=0,
                    fade_out_s=0,
                )
            ]
        )
        one, m = a.assemble(raw, source, 4)
        softened = [{**raw[0], "shape": "soften", "gain_db": -6}]
        two, n = a.assemble(softened, source, 4)
        self.assertLess(two.max(), one.max())
        self.assertTrue(m[0]["source_near_full_scale"])
        quiet = [{**raw[0], "gain_db": -6}]
        three, _ = a.assemble(quiet, source, 4)
        self.assertAlmostEqual(three.max() / one.max(), 10 ** (-6 / 20))
        with self.assertRaises(ValueError):
            self.canonical([self.row(source_range_s=[1.9, 2.1])])

    def test_real_export(self):

        case = load_case("shoes")
        rows = self.canonical(
            [self.row(target_range_s=[1, 1.3], source_range_s=[0.1, 0.4])]
        )
        bound = {"rows": rows, "input_hashes": a.identities(case)}
        with tempfile.TemporaryDirectory() as d:
            r = a.render(case, bound, Path(d))
            self.assertTrue(r["metrics"]["picture_unchanged"])
            self.assertEqual(r["metrics"]["clipped_samples"], 0)
            self.assertLessEqual(r["metrics"]["true_peak_dbtp"], -1)

    def row(self, **changes):
        row = {
            "id": "m1",
            "target_id": "t1",
            "source_id": "s1",
            "target_range_s": [1, 1.2],
            "source_range_s": [0.1, 0.4],
            "kind": "impact",
            "anchor": "contact",
            "disposition": "use",
            "confidence": "uncertain",
            "evidence": "provisional timing evidence",
        }
        row.update(changes)
        return row

    def test_explicit_mapping_and_pause(self):
        rows = validate(
            [
                self.row(),
                self.row(
                    id="pause",
                    target_id="t2",
                    source_id="none",
                    target_range_s=[2, 3],
                    source_range_s=[0, 0],
                    kind="pause",
                    anchor="transition",
                    disposition="omit",
                ),
            ],
            target_duration_s=4,
            source_duration_s=2,
            target_ids={"t1", "t2"},
            source_ids={"s1"},
        )
        self.assertEqual(rows[0]["schema"], "arrangement.v1")
        self.assertEqual(suitability(rows)["omitted_count"], 1)

    def test_render_ready_impact_requires_explicit_landmarks(self):
        with self.assertRaisesRegex(
            ValueError, "explicit contact and source landmarks"
        ):
            validate(
                [self.row()],
                target_duration_s=4,
                source_duration_s=2,
                target_ids={"t1"},
                source_ids={"s1"},
                require_impact_anchors=True,
            )
        ready = self.row(target_anchor_s=1.1, source_anchor_s=0.2)
        rows = validate(
            [ready],
            target_duration_s=4,
            source_duration_s=2,
            target_ids={"t1"},
            source_ids={"s1"},
            require_impact_anchors=True,
        )
        self.assertEqual(rows[0]["target_anchor_s"], 1.1)
        self.assertEqual(rows[0]["source_anchor_s"], 0.2)

    def test_rejects_invented_used_ids_and_unordered_rows(self):
        with self.assertRaises(ValueError):
            validate(
                [self.row(source_id="invented")],
                target_duration_s=4,
                source_duration_s=2,
                target_ids={"t1"},
                source_ids={"s1"},
            )
        with self.assertRaises(ValueError):
            validate(
                [
                    self.row(id="late", target_range_s=[2, 2.1]),
                    self.row(id="early", target_range_s=[1, 1.1]),
                ],
                target_duration_s=4,
                source_duration_s=2,
                target_ids={"t1"},
                source_ids={"s1"},
            )

    def test_range_and_confidence_guards(self):
        with self.assertRaises(ValueError):
            validate(
                [self.row(target_range_s=[-1, 0])],
                target_duration_s=4,
                source_duration_s=2,
                target_ids={"t1"},
                source_ids={"s1"},
            )
        with self.assertRaises(ValueError):
            validate(
                [self.row(confidence="verified")],
                target_duration_s=4,
                source_duration_s=2,
                target_ids={"t1"},
                source_ids={"s1"},
            )


if __name__ == "__main__":
    unittest.main()
