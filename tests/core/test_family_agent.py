import json
import tempfile
import unittest
import wave
from pathlib import Path
from unittest.mock import patch

import numpy as np

from orpheus.domain import family_agent

RATE = 48000
PID = "a" * 16
FID = "b" * 12
TID = "c" * 12


def write_wav(path, samples):
    with wave.open(str(path), "wb") as output:
        output.setparams((1, 2, RATE, len(samples), "NONE", "not compressed"))
        output.writeframes(np.round(np.asarray(samples) * 32767).astype("<i2").tobytes())


class FamilyAgentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="orpheus-family-agent-")
        self.folder = Path(self.temp.name)
        (self.folder / "takes").mkdir()
        self.original = self.folder / "original.wav"
        write_wav(self.original, np.full(RATE, 0.1, dtype=np.float32))
        self.take = self.folder / "takes" / f"{TID}.wav"
        write_wav(self.take, np.ones(1000, dtype=np.float32) * 0.1)
        (self.folder / "takes" / f"{TID}.json").write_text(
            json.dumps(
                {
                    "id": TID,
                    "parent_project_id": PID,
                    "family_id": FID,
                    "audio_sha256": family_agent.projects.digest(self.take),
                }
            )
        )
        self.family = {
            "id": FID,
            "name": "shoe",
            "accepted_ranges": [{"id": "seed", "range_s": [0.2, 0.4]}],
            "replacement_take_id": TID,
        }
        self.case = {
            "id": PID,
            "seconds": 1.0,
            "original_path": self.original,
            "mix_path": self.original,
        }
        self.patches = [
            patch.object(family_agent.projects, "load", return_value=self.case),
            patch.object(family_agent.projects, "project_dir", return_value=self.folder),
            patch.object(family_agent.takes, "project_dir", return_value=self.folder),
            patch.object(family_agent.families, "get", return_value=self.family),
        ]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def test_case_uses_the_family_take_without_a_linked_project(self):
        case = family_agent.load_case(PID, FID)
        self.assertEqual(case["sfx_path"], self.take)
        self.assertEqual(case["accepted_ranges"], [[0.2, 0.4]])

    def test_agent_layer_cannot_escape_accepted_ranges(self):
        layer = self.folder / "layer.wav"
        samples = np.zeros(RATE, dtype=np.float32)
        samples[round(0.1 * RATE) : round(0.12 * RATE)] = 0.2
        write_wav(layer, samples)
        with self.assertRaisesRegex(ValueError, "outside accepted"):
            family_agent._write_mix(
                self.original,
                layer,
                self.folder / "blocked.wav",
                [(round(0.2 * RATE), round(0.4 * RATE))],
                -12,
                0.025,
            )


if __name__ == "__main__":
    unittest.main()
