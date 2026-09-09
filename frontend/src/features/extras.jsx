import React, { useEffect, useState } from "react";
import { api } from "../state/store.js";

function feature(extras, name) {
  const value = extras?.[name];
  return value && typeof value === "object" ? value : null;
}

export function useExtras() {
  const [extras, setExtras] = useState(null);
  useEffect(() => {
    let live = true;
    api("/api/extras")
      .then((value) => live && setExtras(value && typeof value === "object" ? value : null))
      .catch(() => live && setExtras(null));
    return () => {
      live = false;
    };
  }, []);
  return extras;
}

function bytesOf(base64) {
  const binary = atob(base64);
  const buffer = new Uint8Array(binary.length);
  for (let index = 0; index < binary.length; index += 1)
    buffer[index] = binary.charCodeAt(index);
  return buffer;
}

export function GenerateTake({ extras, disabled, onGenerated, onError }) {
  const [prompt, setPrompt] = useState("");
  const [seconds, setSeconds] = useState(5);
  const [busy, setBusy] = useState(false);
  const lyria = feature(extras, "lyria");
  const max = Number(lyria?.max_seconds) > 0 ? Number(lyria.max_seconds) : 10;
  if (!lyria) return null;
  async function generate() {
    if (!prompt.trim() || busy) return;
    setBusy(true);
    try {
      const made = await api("/api/lyria", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, seconds }),
      });
      const type = made.content_type || "audio/wav";
      const file = new File(
        [bytesOf(made.audio_base64)],
        `generated-${Date.now()}.wav`,
        { type },
      );
      onGenerated(file, made);
    } catch (error) {
      onError?.(error);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="generate-take">
      <label>
        Generate AI sound effect with Lyria{" "}
        <span className="muted">Optional</span>
        <input
          value={prompt}
          maxLength={500}
          placeholder="Dry leaves crushed underfoot"
          disabled={disabled || busy}
          onChange={(event) => setPrompt(event.target.value)}
        />
      </label>
      <label>
        Length · {seconds}s
        <input
          type="range"
          min={1}
          max={max}
          value={seconds}
          disabled={disabled || busy}
          onChange={(event) => setSeconds(Number(event.target.value))}
        />
      </label>
      <button
        type="button"
        disabled={disabled || busy || !prompt.trim()}
        onClick={generate}
      >
        {busy ? "Generating…" : "Generate"}
      </button>
    </div>
  );
}

export function StreamSource({ extras, busy, onImported, onError }) {
  const [url, setUrl] = useState("");
  const stream = feature(extras, "livestream");
  const [seconds, setSeconds] = useState(
    Number(stream?.default_seconds) > 0 ? Number(stream.default_seconds) : 120,
  );
  const [working, setWorking] = useState(false);
  if (!stream) return null;
  const maxCapture = Number(stream.max_seconds) > 0 ? Number(stream.max_seconds) : 600;
  async function pull() {
    if (!url.trim() || working) return;
    setWorking(true);
    try {
      const result = await api("/api/stream/import", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url, seconds }),
      });
      onImported(result.project);
    } catch (error) {
      onError?.(error);
    } finally {
      setWorking(false);
    }
  }
  return (
    <div className="stream-source">
      <label>
        Live stream address <span className="muted">Instead of a file</span>
        <input
          value={url}
          placeholder="https://example.com/live.m3u8"
          disabled={busy || working}
          onChange={(event) => setUrl(event.target.value)}
        />
      </label>
      <label>
        Capture · {seconds}s
        <input
          type="range"
          min={5}
          max={maxCapture}
          step={5}
          value={seconds}
          disabled={busy || working}
          onChange={(event) => setSeconds(Number(event.target.value))}
        />
      </label>
      <button type="button" disabled={busy || working || !url.trim()} onClick={pull}>
        {working ? "Capturing…" : "Capture stream"}
      </button>
    </div>
  );
}

export function NarrationInput({ extras, onFile }) {
  const [name, setName] = useState("");
  if (!feature(extras, "narration")) return null;
  return (
    <label className="file-input">
      <span>
        Narration <span className="muted">Optional · txt or md</span>
      </span>
      <strong>{name || "Choose narration"}</strong>
      <input
        type="file"
        accept=".txt,.md,.markdown"
        onChange={(event) => {
          const file = event.target.files[0] || null;
          setName(file?.name || "");
          onFile(file);
        }}
      />
    </label>
  );
}

export async function attachNarration(projectId, file) {
  if (!file || !projectId) return null;
  const query = new URLSearchParams({
    project_id: projectId,
    filename: file.name,
  });
  const request = api(`/api/narration?${query}`, {
    method: "POST",
    headers: { "Content-Type": "text/plain" },
    body: file,
  });
  const bounded = new Promise((resolve) => setTimeout(() => resolve(null), 20000));
  return Promise.race([request, bounded]).catch(() => null);
}
