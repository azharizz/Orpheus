const ACTIVE_STATUSES = new Set(["queued", "pending", "starting", "running"]);

const clamp = (value) => Math.max(0, Math.min(100, value));

function safeStatus(value, fallback = "starting") {
  const status = String(value || fallback).toLowerCase();
  return status.replace(/[^a-z0-9_-]/g, "-") || fallback;
}

export function progressStatusLabel(status) {
  return {
    queued: "Queued",
    pending: "Queued",
    starting: "Starting",
    running: "In progress",
    complete: "Ready",
    review_required: "Needs review",
    stale: "Preview out of date",
    failed: "Could not finish",
    interrupted: "Interrupted",
    incomplete: "Incomplete",
  }[status] || String(status || "Starting").replaceAll("_", " ");
}

/**
 * Normalize persisted activity and an optimistic local operation into one
 * render model. An operation wins over an old completed/stale receipt while
 * its request is still active, but the persisted activity can still provide
 * the current phase and measured percentage once polling catches up.
 */
export function workflowProgressModel(activity = null, waiting = null) {
  if (!activity && !waiting) return null;
  const waitingStatus = safeStatus(waiting?.status, "running");
  const waitingActive = waiting && ACTIVE_STATUSES.has(waitingStatus);
  const persistedActive = activity && ACTIVE_STATUSES.has(safeStatus(activity.status));
  const source = waitingActive
    ? {
        ...(activity || {}),
        ...waiting,
        status: "running",
        phase: persistedActive ? activity.phase : waiting.phase,
        label: persistedActive ? activity.label : waiting.label,
        message: persistedActive ? activity.message : waiting.message,
        progress: persistedActive ? activity.progress : waiting.progress,
      }
    : activity || waiting;
  const status = safeStatus(source?.status, waiting ? "running" : "starting");
  const rawProgress = Number(source?.progress);
  const hasProgress = Number.isFinite(rawProgress);
  const progress = hasProgress ? clamp(rawProgress) : null;
  const phase = String(source?.phase || status).replaceAll("_", " ");
  const detail = source?.label || source?.message || waiting?.label || "Starting local work…";
  const cycle = Number(source?.cycle);
  const candidateCount = Number(source?.candidate_count);
  const counts = [
    Number.isFinite(cycle) && cycle > 0 ? `Cycle ${cycle}` : "",
    Number.isFinite(candidateCount) && candidateCount > 0
      ? `${candidateCount} candidate${candidateCount === 1 ? "" : "s"}`
      : "",
  ].filter(Boolean).join(" · ");
  const candidate = waitingActive && !persistedActive
    ? waiting?.render_id || ""
    : source?.render_id || activity?.render_id || waiting?.render_id || "";
  return {
    status,
    statusLabel: progressStatusLabel(status),
    phase,
    detail,
    counts,
    candidate,
    progress,
    hasProgress,
    active: ACTIVE_STATUSES.has(status),
    updatedAt: source?.updated_at || null,
  };
}
