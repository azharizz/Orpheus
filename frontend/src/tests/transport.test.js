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

test("bounded playback stops at the end of a match", async () => {
  const t = new Transport();
  t.video = media();
  t.video.currentTime = 4;
  await t.play(4.5);
  t.video.currentTime = 4.51;
  t.sync();
  assert.equal(t.video.paused, true);
  assert.equal(t.stopAt, null);
});

test("part preview maps global picture time to local audio time", async () => {
  const t = new Transport();
  t.video = media();
  t.video.currentTime = 159.83;
  t.audio = media();
  t.switchTrack("a", 154.34);
  await t.ready();
  assert.ok(Math.abs(t.audio.currentTime - 5.49) < 1e-9);
  t.seek(161.52);
  assert.ok(Math.abs(t.audio.currentTime - 7.18) < 1e-9);
});
