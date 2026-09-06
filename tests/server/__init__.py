"""HTTP service tests."""

import os


os.environ.setdefault("AGENT_PROVIDER_API_KEY", "offline-test-key")
if os.environ.get("ORPHEUS_LIVE_MCP") != "1":
    os.environ["ORPHEUS_GRAFANA_ENABLED"] = "0"
