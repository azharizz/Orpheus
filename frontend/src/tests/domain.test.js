import { test } from "node:test";
import assert from "node:assert/strict";
import {
  cue,
  validateFile,
  matchVolume,
  candidates,
  label,
  seedRange,
  pendingMatches,
  matchRange,
  pageWindow,
} from "../state/domain.js";
test("reject invalid recording boundaries and oversized media", () => {
  for (const n of ["", -1, 30, NaN, Infinity]) assert.throws(() => cue(n, 30));
  assert.equal(cue("29.9", 30), 29.9);
  assert.throws(() => validateFile({ size: 101 }, 100));
});
test("match pages stay bounded as the review queue changes", () => {
  const matches = Array.from({ length: 12 }, (_, id) => id + 1);
  assert.deepEqual(pageWindow(matches, 1).items, [6, 7, 8, 9, 10]);
  assert.deepEqual(pageWindow(matches, 99).items, [11, 12]);
  assert.equal(pageWindow([], 3).page, 0);
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
test("candidate inventory keeps completed agent renders", () => {
  assert.equal(
    candidates({
      turn_details: [{ candidates: [{ id: "a" }] }],
    }).length,
    1,
  );
});
test("sound-family seeds and pending matches retain measured ranges", () => {
  assert.deepEqual(seedRange("1.25", "1.8", 10), [1.25, 1.8]);
  assert.throws(() => seedRange(2, 1, 10), /start before its end/);
  const family = {
    matches: [
      { id: "m1", range_s: [1, 2], decision: "pending" },
      { id: "m2", start_s: 3, end_s: 4, decision: "accept" },
    ],
  };
  assert.deepEqual(pendingMatches(family).map((match) => match.id), ["m1"]);
  assert.deepEqual(matchRange(family.matches[0]), [1, 2]);
});
