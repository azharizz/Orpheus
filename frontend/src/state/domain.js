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
export function pageWindow(items, page, size = 5) {
  const pages = Math.max(1, Math.ceil(items.length / size));
  const current = Math.min(Math.max(0, page), pages - 1);
  const start = current * size;
  return { items: items.slice(start, start + size), page: current, pages, start };
}
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

export function movieLanes(movie = {}, families = [], maxMarks = 360) {
  const events = movie.events || [];
  const step = Math.max(1, Math.ceil(events.length / maxMarks));
  return {
    events: events.filter((_, index) => index % step === 0),
    suggestions: movie.suggestions || [],
    noise: movie.noise_regions || [],
    accepted: families.flatMap((family) => (family.accepted_ranges || []).map((item) => ({ ...item, family_id: family.id, status: "accepted" }))),
    rejected: families.flatMap((family) => (family.rejected_ranges || []).map((item) => ({ ...item, family_id: family.id, status: "rejected" }))),
  };
}

export function workspaceTarget(search = window.location.search) {
  const params = new URLSearchParams(search);
  const at = Number(params.get("time"));
  return {
    time: Number.isFinite(at) && at >= 0 ? at : 0,
    family: params.get("family") || "",
    event: params.get("event") || "",
    view: params.get("view") === "movie" ? "movie" : "part",
  };
}

export function partWindow(center, duration, span = 15) {
  const width = Math.min(duration, Math.max(5, Number(span) || 15));
  const start = Math.max(0, Math.min(duration - width, Number(center) - width / 2));
  return [Number(start.toFixed(3)), Number((start + width).toFixed(3))];
}

export function eventDensity(events, start, end, bins = 120) {
  const counts = Array.from({ length: bins }, () => 0);
  const width = Math.max(end - start, Number.EPSILON);
  for (const event of events || []) {
    const at = Number(event.anchor_s ?? event.time_s);
    if (at >= start && at <= end) counts[Math.min(bins - 1, Math.floor((at - start) / width * bins))] += 1;
  }
  return counts;
}
