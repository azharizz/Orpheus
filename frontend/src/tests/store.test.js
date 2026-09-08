import assert from "node:assert/strict";
import test from "node:test";
import { action, refresh, snapshot, update } from "../state/store.js";

test("agent start remains visible until the server reports it finished", async () => {
  const originalFetch = global.fetch;
  let running = true;
  global.fetch = async (url) => ({
    ok: true,
    json: async () => String(url).startsWith("/api/projects")
      ? { projects: [], running, errors: [] }
      : {},
  });
  try {
    update({ busy: false, operation: null, running: false });
    await action(() => Promise.resolve({ started: true }), "", { kind: "agent" });
    assert.equal(snapshot().operation?.kind, "agent");
    running = false;
    await refresh();
    assert.equal(snapshot().operation, null);
  } finally {
    global.fetch = originalFetch;
    update({ busy: false, operation: null, running: false });
  }
});
