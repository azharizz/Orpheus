import { test } from "node:test";
import assert from "node:assert/strict";
import {
  cue,
  validateFile,
  matchVolume,
  editRow,
  candidates,
  label,
} from "../state/domain.js";
test("reject invalid recording boundaries and oversized media", () => {
  for (const n of ["", -1, 30, NaN, Infinity]) assert.throws(() => cue(n, 30));
  assert.equal(cue("29.9", 30), 29.9);
  assert.throws(() => validateFile({ size: 101 }, 100));
});
test("labels stored status codes for people while preserving unknown wording", () => {
  assert.equal(label("review_required"), "Review required");
  assert.equal(label("new_state"), "new state");
});
test("level matching attenuates louder takes without amplification", () => {
  assert.equal(matchVolume(-24, [-24, -12]), 1);
  assert.ok(Math.abs(matchVolume(-12, [-24, -12]) - 0.2511886) < 1e-6);
  assert.equal(matchVolume(undefined, []), 1);
});
test("assisted edits preserve original evidence and sibling rows", () => {
  const rows = [
    { id: "a", source_range_s: [1, 2], evidence: "receipt" },
    { id: "b" },
  ];
  const edited = editRow(rows, 0, "source_range_s.0", "1.2");
  assert.deepEqual(rows[0].source_range_s, [1, 2]);
  assert.equal(edited[0].evidence, "receipt");
  assert.equal(edited[1], rows[1]);
  assert.throws(() => editRow(rows, 0, "gain_db", ""));
  assert.equal(
    candidates({
      turn_details: [{ candidates: [{ id: "a" }] }],
      assisted_candidates: [{ id: "b" }],
    }).length,
    2,
  );
});
