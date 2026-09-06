import { test } from "node:test";
import assert from "node:assert/strict";
import {
  startRecording,
  stopRecording,
  recordingState,
  discard,
  uploadTake,
} from "./recording.js";

const pending = () => {
  let resolve, reject;
  const promise = new Promise((a, b) => {
    resolve = a;
    reject = b;
  });
  return { promise, resolve, reject };
};
const picture = () => ({
  muted: false,
  currentTime: 0,
  paused: true,
  async play() {
    this.paused = false;
  },
  pause() {
    this.paused = true;
  },
});
function environment(getUserMedia) {
  Object.defineProperty(globalThis, "navigator", {
    configurable: true,
    value: { mediaDevices: { getUserMedia } },
  });
  globalThis.MediaRecorder = class {
    static isTypeSupported() {
      return true;
    }
    constructor() {
      this.state = "inactive";
      this.mimeType = "audio/webm";
      environment.recorder = this;
    }
    start() {
      this.state = "recording";
    }
    stop() {
      this.state = "inactive";
    }
    flush() {
      this.ondataavailable({ data: new Blob(["captured"]) });
      this.onstop();
    }
  };
}

test("capture owns final flush, preserves start metadata, releases tracks and restores mute", async () => {
  let released = 0;
  environment(async () => ({
    getTracks: () => [
      {
        stop() {
          released++;
        },
      },
    ],
  }));
  const video = picture(),
    metadata = { projectId: "scene", brief: "soft heel", start: 1 };
  await startRecording(video, metadata, 5, 30);
  metadata.start = 3;
  metadata.brief = "changed after start";
  assert.equal(recordingState().active, true);
  assert.equal(video.muted, true);
  stopRecording();
  assert.equal(released, 1);
  assert.equal(video.muted, false);
  assert.equal(recordingState().stopping, true);
  await assert.rejects(
    () => startRecording(picture(), metadata, 5, 30),
    /Save or discard/,
  );
  environment.recorder.flush();
  assert.equal(recordingState().pending, false);
  assert.equal(recordingState().draft.start, 1);
  assert.equal(recordingState().draft.brief, "soft heel");
  discard();
});

test("cancelled permission cannot release or overwrite a later capture", async () => {
  const permission = pending();
  let oldReleased = 0,
    newReleased = 0;
  environment(() => permission.promise);
  const old = startRecording(picture(), { start: 0, projectId: "old" }, 5, 30);
  stopRecording();
  navigator.mediaDevices.getUserMedia = async () => ({
    getTracks: () => [
      {
        stop() {
          newReleased++;
        },
      },
    ],
  });
  await startRecording(picture(), { start: 0, projectId: "new" }, 5, 30);
  permission.resolve({
    getTracks: () => [
      {
        stop() {
          oldReleased++;
        },
      },
    ],
  });
  await old;
  assert.equal(oldReleased, 1);
  assert.equal(newReleased, 0);
  assert.equal(recordingState().active, true);
  stopRecording();
  environment.recorder.flush();
  assert.equal(recordingState().draft.projectId, "new");
  discard();
});

test("permission denial starts no capture and retains useful error", async () => {
  environment(async () => {
    throw Error("Permission denied");
  });
  await startRecording(picture(), { start: 0 }, 5, 30);
  assert.equal(recordingState().active, false);
  assert.equal(recordingState().pending, false);
  assert.match(recordingState().error, /Permission denied/);
});

test("capture failure survives final audio delivery; upload cannot replace an unsaved take", async () => {
  environment(async () => ({ getTracks: () => [{ stop() {} }] }));
  await startRecording(picture(), { start: 0 }, 5, 30);
  environment.recorder.state = "inactive";
  environment.recorder.onerror();
  environment.recorder.flush();
  assert.match(recordingState().error, /capture failed/);
  const draft = recordingState().draft;
  assert.throws(
    () => uploadTake(new Blob(["new"]), { start: 0 }, 100, 5),
    /Save or discard/,
  );
  assert.equal(recordingState().draft, draft);
  discard();
});
