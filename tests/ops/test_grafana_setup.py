"""Provisioning must remain independent of the reference lab."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from orpheus import config
from orpheus.ops import grafana, observability


class GrafanaSetupChecks(unittest.TestCase):
    def test_control_room_prioritizes_decisions_over_raw_logs(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with patch.object(grafana, "OBSERVABILITY_ASSETS", root):
                grafana.dashboard()
            doc = json.loads((root / "dashboards/foley.json").read_text())
            kinds = [panel["type"] for panel in doc["panels"]]
            self.assertEqual(doc["title"], "Agentic Foley Control Room")
            self.assertIn("state-timeline", kinds)
            self.assertIn("barchart", kinds)
            self.assertIn("gauge", kinds)
            self.assertNotIn("logs", kinds)
            raw = next(panel for panel in doc["panels"] if panel["type"] == "row")
            self.assertTrue(raw["collapsed"])
            self.assertEqual(len(raw["panels"]), 3)

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
                self.assertEqual(compose.call_count, 2)
                grafana.setup()
                self.assertEqual(
                    client.post.call_count,
                    2,
                    "Setup must reuse its existing read-only service token",
                )

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
                patch.object(grafana, "compose"),
                patch.object(grafana.httpx, "Client") as http,
            ):
                http.return_value.__enter__.return_value = client
                grafana.setup()
            self.assertIn("GRAFANA_MCP_TOKEN=replacement-token", (folder / ".env").read_text())
