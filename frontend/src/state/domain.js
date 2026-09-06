export const candidates = (p) => [
  ...(p.turn_details || []).flatMap((t) => t.candidates || []),
];
export function cue(value, duration) {
  const n = Number(value);
  if (value === "" || !Number.isFinite(n) || n < 0 || n >= duration)
    throw Error("Picture cue must be within the prepared scene.");
  return n;
}
export function validateFile(file, limit) {
  if (!file || !file.size) throw Error("Choose a non-empty media file.");
  if (file.size > limit)
    throw Error(`File exceeds ${Math.round(limit / 1048576)} MiB.`);
  return file;
}
export function seedRange(start, end, duration) {
  const range = [Number(start), Number(end)];
  if (
    range.some((value) => !Number.isFinite(value)) ||
    range[0] < 0 ||
    range[1] > duration ||
    range[1] <= range[0]
  )
    throw Error("Sound example needs a start before its end, inside the film.");
  return range;
}
export const pendingMatches = (family) =>
  (family?.pending_matches || family?.matches || []).filter(
    (match) => !match.decision || match.decision === "pending",
  );
export const matchRange = (match) =>
  match.range_s || match.target_range_s || [match.start_s, match.end_s];
export const time = (n) =>
  `${Math.floor((Number(n) || 0) / 60)
    .toString()
    .padStart(2, "0")}:${((Number(n) || 0) % 60).toFixed(3).padStart(6, "0")}`;
export function label(value) {
  const known = {
    review_required: "Review required",
    mono_analysis_copy: "Mono analysis copy",
    source_near_full_scale_samples: "Source near full scale",
  };
  return known[value] || String(value).replaceAll("_", " ");
}
export function matchVolume(level, levels) {
  const finite = levels.filter(Number.isFinite);
  return Number.isFinite(level) && finite.length
    ? Math.min(1, 10 ** ((Math.min(...finite) - level) / 20))
    : 1;
}
