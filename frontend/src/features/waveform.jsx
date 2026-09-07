import React, { useCallback } from "react";
import { loadWave, waveKey } from "../state/store.js";
import { time } from "../state/domain.js";

export function Wave({ pid, role, cid = "", state, label, position = 0, start = 0, end, bins = 600, select, ranges = [] }) {
  const stop = end ?? "";
  const key = waveKey(pid, role, cid, start, stop, bins);
  const wave = state.waveforms[key];
  const bind = useCallback(() => loadWave(pid, role, cid, start, stop, bins), [pid, role, cid, start, stop, bins]);
  const peaks = wave?.peaks || [];
  const first = wave?.start_s ?? start;
  const last = wave?.end_s ?? end ?? wave?.duration_s ?? 1;
  const span = Math.max(last - first, .001);
  const x = (value) => Math.max(0, Math.min(1000, (value - first) / span * 1000));
  return <div className="wave" ref={bind}>
    <div className="wave-label"><span>{label}</span><span>{time(first)} – {time(last)}</span></div>
    {wave?.error ? <p className="muted">Waveform unavailable: {wave.error}</p> : peaks.length ? (
      <svg viewBox="0 0 1000 64" preserveAspectRatio="none" role="img" aria-label={`${label}, visible audio from ${time(first)} to ${time(last)}`}>
        {ranges.filter((range) => range.end > first && range.start < last).map((range, index) => <rect key={index} className={`wave-range wave-range-${range.kind || "pending"}`} x={x(Math.max(first, range.start))} width={Math.max(2, x(Math.min(last, range.end)) - x(Math.max(first, range.start)))} y="0" height="64" />)}
        <path d={peaks.map((peak, index) => { const value = Math.max(0, Math.min(1, peak)); return `M${index * 1000 / peaks.length},${32 - value * 30}v${value * 60}`; }).join(" ")} fill="none" stroke="currentColor" strokeWidth="1.5" />
        {position >= first && position <= last && <line x1={x(position)} x2={x(position)} y1="0" y2="64" className="playhead" />}
      </svg>
    ) : <p className="muted">Loading measured waveform…</p>}
    {select && <input aria-label={`Seek ${label} in seconds`} type="range" min={first} max={last} step="0.01" value={Math.max(first, Math.min(position, last))} onChange={(event) => select(Number(event.target.value))} />}
  </div>;
}
