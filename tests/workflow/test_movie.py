import asyncio
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from google.genai import types

from orpheus.agent import movie
from orpheus.server import movie_worker


class MovieCoordinatorTests(unittest.TestCase):
    def test_movie_worker_bounds_family_agent_delegation(self):
        analysis = {"events": [], "families": [], "noise_regions": []}
        eligible = [{"id": f"family-{i}"} for i in range(4)]
        async def family_run(pid, family_id, feedback):
            return {"id": family_id, "status": "review_required"}
        async def coordinate(*args):
            return {"status": "completed", "families": [], "noise": []}
        with tempfile.TemporaryDirectory() as tmp, patch.object(movie_worker.movie, "analyze", return_value=analysis), patch.object(movie_worker.movie, "eligible_families", return_value=eligible), patch.object(movie_worker.movie, "render_draft", side_effect=ValueError("No draft")), patch.object(movie_worker, "coordinate", side_effect=coordinate), patch.object(movie_worker.worker, "execute", side_effect=family_run) as execute, patch.object(movie_worker.obs, "investigate", return_value={"status": "ok"}), patch.object(movie_worker.obs, "emit"), patch.object(movie_worker.projects, "project_dir", return_value=Path(tmp)), patch.object(movie_worker.projects, "atomic"), patch.object(movie_worker.movie, "status", return_value={}), patch.object(movie_worker.movie, "_save"):
            result = asyncio.run(movie_worker.execute("1234567890abcdef", "Review"))
        self.assertEqual(execute.call_count, 3)
        self.assertEqual(result["family_runs"][-1]["status"], "deferred")

    def test_coordinator_keeps_only_bounded_known_recommendations(self):
        class Model:
            async def generate_content_async(self, request):
                yield SimpleNamespace(content=types.Content(role="model", parts=[types.Part(text='{"families":[{"id":"family-one","working_label":"Possible steps","action":"needs_sfx","reason":"No take"},{"id":"invented","action":"run_family_agent"}],"noise":[{"id":"noise-one","action":"human_review","reason":"Listen"}],"summary":"Review first"}')]))

        analysis = {
            "events": [{"anchor_s": 1.0, "acoustic_band": "mid"}],
            "families": [{"id": "family-one", "name": "Contact", "band": "mid", "replacement_take_id": None}],
            "noise_regions": [{"id": "noise-one", "range_s": [2, 4]}],
        }
        with tempfile.TemporaryDirectory() as tmp, patch.object(movie, "ControllerModel", return_value=Model()), patch.object(movie.projects, "load", return_value={"seconds": 5}), patch.object(movie.projects, "project_dir", return_value=Path(tmp)), patch.object(movie.projects, "frames", return_value=[(1.0, Path(tmp) / "frame.jpg")]):
            (Path(tmp) / "frame.jpg").write_bytes(b"jpeg")
            result = asyncio.run(movie.coordinate("1234567890abcdef", analysis, {"status": "ok", "evidence_count": 2}, lambda *a, **k: None))
        self.assertEqual(result["families"], [{"id": "family-one", "working_label": "Possible steps", "action": "needs_sfx", "reason": "No take"}])
        self.assertEqual(result["noise"][0]["action"], "human_review")


if __name__ == "__main__":
    unittest.main()
