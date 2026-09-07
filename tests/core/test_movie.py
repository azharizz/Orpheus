import json
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import numpy as np

from orpheus.domain import families, media, movie, projects, takes
from tests.support import load_case


class MovieAnalysisTests(unittest.TestCase):
    def test_multi_family_draft_preserves_picture_and_unreviewed_pcm(self):
        source = load_case()
        with tempfile.TemporaryDirectory() as tmp, patch.object(projects, "ROOT", Path(tmp)), patch.object(projects, "PROJECTS", Path(tmp) / "projects"), patch.object(movie.obs, "emit"):
            doc = projects.create(source["video_path"])
            with self.assertRaisesRegex(ValueError, "replacement take"):
                movie.render_draft(doc["id"])
            first = families.create(doc["id"], "First contact", [0.72, 1.18])
            second = families.create(doc["id"], "Second contact", [2.12, 2.58])
            takes.add_take(doc["id"], source["sfx_path"], family_id=first["id"])
            takes.add_take(doc["id"], source["sfx_path"], family_id=second["id"])
            receipt = movie.render_draft(doc["id"])
            folder = projects.project_dir(doc["id"])
            self.assertEqual(sum(row["status"] == "drafted" for row in receipt["families"]), 2)
            self.assertTrue(receipt["metrics"]["picture_unchanged"])
            self.assertEqual(receipt["metrics"]["clipped_samples"], 0)
            self.assertEqual(media.picture_hash(folder / "video.mp4"), media.picture_hash(folder / receipt["video"]))
            with wave.open(str(folder / "mix.wav"), "rb") as original, wave.open(str(folder / receipt["wav"]), "rb") as rendered:
                original.setpos(7 * 48_000)
                rendered.setpos(7 * 48_000)
                self.assertEqual(original.readframes(4_800), rendered.readframes(4_800))

    def test_analysis_waits_for_media_preparation(self):
        with patch.object(projects, "load", return_value={"status": "preparing"}):
            with self.assertRaisesRegex(ValueError, "finish preparation"):
                movie.analyze("1234567890abcdef")

    def test_analysis_is_resumable_and_marks_events_and_noise(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            audio = folder / "original.wav"
            rate = 48_000
            samples = np.zeros(rate * 5, dtype=np.float32)
            for at in (0.5, 1.5, 2.5):
                start = round(at * rate)
                t = np.arange(round(.2 * rate)) / rate
                samples[start:start + len(t)] += .45 * np.sin(2 * np.pi * 500 * t) * np.exp(-t * 35)
            t = np.arange(rate * 2) / rate
            samples[rate * 3:] += .08 * np.sin(2 * np.pi * 997 * t)
            with wave.open(str(audio), "wb") as target:
                target.setparams((1, 2, rate, len(samples), "NONE", "not compressed"))
                target.writeframes(np.round(samples * 32767).astype("<i2").tobytes())
            case = {"id": "1234567890abcdef", "seconds": 5, "original_path": audio}
            with patch.object(projects, "load", return_value=case), patch.object(projects, "project_dir", return_value=folder), patch.object(movie.obs, "emit"):
                first = movie.analyze(case["id"])
                second = movie.analyze(case["id"])
            self.assertEqual(first, second)
            self.assertEqual(first["status"], "review_required")
            self.assertGreaterEqual(len(first["events"]), 2)
            self.assertTrue(first["waveform"])
            self.assertTrue(first["suggestions"])
            self.assertNotIn("families", first)
            self.assertFalse((folder / "families").exists())
            self.assertTrue((folder / "movie-analysis.json").exists())
            self.assertEqual(json.loads((folder / "movie-analysis.json").read_text())["progress"], 100)


if __name__ == "__main__":
    unittest.main()
