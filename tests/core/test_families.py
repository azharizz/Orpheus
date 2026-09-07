import json
import struct
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import numpy as np

from orpheus.domain import families, takes as take_domain


RATE = 48000
PID = "a" * 16


def write_wav(path, samples, channels=1):
    values = np.asarray(samples)
    with wave.open(str(path), "wb") as stream:
        stream.setparams((channels, 2, RATE, len(values), "NONE", "not compressed"))
        stream.writeframes(np.round(values * 32767).astype("<i2").tobytes())


def pulse(frequency=240, seconds=0.24, level=0.5):
    clock = np.arange(round(seconds * RATE)) / RATE
    return level * np.exp(-clock * 20) * np.sin(2 * np.pi * frequency * clock)


def sparse_wav(path, seconds, events):
    frames = round(seconds * RATE)
    size = frames * 2
    with path.open("wb") as stream:
        stream.write(struct.pack("<4sI4s4sIHHIIHH4sI", b"RIFF", 36 + size, b"WAVE",
                                 b"fmt ", 16, 1, 1, RATE, RATE * 2, 2, 16,
                                 b"data", size))
        stream.seek(44 + size - 1)
        stream.write(b"\0")
        for moment, samples in events:
            stream.seek(44 + round(moment * RATE) * 2)
            stream.write(np.round(samples * 32767).astype("<i2").tobytes())


class FamilyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="orpheus-family-")
        self.folder = Path(self.temp.name) / PID
        self.folder.mkdir()
        self.audio = np.zeros(4 * RATE, dtype=np.float32)
        for moment in (0.5, 1.5, 2.5):
            sound = pulse()
            start = round(moment * RATE)
            self.audio[start : start + len(sound)] += sound
        other = pulse(1200, level=0.45)
        self.audio[round(3.2 * RATE) : round(3.2 * RATE) + len(other)] += other
        write_wav(self.folder / "original.wav", self.audio)
        self.case = {
            "id": PID,
            "seconds": 4.0,
            "original_path": self.folder / "original.wav",
            "video_path": self.folder / "video.mp4",
        }
        self.patches = (
            patch.object(families, "project_dir", return_value=self.folder),
            patch.object(families, "load", return_value=self.case),
            patch.object(take_domain, "project_dir", return_value=self.folder),
        )
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def test_index_is_deterministic_cached_and_small_for_a_feature_film(self):
        first = families.build_index(PID)
        features = np.load(self.folder / "similarity" / "features.npy", mmap_mode="r")
        copy = np.asarray(features).copy()
        second = families.build_index(PID)
        np.testing.assert_array_equal(copy, features)
        self.assertEqual(first["cache_key"], second["cache_key"])
        self.assertEqual(second["status"], "ready")
        self.assertEqual(families.index_status(PID)["total_windows"], len(features))
        two_hours = families._window_count(2 * 60 * 60 * RATE)
        self.assertLess(two_hours * families.FEATURES * 4, 100 * 1024 * 1024)

    def test_two_hour_sparse_media_uses_the_same_rank_and_refine_path(self):
        sparse_wav(self.folder / "original.wav", 7200, [(0.5, pulse()), (600.08, pulse())])
        self.case["seconds"] = 7200
        with patch.object(families, "HOP_S", 600):
            family = families.create(PID, "sparse shoe", [0.48, 0.78])
        self.assertTrue(any(
            abs(item["refined_anchor_s"] - 600.08) < 0.08
            for item in family["pending_matches"]
        ))

    def test_interrupted_index_resumes_from_completed_batch(self):
        real = families._fingerprints
        calls = 0

        def interrupt_once(windows):
            nonlocal calls
            calls += 1
            if calls == 2:
                raise RuntimeError("stop")
            return real(windows)

        with (
            patch.object(families, "BATCH_WINDOWS", 2),
            patch.object(families, "_fingerprints", side_effect=interrupt_once),
            self.assertRaises(RuntimeError),
        ):
            families.build_index(PID)
        state = json.loads((self.folder / "similarity" / "index.json").read_text())
        self.assertEqual(state["status"], "interrupted")
        self.assertEqual(state["completed_windows"], 2)
        with patch.object(families, "BATCH_WINDOWS", 2):
            ready = families.build_index(PID)
        self.assertEqual(ready["completed_windows"], ready["window_count"])
        self.assertEqual(ready["status"], "ready")

    def test_seed_finds_repeated_events_and_review_is_atomic(self):
        family = families.create(PID, "shoe contact", [0.48, 0.78])
        anchors = [item["refined_anchor_s"] for item in family["pending_matches"][:8]]
        self.assertTrue(any(abs(value - 1.5) < 0.08 for value in anchors))
        self.assertTrue(any(abs(value - 2.5) < 0.08 for value in anchors))
        chosen = family["pending_matches"][:2]
        reviewed = families.review(PID, family["id"], [chosen[0]["id"]], [chosen[1]["id"]])
        self.assertEqual(len(reviewed["accepted_ranges"]), 2)
        self.assertEqual(len(reviewed["rejected_ranges"]), 1)
        self.assertEqual(reviewed["search_version"], 2)
        decided = {item["id"] for item in chosen}
        self.assertFalse(decided & {item["id"] for item in reviewed["pending_matches"]})
        with self.assertRaises(ValueError):
            families.review(PID, family["id"], ["unknown"], [])

    def test_annotated_queue_meets_quality_gate(self):
        family = families.create(PID, "shoe contact", [0.48, 0.78])
        truth = [1.5, 2.5]
        found = [item["refined_anchor_s"] for item in family["pending_matches"]]
        errors = [min(abs(value - target) for value in found) for target in truth]
        true_positives = sum(any(abs(value - target) <= 0.1 for target in truth) for value in found)
        precision = true_positives / len(found)
        recall = sum(error <= 0.1 for error in errors) / len(truth)
        f2 = 5 * precision * recall / (4 * precision + recall)
        self.assertGreaterEqual(recall, 0.9)
        self.assertGreaterEqual(precision, 0.75)
        self.assertLessEqual(float(np.median(errors)), 0.1)
        self.assertGreaterEqual(f2, 0.9)

    def test_deferred_family_is_visible_before_feature_film_search(self):
        family = families.create(PID, "shoe", [0.48, 0.78], defer=True)
        self.assertEqual(family["status"], "part_ready")
        self.assertEqual(family["scope"], "part")
        self.assertEqual(families.list_families(PID)[0]["id"], family["id"])
        with self.assertRaisesRegex(ValueError, "replacement SFX"):
            families.search(PID, family["id"])
        take_id = "d" * 12
        take_folder = self.folder / "takes"
        take_folder.mkdir()
        take_path = take_folder / f"{take_id}.wav"
        write_wav(take_path, pulse())
        (take_folder / f"{take_id}.json").write_text(json.dumps({
            "id": take_id, "parent_project_id": PID, "family_id": family["id"],
            "audio_sha256": families._sha256(take_path),
        }))
        families.assign_take(PID, family["id"], take_id)
        with self.assertRaisesRegex(ValueError, "Approve the fitted part"):
            families.search(PID, family["id"])
        approved = families.get(PID, family["id"])
        approved["latest_render"] = {"id": "approvedpart", "human_approved": True}
        families.atomic(families._family_path(PID, family["id"]), approved)
        ready = families.search(PID, family["id"])
        self.assertEqual(ready["scope"], "movie")
        self.assertEqual(ready["status"], "review_required")
        self.assertTrue(ready["pending_matches"])

    def test_index_cache_invalidates_when_audio_changes(self):
        before = families.build_index(PID)["cache_key"]
        self.audio[0] = 0.25
        write_wav(self.folder / "original.wav", self.audio)
        after = families.build_index(PID)["cache_key"]
        self.assertNotEqual(before, after)

    def test_assign_take_checks_provenance(self):
        family = families.create(PID, "shoe", [0.48, 0.78])
        takes = self.folder / "takes"
        takes.mkdir()
        take_id = "b" * 12
        take_path = takes / f"{take_id}.wav"
        write_wav(take_path, pulse())
        (takes / f"{take_id}.json").write_text(
            json.dumps(
                {
                    "id": take_id,
                    "parent_project_id": PID,
                    "family_id": family["id"],
                    "audio_sha256": families._sha256(take_path),
                }
            )
        )
        result = families.assign_take(PID, family["id"], take_id)
        self.assertEqual(result["replacement_take_id"], take_id)

    def test_selective_mix_preserves_every_sample_outside_accepted_window(self):
        clock = np.arange(2 * RATE) / RATE
        original = (0.08 * np.sin(2 * np.pi * 90 * clock)).astype(np.float32)
        replacement = pulse(level=0.9)
        match = {
            "id": "event",
            "range_s": [0.7, 1.35],
            "refined_anchor_s": 0.9,
        }
        mixed, receipt = families.mix_selective(
            original, replacement, [match], duck_db=-12, ramp_s=0.025
        )
        start, end = round(0.7 * RATE), round(1.35 * RATE)
        np.testing.assert_array_equal(mixed[:start], original[:start])
        np.testing.assert_array_equal(mixed[end:], original[end:])
        self.assertFalse(np.array_equal(mixed[start:end], original[start:end]))
        self.assertLess(np.max(np.abs(mixed)), 1)
        self.assertLessEqual(receipt["replacement_peak_protection_db"], 0)

    def test_stereo_mix_keeps_shape_and_overlap_uses_deepest_duck(self):
        original = np.full((RATE, 2), 0.2, dtype=np.float32)
        replacement = pulse(seconds=0.1, level=0.1)
        matches = [
            {"id": "a", "range_s": [0.2, 0.7], "refined_anchor_s": 0.35},
            {"id": "b", "range_s": [0.4, 0.9], "refined_anchor_s": 0.55},
        ]
        mixed, _ = families.mix_selective(original, replacement, matches)
        self.assertEqual(mixed.shape, original.shape)
        np.testing.assert_array_equal(mixed[: round(0.2 * RATE)], original[: round(0.2 * RATE)])
        np.testing.assert_array_equal(mixed[round(0.9 * RATE) :], original[round(0.9 * RATE) :])

    def test_waveform_accepts_stereo_render_output(self):
        stereo = np.column_stack((self.audio, self.audio * 0.5))
        path = self.folder / "stereo.wav"
        write_wav(path, stereo, channels=2)
        from orpheus.domain import media
        result = media.waveform(path)
        self.assertEqual(result["channels"], 2)
        self.assertTrue(result["peaks"])

    def test_waveform_reads_only_requested_resolution_and_range(self):
        from orpheus.domain import media

        result = media.waveform(self.folder / "original.wav", bins=64, start_s=1, end_s=2)
        self.assertEqual((result["start_s"], result["end_s"]), (1, 2))
        self.assertLessEqual(len(result["peaks"]), 64)
        self.assertAlmostEqual(result["bin_duration_s"], 1 / len(result["peaks"]), places=6)
        with self.assertRaisesRegex(ValueError, "inside"):
            media.waveform(self.folder / "original.wav", start_s=3, end_s=2)

    def test_render_uses_assigned_take_and_preserves_picture(self):
        families.ff(
            "-f",
            "lavfi",
            "-i",
            "testsrc2=s=96x64:r=10",
            "-t",
            4,
            "-c:v",
            "libx264",
            self.case["video_path"],
        )
        family = families.create(PID, "shoe", [0.48, 0.78])
        takes = self.folder / "takes"
        takes.mkdir()
        take_id = "c" * 12
        take_path = takes / f"{take_id}.wav"
        write_wav(take_path, pulse(level=0.3))
        (takes / f"{take_id}.json").write_text(
            json.dumps(
                {
                    "id": take_id,
                    "parent_project_id": PID,
                    "family_id": family["id"],
                    "audio_sha256": families._sha256(take_path),
                }
            )
        )
        families.assign_take(PID, family["id"], take_id)
        with take_path.open("ab") as stream:
            stream.write(b"changed")
        with self.assertRaisesRegex(ValueError, "provenance"):
            families.render(PID, family["id"])
        write_wav(take_path, pulse(level=0.3))
        receipt = families.render(PID, family["id"])
        self.assertEqual(receipt["render_mode"], "selective_duck_overlay")
        self.assertTrue(receipt["metrics"]["picture_unchanged"])
        self.assertEqual(receipt["metrics"]["clipped_samples"], 0)
        self.assertTrue((self.folder / receipt["video"]).is_file())
        self.assertTrue((self.folder / receipt["master"]).is_file())
        families.record_render_review(PID, family["id"], receipt["id"], "approve")
        saved = json.loads((self.folder / f"{receipt['id']}.json").read_text())
        self.assertTrue(saved["human_approved"])
        self.assertEqual(saved["human_verdict"], "approve")


if __name__ == "__main__":
    unittest.main()
