import { test } from "node:test";
import assert from "node:assert/strict";
import { registerMedia, claimMedia } from "./audio-focus.js";

test("audition pauses other sources while preserving paired picture and candidate; unmount releases media", () => {
  const video = {
      paused: false,
      pause() {
        this.paused = true;
      },
    },
    candidate = { ...video },
    source = { ...video };
  const releases = [video, candidate, source].map(registerMedia);
  claimMedia(video, candidate);
  assert.equal(source.paused, true);
  assert.equal(video.paused, false);
  assert.equal(candidate.paused, false);
  source.paused = false;
  claimMedia(source);
  assert.equal(video.paused, true);
  assert.equal(candidate.paused, true);
  assert.equal(source.paused, false);
  releases.forEach((release) => release());
  assert.equal(source.paused, true);
});
