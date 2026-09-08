import assert from "node:assert/strict";
import test from "node:test";
import { workflowProgressModel } from "../state/progress.js";

test("an optimistic operation takes precedence over an older completed receipt", () => {
  const model = workflowProgressModel(
    { status: "complete", phase: "ready", progress: 100, message: "Old preview ready", render_id: "old-render" },
    { kind: "full_render", label: "Starting the full-movie preview" },
  );
  assert.equal(model.status, "running");
  assert.equal(model.active, true);
  assert.equal(model.hasProgress, false);
  assert.equal(model.detail, "Starting the full-movie preview");
  assert.equal(model.candidate, "");
});

test("a persisted running receipt supplies real render progress after polling", () => {
  const model = workflowProgressModel(
    {
      status: "running",
      phase: "mixing",
      progress: 62.4,
      message: "Writing the selective replacement mix",
      render_id: "render-1",
    },
    { kind: "full_render", label: "Starting the full-movie preview" },
  );
  assert.equal(model.status, "running");
  assert.equal(model.phase, "mixing");
  assert.equal(model.progress, 62.4);
  assert.equal(model.detail, "Writing the selective replacement mix");
  assert.equal(model.candidate, "render-1");
});

test("agent progress remains intentionally indeterminate while it reports stages", () => {
  const model = workflowProgressModel({
    status: "running",
    phase: "grafana",
    label: "Reading Grafana evidence",
    cycle: 2,
    candidate_count: 1,
  });
  assert.equal(model.hasProgress, false);
  assert.equal(model.counts, "Cycle 2 · 1 candidate");
  assert.equal(model.statusLabel, "In progress");
});
