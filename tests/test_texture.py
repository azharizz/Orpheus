from tests.support import load_case
import unittest
import numpy as np
import tempfile
import wave
from pathlib import Path
from orpheus.texture import assemble, render
from orpheus.projects import media


class TextureChecks(unittest.TestCase):
    def test_crossfade_constant_signal(self):
        out, seams = assemble(np.ones(48000) * 0.1, 3, 0.1, True)
        self.assertEqual(len(out), 144000)
        self.assertGreater(len(seams), 0)
        self.assertTrue(np.allclose(out, 0.1))

    def test_no_implicit_repeat(self):
        with self.assertRaises(ValueError):
            assemble(np.ones(48000), 2, 0.1, False)

    def test_bad_crossfade(self):
        with self.assertRaises(ValueError):
            assemble(np.ones(48000), 2, 0.6, True)

    def test_real_export_interval(self):
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d)
            src = folder / "source.wav"
            signal = 0.1 * np.sin(2 * np.pi * 200 * np.arange(96000) / 48000)
            with wave.open(str(src), "wb") as w:
                w.setparams((1, 2, 48000, len(signal), "NONE", "not compressed"))
                w.writeframes(np.round(signal * 32767).astype("<i2").tobytes())
            case = {**load_case("shoes"), "sfx_path": src}
            with self.assertRaises(ValueError):
                render(case, folder, 1, 7, 0, 3, -22, True, 0.1)
            result = render(case, folder, 1, 7, 0, 2, -22, True, 0.1)
            out = media.read_audio(folder / result["wav"])
            self.assertTrue(np.all(out[:48000] == 0))
            self.assertTrue(np.all(out[7 * 48000 :] == 0))
            self.assertEqual(result["metrics"]["max_dropout_s"], 0)
            self.assertEqual(result["metrics"]["clipped_samples"], 0)
            self.assertTrue(result["metrics"]["picture_unchanged"])
            self.assertNotIn("encoded_peak_error_ms", result["metrics"])


if __name__ == "__main__":
    unittest.main()
