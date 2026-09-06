import { test } from "node:test";
import assert from "node:assert/strict";
import { Transport } from "./transport.js";
const media = () => ({
  currentTime: 3.24,
  paused: false,
  muted: false,
  pause() {
    this.paused = true;
  },
  async play() {
    this.paused = false;
  },
});
test("track switch preserves shared time and only resumes when new audio is ready", async () => {
  const t = new Transport();
  t.video = media();
  t.audio = media();
  t.switchTrack("a");
  assert.equal(t.video.currentTime, 3.24);
  assert.equal(t.video.paused, true);
  assert.equal(t.video.muted, true);
  t.audio.currentTime = 0;
  await t.ready();
  assert.equal(t.audio.currentTime, 3.24);
  assert.equal(t.video.paused, false);
  await t.switchTrack("original");
  assert.equal(t.audio.paused, true);
  assert.equal(t.video.muted, false);
});
test("audio rejection pauses both paths", async () => {
  const t = new Transport();
  t.video = media();
  t.audio = media();
  t.track = "a";
  t.audio.play = async () => {
    throw Error("decode failed");
  };
  await assert.rejects(() => t.play());
  assert.ok(t.video.paused && t.audio.paused);
});
