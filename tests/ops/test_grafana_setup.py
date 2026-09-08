"""Provisioning must remain independent of the reference lab."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from orpheus import config
from orpheus.ops import grafana, observability


class GrafanaSetupChecks(unittest.TestCase):
    def test_review_station_centres_the_film_with_evidence_around_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(grafana, "OBSERVABILITY_ASSETS", root):
                grafana.dashboard()
            doc = json.loads((root / "dashboards/foley.json").read_text())
            visible = [panel for panel in doc["panels"] if panel["type"] != "row"]
            titles = [panel["title"] for panel in doc["panels"]]
            kinds = [panel["type"] for panel in doc["panels"]]
            self.assertNotIn("state-timeline", kinds)
            self.assertNotIn("logs", kinds)

            question = next(p for p in visible if p["title"].endswith("sound finished?"))
            self.assertEqual(question["gridPos"]["y"], 0)
            self.assertEqual(question["gridPos"]["w"], 24)

            self.assertNotIn("canvas", kinds)


            film = next(panel for panel in visible if panel["title"] == "The film")
            self.assertEqual(film["gridPos"]["x"], 0)
            self.assertIn("<video", film["options"]["content"])
            self.assertIn("#t=${part_start}", film["options"]["content"])

            self.assertLessEqual(len(visible), 12)
            self.assertTrue(all(panel["description"] for panel in visible))
            self.assertIn("This is a film", doc["description"])

            wave = next(p for p in visible if p["title"] == "Soundwave of the film")
            body = wave["options"]["content"]
            self.assertIn("/api/waveform", body)
            self.assertIn("currentTime", body)
            self.assertIn('<canvas id="owave-all"', body)
            self.assertIn('<canvas id="owave-zoom"', body)
            self.assertIn("${part_start}", body)
            self.assertNotIn("dataset.on", body)
            self.assertIn("clearInterval(window.__owaveTimer)", body)
            self.assertIn("function tick()", body)
            self.assertIn("var-", body)
            self.assertIn("not proven silence", wave["description"])
            self.assertNotIn("Working right now", titles)


            run = next(p for p in visible if p["title"] == "Last recorded run")
            labels = run["fieldConfig"]["defaults"]["mappings"][0]["options"]
            self.assertEqual(labels["1"]["text"], "PASSED LAST RUN")
            self.assertEqual(labels["0"]["text"], "NOT DECIDED")
            self.assertIn("not a live check", run["description"])

            part_end = next(v for v in doc["templating"]["list"] if v["name"] == "part_end")
            self.assertNotEqual(part_end["current"]["value"], "999999")
            self.assertNotIn("14d", doc["time"]["from"])

            ledger = next(p for p in visible if p["title"] == "Who decided, and on what")
            self.assertIn("human_review", ledger["targets"][0]["expr"])

            rows = {panel["title"]: panel for panel in doc["panels"] if panel["type"] == "row"}
            raw = rows["Raw evidence · open for diagnosis"]
            self.assertTrue(raw["collapsed"])
            self.assertEqual(len(raw["panels"]), 3)
            runtime = rows["Runtime · can these panels be trusted"]
            self.assertTrue(runtime["collapsed"])
            health = next(p for p in runtime["panels"] if p["title"] == "Grafana MCP")
            self.assertIn('event="grafana_query"', health["targets"][0]["expr"])
            self.assertNotIn("or vector", health["targets"][0]["expr"])

            moment = next(p for p in visible if p["title"] == "What is happening at this moment")
            mbody = moment["options"]["content"]
            self.assertIn("/api/families", mbody)
            self.assertIn("currentTime", mbody)
            self.assertIn("clearInterval(window.__onowTimer)", mbody)
            self.assertIn("moveTo(0,r.height/2)", mbody)
            self.assertIn("moveTo(mid,0)", mbody)
            self.assertIn("rather than proven silent", moment["description"])
            self.assertIn("never an approval", moment["description"])

            sure = next(p for p in visible if p["title"].startswith("How sure"))
            sbody = sure["options"]["content"]
            self.assertIn("/api/families", sbody)
            self.assertIn("/api/movie", sbody)
            self.assertIn("currentTime", sbody)
            self.assertIn("clearInterval(window.__osureTimer)", sbody)
            self.assertIn("never a probability", sure["description"])
            draw = sbody[sbody.index("function draw()"):sbody.index("function ready()")]
            self.assertNotIn("fetch(", draw)

            ledger = next(p for p in visible if p["title"] == "Who decided, and on what")
            hides = next(p for p in visible if p["title"] == "What the film still hides")
            self.assertEqual(ledger["gridPos"]["y"], hides["gridPos"]["y"])

            for retired in (
                "Loudness · last render",
                "Timing · last render",
                "Baseline vs agent",
                "Contact alignment · each replaced sound against its reviewed anchor",
                "Movie waveform · picture position",
                "Prepared movie proxy",
                "Grafana evidence reads",
                "Candidate evidence",
                "Run duration",
                "Reported cost",
            ):
                self.assertNotIn(retired, titles)

    def test_setup_ports_config_and_private_credentials(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            client = MagicMock()
            client.get.return_value.status_code = 200
            client.post.side_effect = [
                MagicMock(json=lambda: {"id": 7}),
                MagicMock(json=lambda: {"key": "test-token-not-real"}),
            ]
            with (
                patch.object(observability, "STORE", folder),
                patch.object(observability, "CONFIG", folder / "local.json"),
                patch.object(grafana, "dashboard") as dashboard,
                patch.object(grafana, "compose") as compose,
                patch.object(grafana.httpx, "Client") as http,
            ):
                http.return_value.__enter__.return_value = client
                grafana.setup()
                cfg = json.loads((folder / "local.json").read_text())
                self.assertEqual(
                    cfg["mcp_url"],
                    f"http://127.0.0.1:{config.GRAFANA_PORTS['MCP']}/mcp",
                )
                self.assertEqual((folder / ".env").stat().st_mode & 0o777, 0o600)
                self.assertEqual((folder / "local.json").stat().st_mode & 0o777, 0o600)
                self.assertIn(
                    f"host.docker.internal:{config.GRAFANA_PORTS['METRICS']}",
                    (folder / "prometheus.yaml").read_text(),
                )
                self.assertNotIn(
                    "__METRICS_PORT__", (folder / "prometheus.yaml").read_text()
                )
                self.assertEqual(compose.call_count, 3)
                self.assertIn("reset-admin-password", compose.call_args_list[1].args)
                grafana.setup()
                self.assertEqual(
                    client.post.call_count,
                    2,
                    "Setup must reuse its existing read-only service token",
                )
                self.assertEqual(dashboard.call_count, 2)

    def test_setup_recovers_existing_service_account_without_token_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            folder = Path(temporary)
            (folder / ".env").write_text(
                "GRAFANA_ADMIN_PASSWORD=test\nMCP_CALLER_TOKEN=test\n"
            )
            health = MagicMock(status_code=200)
            search = MagicMock(
                json=lambda: {
                    "serviceAccounts": [{"id": 7, "name": "orpheus-mcp-reader"}]
                }
            )
            duplicate = MagicMock(status_code=400)
            token = MagicMock(json=lambda: {"key": "replacement-token"})
            client = MagicMock()
            client.get.side_effect = [health, search]
            client.post.side_effect = [duplicate, token]
            with (
                patch.object(observability, "STORE", folder),
                patch.object(observability, "CONFIG", folder / "local.json"),
                patch.object(grafana, "dashboard"),
                patch.object(grafana, "compose"),
                patch.object(grafana.httpx, "Client") as http,
            ):
                http.return_value.__enter__.return_value = client
                grafana.setup()
            self.assertIn("GRAFANA_MCP_TOKEN=replacement-token", (folder / ".env").read_text())
