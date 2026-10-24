import { describe, expect, it } from "vitest";

import { normalizeAutomationSettings } from "./automation-settings";

/**
 * A43-01 — current consumer membership in the typed normalizer.
 *
 * The API now separates the current population (fresh-at-read instances) from
 * retained history (stopped/expired identities). These cases pin the
 * fail-closed normalizer: a collective claim is only accepted when it agrees
 * with the instance evidence, and a document that mixes the two populations
 * never becomes a deployment-wide success.
 */

const FIELDS = [
  "automation.maximumActiveJobs",
  "automation.staleJobAgeSeconds",
  "automation.workerPollSeconds",
  "automation.schedulerPollSeconds",
] as const;

function document(overrides: Record<string, unknown> = {}) {
  return {
    fields: FIELDS.map((fieldPath) => ({
      fieldPath,
      label: fieldPath,
      unit: "秒",
      valueType: "number",
      minimum: null,
      maximum: null,
      meaning: "meaning",
      notMeaning: "not meaning",
      consumer: null,
      integer: false,
    })),
    target: {
      revisionId: "rev-1",
      revisionVersion: 3,
      digest: "digest-1",
      values: {
        "automation.maximumActiveJobs": 100,
        "automation.staleJobAgeSeconds": 3600,
        "automation.workerPollSeconds": 2,
        "automation.schedulerPollSeconds": 5,
      },
    },
    consumers: {
      worker: {
        service: "worker",
        field: "automation.workerPollSeconds",
        publishedValue: 2,
        adopted: true,
        instanceCount: 1,
        historyCount: 1,
        history: [
          {
            instanceId: "worker-stopped",
            liveness: "stopped",
            durableState: "historical_registration_stopped",
            nextAction: "retained registration, not a current consumer",
          },
        ],
        instances: [
          {
            instanceId: "worker-live",
            liveness: "live",
            status: "adopted",
            effectiveValue: 2,
            publishedRevisionId: "rev-1",
            reportedRevisionId: "rev-1",
            reportedAt: "2026-03-16T00:00:00+00:00",
            appliedFields: ["automation.workerPollSeconds"],
            overrideSource: null,
            durableState: "adopted_current_publication",
            nextAction: "none",
          },
        ],
        durableState: "adopted_current_publication",
        nextAction: "none",
      },
      scheduler: {
        service: "scheduler",
        field: "automation.schedulerPollSeconds",
        publishedValue: 5,
        adopted: true,
        instanceCount: 1,
        historyCount: 0,
        history: [],
        instances: [
          {
            instanceId: "scheduler-live",
            liveness: "live",
            status: "adopted",
            effectiveValue: 5,
            publishedRevisionId: "rev-1",
            reportedRevisionId: "rev-1",
            reportedAt: "2026-03-16T00:00:00+00:00",
            appliedFields: ["automation.schedulerPollSeconds"],
            overrideSource: null,
            durableState: "adopted_current_publication",
            nextAction: "none",
          },
        ],
        durableState: "adopted_current_publication",
        nextAction: "none",
      },
    },
    adoption: { consumers: 2, adoptedConsumers: 2, allAdopted: true },
    canManage: true,
    ...overrides,
  };
}

function workerConsumers(mutate: (worker: Record<string, unknown>) => void) {
  const base = document();
  mutate(base.consumers.worker as unknown as Record<string, unknown>);
  return base;
}

describe("normalizeAutomationSettings current membership", () => {
  it("keeps a retained stopped predecessor separate from the live consumer", () => {
    const model = normalizeAutomationSettings(document());
    const worker = model.consumers.find((item) => item.service === "worker")!;
    expect(worker.adopted).toBe(true);
    expect(worker.instances.map((item) => item.instanceId)).toEqual([
      "worker-live",
    ]);
    expect(worker.instanceCount).toBe(1);
    expect(worker.historyCount).toBe(1);
    expect(worker.history.map((item) => item.instanceId)).toEqual([
      "worker-stopped",
    ]);
    expect(model.adoption.allAdopted).toBe(true);
  });

  it("never accepts a claim backed by a live row inside history", () => {
    const model = normalizeAutomationSettings(
      workerConsumers((worker) => {
        worker["history"] = [
          {
            instanceId: "worker-claimed-live",
            liveness: "live",
            durableState: "adopted_current_publication",
            nextAction: "none",
          },
        ];
      }),
    );
    const row = model.consumers.find((item) => item.service === "worker")!;
    expect(row.adopted).toBe(false);
    expect(model.adoption.allAdopted).toBe(false);
  });

  it("never accepts a claim whose instanceCount disagrees with its rows", () => {
    const model = normalizeAutomationSettings(
      workerConsumers((worker) => {
        worker["instanceCount"] = 2;
      }),
    );
    const row = model.consumers.find((item) => item.service === "worker")!;
    expect(row.adopted).toBe(false);
    expect(model.adoption.allAdopted).toBe(false);
  });

  it("keeps a missing current population unproven, whatever the flag says", () => {
    const model = normalizeAutomationSettings(
      workerConsumers((worker) => {
        worker["instances"] = [];
        worker["instanceCount"] = 0;
        worker["adopted"] = true;
      }),
    );
    const row = model.consumers.find((item) => item.service === "worker")!;
    expect(row.adopted).toBe(false);
    expect(row.durableState).toBe("adopted_current_publication");
    expect(model.adoption.allAdopted).toBe(false);
  });

  it("degrades an absent historyCount to the bounded rows it shows", () => {
    const model = normalizeAutomationSettings(
      workerConsumers((worker) => {
        delete worker["historyCount"];
      }),
    );
    const row = model.consumers.find((item) => item.service === "worker")!;
    expect(row.historyCount).toBe(1);
  });

  it("rejects a malformed history entry instead of trusting the rest", () => {
    expect(() =>
      normalizeAutomationSettings(
        workerConsumers((worker) => {
          worker["history"] = [{ liveness: "stopped" }];
        }),
      ),
    ).toThrow();
  });

  it("keeps an unreadable read explicitly unproven rather than empty-but-fine", () => {
    const model = normalizeAutomationSettings(
      workerConsumers((worker) => {
        worker["instances"] = [];
        worker["instanceCount"] = 0;
        worker["adopted"] = false;
        worker["durableState"] = "consumer_registration_unreadable";
        worker["nextAction"] = "check database health/permissions and re-read";
      }),
    );
    const row = model.consumers.find((item) => item.service === "worker")!;
    expect(row.adopted).toBe(false);
    expect(row.durableState).toBe("consumer_registration_unreadable");
    expect(row.nextAction).toContain("database");
  });
});
