import { useSyncExternalStore } from "react";
import { cue, validateFile } from "./domain.js";
const listeners = new Set();
let state = {
  active: false,
  pending: false,
  draft: null,
  elapsed: 0,
  error: "",
};
let recorder,
  stream,
  timeout,
  ticker,
  video,
  priorMute = false,
  generation = 0;
const emit = (patch) => {
  state = { ...state, ...patch };
  listeners.forEach((fn) => fn());
};
export const recordingState = () => state;
export const useRecording = () =>
  useSyncExternalStore((fn) => {
    listeners.add(fn);
    return () => listeners.delete(fn);
  }, recordingState);
function release() {
  stream?.getTracks().forEach((t) => t.stop());
  stream = null;
  clearTimeout(timeout);
  clearInterval(ticker);
  if (video) {
    video.pause();
    video.muted = priorMute;
    video = null;
  }
  emit({ active: false, pending: false });
}
function retain(blob, metadata) {
  if (!blob.size) {
    emit({ error: "No audio captured. Try again or upload a take." });
    return;
  }
  discard();
  emit({
    draft: { ...metadata, blob, url: URL.createObjectURL(blob) },
    error: "",
  });
}
export function discard() {
  if (state.draft) URL.revokeObjectURL(state.draft.url);
  emit({ draft: null });
}
export function uploadTake(file, metadata, limit, duration) {
  validateFile(file, limit);
  cue(metadata.start, duration);
  retain(file, { ...metadata, clock: "uploaded" });
}
export async function startRecording(picture, metadata, duration, maxDuration) {
  if (state.active || state.pending || state.draft)
    throw Error("Save or discard the current take first.");
  const start = cue(metadata.start, duration);
  if (!picture) throw Error("Picture is not ready.");
  if (!navigator.mediaDevices?.getUserMedia || !globalThis.MediaRecorder)
    throw Error("Microphone recording is unavailable. Upload a take instead.");
  const token = ++generation;
  emit({ pending: true, error: "", elapsed: 0 });
  try {
    const acquired = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: false,
        noiseSuppression: false,
        autoGainControl: false,
      },
    });
    if (token !== generation) {
      acquired.getTracks().forEach((t) => t.stop());
      return;
    }
    stream = acquired;
    video = picture;
    priorMute = video.muted;
    video.muted = true;
    video.currentTime = start;
    const mimeType = ["audio/webm;codecs=opus", "audio/mp4", "audio/webm"].find(
      (t) => MediaRecorder.isTypeSupported(t),
    );
    recorder = new MediaRecorder(stream, mimeType ? { mimeType } : undefined);
    const chunks = [];
    recorder.ondataavailable = (event) => {
      if (event.data.size) chunks.push(event.data);
    };
    recorder.onstop = () => {
      retain(new Blob(chunks, { type: recorder.mimeType }), {
        ...metadata,
        start,
        clock: "browser_playback",
      });
      release();
    };
    recorder.onerror = () => {
      emit({
        error:
          "Microphone capture failed. Any captured audio is retained for audition.",
      });
      stopRecording();
    };
    await video.play();
    if (token !== generation) {
      release();
      return;
    }
    recorder.start(250);
    const began = performance.now();
    emit({ active: true, pending: false });
    ticker = setInterval(
      () => emit({ elapsed: (performance.now() - began) / 1000 }),
      250,
    );
    timeout = setTimeout(
      stopRecording,
      Math.min(maxDuration, duration - start) * 1000,
    );
  } catch (error) {
    release();
    emit({
      error: `Microphone or picture unavailable: ${error.message}. Upload a take instead.`,
    });
  }
}
export function stopRecording() {
  generation++;
  if (recorder?.state === "recording") recorder.stop();
  release();
}
if (typeof window !== "undefined")
  window.addEventListener("pagehide", stopRecording);

if (typeof window !== "undefined")
  window.addEventListener("beforeunload", (event) => {
    if (state.draft || state.active || state.pending) {
      event.preventDefault();
      event.returnValue = "";
    }
  });
