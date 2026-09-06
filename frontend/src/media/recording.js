import { useSyncExternalStore } from "react";
import { cue, validateFile } from "../state/domain.js";

const listeners = new Set();
let state = {
  active: false,
  pending: false,
  stopping: false,
  draft: null,
  elapsed: 0,
  error: "",
};
let session = null;
const emit = (patch) => {
  state = { ...state, ...patch };
  listeners.forEach((fn) => fn());
};
const subscribe = (fn) => {
  listeners.add(fn);
  return () => listeners.delete(fn);
};
export const recordingState = () => state;
export const useRecording = () =>
  useSyncExternalStore(subscribe, recordingState);

function release(current) {
  current.stream?.getTracks().forEach((track) => track.stop());
  current.stream = null;
  clearTimeout(current.timeout);
  clearInterval(current.ticker);
  if (current.startedPicture) {
    current.picture.pause();
    current.picture.muted = current.priorMute;
    current.startedPicture = false;
  }
}
function finish(current) {
  release(current);
  if (session !== current) return;
  session = null;
  emit({ active: false, pending: false, stopping: false });
}
function retain(blob, metadata, error = "") {
  if (!blob.size) {
    emit({ error: error || "No audio captured. Try again or upload a take." });
    return;
  }
  discard();
  emit({ draft: { ...metadata, blob, url: URL.createObjectURL(blob) }, error });
}
export function discard() {
  if (state.draft) URL.revokeObjectURL(state.draft.url);
  emit({ draft: null });
}
export function uploadTake(file, metadata, limit, duration) {
  if (session || state.draft)
    throw Error("Save or discard the current take first.");
  validateFile(file, limit);
  const start = cue(metadata.start, duration);
  retain(file, { ...metadata, start, clock: "uploaded" });
}
export async function startRecording(picture, metadata, duration, maxDuration) {
  if (session || state.draft)
    throw Error("Save or discard the current take first.");
  const start = cue(metadata.start, duration);
  if (!Number.isFinite(maxDuration) || maxDuration <= 0)
    throw Error("Recording limit is unavailable.");
  if (!picture) throw Error("Picture is not ready.");
  if (!navigator.mediaDevices?.getUserMedia || !globalThis.MediaRecorder)
    throw Error("Microphone recording is unavailable. Upload a take instead.");
  const current = {
    picture,
    metadata: { ...metadata, start, clock: "browser_playback" },
    cancelled: false,
    chunks: [],
    error: "",
  };
  session = current;
  emit({ pending: true, stopping: false, error: "", elapsed: 0 });
  try {
    const acquired = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: false,
        noiseSuppression: false,
        autoGainControl: false,
      },
    });
    if (current.cancelled) {
      acquired.getTracks().forEach((track) => track.stop());
      return;
    }
    current.stream = acquired;
    current.priorMute = picture.muted;
    current.startedPicture = true;
    picture.muted = true;
    picture.currentTime = start;
    const mimeType = ["audio/webm;codecs=opus", "audio/mp4", "audio/webm"].find(
      (type) => MediaRecorder.isTypeSupported(type),
    );
    const recorder = new MediaRecorder(
      acquired,
      mimeType ? { mimeType } : undefined,
    );
    current.recorder = recorder;
    recorder.ondataavailable = (event) => {
      if (event.data.size) current.chunks.push(event.data);
    };
    recorder.onstop = () => {
      if (session === current)
        retain(
          new Blob(current.chunks, { type: recorder.mimeType }),
          current.metadata,
          current.error,
        );
      finish(current);
    };
    recorder.onerror = () => {
      current.error =
        "Microphone capture failed. Any captured audio remains available for audition.";
      emit({ error: current.error });
      stopRecording();
    };
    await picture.play();
    if (current.cancelled) return;
    recorder.start(250);
    current.beganCapture = true;
    const began = performance.now();
    emit({ active: true, pending: false });
    current.ticker = setInterval(
      () => emit({ elapsed: (performance.now() - began) / 1000 }),
      250,
    );
    current.timeout = setTimeout(
      stopRecording,
      Math.min(maxDuration, duration - start) * 1000,
    );
  } catch (error) {
    if (!current.cancelled && session === current)
      emit({
        error: `Microphone or picture unavailable: ${error.message}. Upload a take instead.`,
      });
    finish(current);
  }
}
export function stopRecording() {
  const current = session;
  if (!current || current.cancelled) return;
  current.cancelled = true;
  if (current.beganCapture) {
    // Keep ownership until the browser flushes the final chunk and stop event.
    emit({ active: false, pending: true, stopping: true });
    if (current.recorder.state === "recording") current.recorder.stop();
    release(current);
  } else finish(current);
}
if (typeof window !== "undefined") {
  window.addEventListener("pagehide", stopRecording);
  window.addEventListener("beforeunload", (event) => {
    if (state.draft || session) {
      event.preventDefault();
      event.returnValue = "";
    }
  });
}
