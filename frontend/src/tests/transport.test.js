import { test } from "node:test";
import assert from "node:assert/strict";
import { Transport } from "../media/transport.js";
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
test("pause cancels a pending audio start before picture playback", async () => {
  const t = new Transport();
  t.video = media();
  t.audio = media();
  t.track = "a";
  let resolve;
  t.audio.play = () =>
    new Promise((done) => {
      resolve = done;
    });
  const pending = t.play();
  t.pause();
  resolve();
  await pending;
  assert.equal(t.video.paused, true);
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

test("reselecting the audible track leaves playback running; explicit pause cancels delayed resume", async () => {
  const t = new Transport();
  t.video = media();
  t.audio = media();
  t.switchTrack("original");
  assert.equal(t.video.paused, false);
  t.switchTrack("a");
  t.pause();
  await t.ready();
  assert.equal(t.video.paused, true);
});
