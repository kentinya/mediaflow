import type { DashboardModel } from "../src/entities/dashboard/dashboard";

/** A wire-format snapshot matching the existing Python API response shape. */
export const dashboardPayload: Record<string, unknown> = {
  as_of: "2026-08-22T12:00:00+00:00",
  resource_libraries: 2,
  media_libraries: 3,
  files: { total: 12, ready: 9, unstable: 1, missing: 1, errors: 1 },
  tasks: {
    total: 4,
    pending: 1,
    running: 1,
    completed: 1,
    partial_success: 0,
    failed: 1,
    cancelled: 0,
    paused: 0,
  },
  jobs: {
    total: 2,
    pending: 1,
    running: 0,
    completed: 1,
    failed: 0,
    cancelled: 0,
  },
  pending_confirmations: 1,
  pending_metadata_reviews: 2,
  pending_classification_reviews: 0,
  dead_letter_notifications: 1,
  recent_failures: [
    {
      kind: "job",
      identifier: "job-failed",
      status: "failed",
      occurred_at: "2026-08-22T11:58:00+00:00",
      category: "processing_error",
    },
  ],
};

/** The expected normalized frontend model for the payload above. */
export const dashboardModel: DashboardModel = {
  asOf: "2026-08-22T12:00:00+00:00",
  resourceLibraries: 2,
  mediaLibraries: 3,
  files: { total: 12, ready: 9, unstable: 1, missing: 1, errors: 1 },
  tasks: {
    total: 4,
    pending: 1,
    running: 1,
    completed: 1,
    partialSuccess: 0,
    failed: 1,
    cancelled: 0,
    paused: 0,
  },
  jobs: {
    total: 2,
    pending: 1,
    running: 0,
    completed: 1,
    failed: 0,
    cancelled: 0,
  },
  pendingConfirmations: 1,
  pendingMetadataReviews: 2,
  pendingClassificationReviews: 0,
  deadLetterNotifications: 1,
  recentFailures: [
    {
      kind: "job",
      identifier: "job-failed",
      status: "failed",
      occurredAt: "2026-08-22T11:58:00+00:00",
      category: "processing_error",
    },
  ],
};

export function emptyDashboardPayload(): Record<string, unknown> {
  return {
    ...dashboardPayload,
    files: { total: 0, ready: 0, unstable: 0, missing: 0, errors: 0 },
    tasks: {
      total: 0,
      pending: 0,
      running: 0,
      completed: 0,
      partial_success: 0,
      failed: 0,
      cancelled: 0,
      paused: 0,
    },
    jobs: {
      total: 0,
      pending: 0,
      running: 0,
      completed: 0,
      failed: 0,
      cancelled: 0,
    },
    recent_failures: [],
  };
}
