"""Provisioning must remain independent of the reference lab."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from orpheus import grafana, observability, config


class GrafanaSetupChecks(unittest.TestCase):
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
