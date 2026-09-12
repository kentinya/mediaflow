/**
 * Frontend-owned bounded Notification models.
 *
 * The Python contract exposes the V2 Notification journey as digest-free
 * operator documents under ``/api/v1/operations/notifications/``: a Webhook
 * definitions page with the exact immutable Active identity and open-Draft
 * state, a definition detail, a Draft editor document, a bounded signed-test
 * outcome, and a delivery detail with permission-aware recovery actions.
 * Delivery list/paging and the recovery mutations reuse the existing backend
 * routes whose optimistic status/update fences and permission checks remain
 * authoritative.
 *
 * Normalization is deliberately fail-closed: unknown status values, a coerced
 * boolean, a missing required identity or a contradictory block make the whole
 * response malformed so the UI renders no control instead of guessing
 * authority. No document here ever carries a revision digest, a resolved
 * secret, a delivery body or an endpoint credential.
 */

import {
  normalizeBoolean,
  normalizeBoundedCount,
  normalizeBoundedText,
  normalizeEnum,
  normalizeOptionalText,
  readRecord,
} from "../shared/normalize";
import {
  normalizeActionTransport,
  type ActionModel,
  type ActionTransportContract,
} from "./action-transport";

export const NOTIFICATION_EVENT_TYPES = [
  "job.completed",
  "job.failed",
  "job.cancelled",
  "schedule.emitted",
] as const;
export type NotificationEventType = (typeof NOTIFICATION_EVENT_TYPES)[number];

export const NOTIFICATION_DELIVERY_STATUSES = [
  "pending",
  "delivering",
  "retry",
  "delivered",
  "dead-letter",
] as const;
export type NotificationDeliveryStatus =
  (typeof NOTIFICATION_DELIVERY_STATUSES)[number];

export const NOTIFICATION_OPEN_DRAFT_STATUSES = ["draft", "validated"] as const;

/**
 * Definition and delivery identities travel in exact route segments: a strict
 * URI-safe value is part of the contract, and anything else (paths, spaces,
 * percent-encoding) is malformed evidence rather than a coercible identity.
 */
export const NOTIFICATION_URI_SAFE_SEGMENT = /^[A-Za-z0-9][A-Za-z0-9._-]*$/;

function uriSafeSegment(
  source: Record<string, unknown>,
  field: string,
  maxLength: number,
): string {
  const value = text(source, field, maxLength);
  if (!NOTIFICATION_URI_SAFE_SEGMENT.test(value)) {
    return fail(field);
  }
  return value;
}

/**
 * Where the definition durably lives: in the immutable Active configuration,
 * or only inside an open successor Draft (newly created or copied). A
 * document without this exact state marker is malformed so no Draft can ever
 * be rendered as Active.
 */
export const NOTIFICATION_DEFINITION_STATES = ["active", "draft-only"] as const;

export const WEBHOOK_SECRET_READINESS_STATES = ["SET", "UNSET"] as const;

export const WEBHOOK_TEST_OUTCOMES = ["success", "failure"] as const;

/** The bounded test outcome categories the signed-test service may publish. */
export const WEBHOOK_TEST_CATEGORIES = [
  "timeout",
  "transport",
  "missing_secret",
  "invalid_definition",
] as const;

export const WEBHOOK_TEST_HTTP_CATEGORY = /^http_[1-5]\d\d$/;

export const DELIVERY_LEASE_STATES = [
  "not_leased",
  "active",
  "expired",
] as const;

export const DELIVERY_RECOVERY_ACTIONS = [
  "requeue-dead-letter",
  "resolve-stale",
] as const;

/**
 * The exact action kinds the Notification journey documents may advertise.
 * Each kind is bound to one method, one owned route and one exact suffix; the
 * definition-edit contract carries a single `*` segment pinned to the exact
 * Webhook identity, and the collection-level create action is bound to the
 * exact open-Draft revision.
 */
export type NotificationActionKind =
  | "webhook-detail"
  | "webhook-test"
  | "webhook-edit"
  | "webhook-copy"
  | "webhook-enable"
  | "webhook-disable"
  | "webhook-draft-create"
  | "webhook-activate"
  | "list-create"
  | "list-create-draft"
  | "draft-create"
  | "draft-save"
  | "draft-validate"
  | "draft-activate"
  | "draft-test"
  | "delivery-detail"
  | "delivery-requeue"
  | "delivery-resolve-stale";

const OPERATIONS_WEBHOOKS_ROUTE = "/api/v1/operations/notifications/webhooks/";
const OPERATIONS_DELIVERIES_ROUTE =
  "/api/v1/operations/notifications/deliveries/";
const CONFIGURATION_REVISIONS_ROUTE = "/api/v1/configuration/revisions/";
const NOTIFICATIONS_ROUTE = "/api/v1/notifications/";

type NotificationActionContract = ActionTransportContract;

export const NOTIFICATION_ACTION_CONTRACTS: Readonly<
  Record<NotificationActionKind, NotificationActionContract>
> = {
  "webhook-detail": {
    method: "GET",
    routePrefix: OPERATIONS_WEBHOOKS_ROUTE,
    suffix: "",
    requiresConfirmation: false,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "webhook-test": {
    method: "POST",
    routePrefix: OPERATIONS_WEBHOOKS_ROUTE,
    suffix: "test",
    requiresConfirmation: false,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "webhook-edit": {
    method: "PUT",
    routePrefix: CONFIGURATION_REVISIONS_ROUTE,
    // One URI-safe parameter segment pinned to the exact Webhook identity.
    suffix: "objects/webhooks/*",
    requiresConfirmation: false,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "webhook-copy": {
    method: "POST",
    routePrefix: CONFIGURATION_REVISIONS_ROUTE,
    suffix: "objects/webhooks/*/copy",
    requiresConfirmation: false,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "webhook-enable": {
    method: "POST",
    routePrefix: CONFIGURATION_REVISIONS_ROUTE,
    suffix: "objects/webhooks/*/enable",
    requiresConfirmation: false,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "webhook-disable": {
    method: "POST",
    routePrefix: CONFIGURATION_REVISIONS_ROUTE,
    suffix: "objects/webhooks/*/disable",
    requiresConfirmation: false,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "webhook-draft-create": {
    method: "POST",
    routePrefix: CONFIGURATION_REVISIONS_ROUTE,
    suffix: "successor",
    requiresConfirmation: false,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "webhook-activate": {
    method: "POST",
    routePrefix: OPERATIONS_WEBHOOKS_ROUTE,
    suffix: "activate-draft",
    requiresConfirmation: true,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "list-create": {
    method: "POST",
    routePrefix: CONFIGURATION_REVISIONS_ROUTE,
    // The create transport is bound to the exact open-Draft revision.
    suffix: "objects/webhooks",
    requiresConfirmation: false,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "list-create-draft": {
    method: "POST",
    routePrefix: CONFIGURATION_REVISIONS_ROUTE,
    suffix: "successor",
    requiresConfirmation: false,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "draft-create": {
    method: "POST",
    routePrefix: CONFIGURATION_REVISIONS_ROUTE,
    suffix: "successor",
    requiresConfirmation: false,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "draft-save": {
    method: "PUT",
    routePrefix: CONFIGURATION_REVISIONS_ROUTE,
    // One URI-safe parameter segment pinned to the exact Webhook identity.
    suffix: "objects/webhooks/*",
    requiresConfirmation: false,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "draft-validate": {
    method: "POST",
    routePrefix: CONFIGURATION_REVISIONS_ROUTE,
    suffix: "validate",
    requiresConfirmation: false,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "draft-activate": {
    method: "POST",
    routePrefix: OPERATIONS_WEBHOOKS_ROUTE,
    suffix: "activate-draft",
    requiresConfirmation: true,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "draft-test": {
    method: "POST",
    routePrefix: OPERATIONS_WEBHOOKS_ROUTE,
    suffix: "test",
    requiresConfirmation: false,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "delivery-detail": {
    method: "GET",
    routePrefix: OPERATIONS_DELIVERIES_ROUTE,
    suffix: "",
    requiresConfirmation: false,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "delivery-requeue": {
    method: "POST",
    routePrefix: NOTIFICATIONS_ROUTE,
    suffix: "requeue",
    requiresConfirmation: true,
    offeredWithoutTransport: false,
    objectBound: true,
  },
  "delivery-resolve-stale": {
    method: "POST",
    routePrefix: NOTIFICATIONS_ROUTE,
    suffix: "resolve-stale",
    requiresConfirmation: true,
    offeredWithoutTransport: false,
    objectBound: true,
  },
};

export type NotificationActionModel = ActionModel;

export class NotificationNormalizationError extends Error {
  constructor(field: string) {
    super(
      `notification response did not match the expected contract (${field})`,
    );
    this.name = "NotificationNormalizationError";
  }
}

function fail(field: string): never {
  throw new NotificationNormalizationError(field);
}

function enumOrFail<T extends readonly string[]>(
  value: unknown,
  field: string,
  allowed: T,
): T[number] {
  try {
    return normalizeEnum(value, field, allowed);
  } catch {
    return fail(field);
  }
}

function text(
  source: Record<string, unknown>,
  field: string,
  maxLength?: number,
): string {
  try {
    return normalizeBoundedText(source[field], field, maxLength);
  } catch {
    return fail(field);
  }
}

function optionalText(
  source: Record<string, unknown>,
  field: string,
  maxLength?: number,
): string | null {
  try {
    return normalizeOptionalText(source[field], field, maxLength);
  } catch {
    return fail(field);
  }
}

function flag(source: Record<string, unknown>, field: string): boolean {
  try {
    return normalizeBoolean(source[field], field);
  } catch {
    return fail(field);
  }
}

function count(source: Record<string, unknown>, field: string): number {
  try {
    return normalizeBoundedCount(source[field], field);
  } catch {
    return fail(field);
  }
}

function optionalCount(
  source: Record<string, unknown>,
  field: string,
): number | null {
  if (source[field] === null || source[field] === undefined) {
    return null;
  }
  return count(source, field);
}

function optionalRecord(
  value: unknown,
  field: string,
): Record<string, unknown> | null {
  if (value === null || value === undefined) {
    return null;
  }
  return readRecord(value, field);
}

function enumList<T extends string>(
  source: Record<string, unknown>,
  field: string,
  allowed: readonly T[],
  maximum: number,
): T[] {
  const raw = source[field];
  if (!Array.isArray(raw) || raw.length > maximum) {
    return fail(field);
  }
  return raw.map((item, index) =>
    enumOrFail(item, `${field}[${index}]`, allowed),
  );
}

export function normalizeNotificationAction(
  value: unknown,
  field: string,
  kind: NotificationActionKind,
  identity: string | null = null,
  parameter: string | null = null,
): NotificationActionModel {
  try {
    return normalizeActionTransport(
      value,
      field,
      NOTIFICATION_ACTION_CONTRACTS[kind],
      identity,
      parameter,
    );
  } catch {
    return fail(field);
  }
}

export interface NotificationActiveConfigurationModel {
  readonly revisionId: string;
  readonly version: number;
  readonly revisionSequence: number;
  readonly status: string;
}

export function normalizeNotificationActiveConfiguration(
  value: unknown,
  field = "activeConfiguration",
): NotificationActiveConfigurationModel | null {
  if (value === null || value === undefined) {
    return null;
  }
  const source = readRecord(value, field);
  return {
    revisionId: text(source, "revisionId"),
    version: count(source, "version"),
    revisionSequence: count(source, "revisionSequence"),
    status: text(source, "status"),
  };
}

export interface NotificationDraftStateModel {
  readonly present: boolean;
  readonly reason: string | null;
  readonly revisionId: string | null;
  readonly revisionVersion: number | null;
  readonly revisionStatus: string | null;
  readonly baseActiveRevisionId: string | null;
  readonly updatedAt: string | null;
  readonly validatedAt: string | null;
  readonly validationErrors: readonly string[];
}

export function normalizeNotificationDraftState(
  value: unknown,
  field = "draftState",
): NotificationDraftStateModel {
  const source = readRecord(value, field);
  const present = flag(source, "present");
  const revisionId = optionalText(source, "revisionId");
  const revisionVersion = optionalCount(source, "revisionVersion");
  const reason = optionalText(source, "reason");
  if (present && (revisionId === null || revisionVersion === null)) {
    // An open Draft is a durable revision: an offered Draft without its
    // exact optimistic identity is malformed evidence.
    return fail(`${field}.revisionId`);
  }
  if (!present && (revisionId !== null || revisionVersion !== null)) {
    return fail(`${field}.present`);
  }
  const errors = source["validationErrors"];
  if (errors !== null && errors !== undefined && !Array.isArray(errors)) {
    return fail(`${field}.validationErrors`);
  }
  if (Array.isArray(errors) && errors.length > 100) {
    return fail(`${field}.validationErrors`);
  }
  return {
    present,
    reason,
    revisionId,
    revisionVersion,
    revisionStatus: optionalText(source, "revisionStatus"),
    baseActiveRevisionId: optionalText(source, "baseActiveRevisionId"),
    updatedAt: optionalText(source, "updatedAt"),
    validatedAt: optionalText(source, "validatedAt"),
    validationErrors: (errors ?? []).map((item, index) =>
      normalizeBoundedText(item, `${field}.validationErrors[${index}]`),
    ),
  };
}

/** The deployment-owned secret reference readiness, never a secret value. */
export interface WebhookSecretReadinessModel {
  readonly field: string;
  readonly env: string;
  readonly state: (typeof WEBHOOK_SECRET_READINESS_STATES)[number];
}

function normalizeSecretReadiness(
  value: unknown,
  field: string,
): WebhookSecretReadinessModel {
  const source = readRecord(value, field);
  return {
    field: text(source, "field"),
    env: text(source, "env"),
    state: enumOrFail(
      source["state"],
      `${field}.state`,
      WEBHOOK_SECRET_READINESS_STATES,
    ),
  };
}

/**
 * The bounded editable Webhook form document plus its deployment readiness.
 * Only the canonical Webhook fields are modelled; the canonical server
 * validator rejects everything else, so an unknown field can never travel
 * from the browser into a Draft.
 */
export interface WebhookDefinitionDocumentModel {
  readonly id: string;
  readonly url: string;
  readonly secretEnv: string;
  readonly events: readonly NotificationEventType[];
  readonly enabled: boolean;
  readonly timeoutSeconds: number;
  readonly maxAttempts: number;
  readonly baseRetrySeconds: number;
  readonly maxRetrySeconds: number;
  readonly secretReadiness: readonly WebhookSecretReadinessModel[];
  readonly structuralValid: boolean;
  readonly validationError: string | null;
}

function positiveBoundedNumber(
  source: Record<string, unknown>,
  key: string,
  field: string,
): number {
  const value = source[key];
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) {
    return fail(field);
  }
  return value;
}

export function normalizeWebhookDefinitionDocument(
  value: unknown,
  field = "webhook",
): WebhookDefinitionDocumentModel {
  const source = readRecord(value, field);
  const rawEvents = source["events"];
  if (!Array.isArray(rawEvents) || rawEvents.length === 0) {
    return fail(`${field}.events`);
  }
  const rawReadiness = source["secretReadiness"];
  if (!Array.isArray(rawReadiness) || rawReadiness.length > 16) {
    return fail(`${field}.secretReadiness`);
  }
  return {
    id: uriSafeSegment(source, "id", 64),
    url: text(source, "url", 2048),
    secretEnv: text(source, "secretEnv", 128),
    events: rawEvents.map((item, index) =>
      enumOrFail(item, `${field}.events[${index}]`, NOTIFICATION_EVENT_TYPES),
    ),
    enabled: flag(source, "enabled"),
    timeoutSeconds: positiveBoundedNumber(
      source,
      "timeoutSeconds",
      `${field}.timeoutSeconds`,
    ),
    maxAttempts: count(source, "maxAttempts"),
    baseRetrySeconds: positiveBoundedNumber(
      source,
      "baseRetrySeconds",
      `${field}.baseRetrySeconds`,
    ),
    maxRetrySeconds: positiveBoundedNumber(
      source,
      "maxRetrySeconds",
      `${field}.maxRetrySeconds`,
    ),
    secretReadiness: rawReadiness.map((item, index) =>
      normalizeSecretReadiness(item, `${field}.secretReadiness[${index}]`),
    ),
    structuralValid: flag(source, "structuralValid"),
    validationError: optionalText(source, "validationError", 384),
  };
}

export interface WebhookDefinitionModel {
  readonly document: WebhookDefinitionDocumentModel;
  readonly definitionState: (typeof NOTIFICATION_DEFINITION_STATES)[number];
  readonly draftState: NotificationDraftStateModel;
  readonly activeConfiguration: NotificationActiveConfigurationModel | null;
  readonly actions: {
    readonly detail: NotificationActionModel;
    readonly test: NotificationActionModel;
    readonly edit: NotificationActionModel;
    readonly copy: NotificationActionModel;
    readonly enable: NotificationActionModel;
    readonly disable: NotificationActionModel;
    readonly draftCreate: NotificationActionModel;
    readonly activate: NotificationActionModel;
  };
}

export function normalizeWebhookDefinition(
  value: unknown,
  field = "webhook",
): WebhookDefinitionModel {
  const source = readRecord(value, field);
  const document = normalizeWebhookDefinitionDocument(source, field);
  const draftState = normalizeNotificationDraftState(
    source["draftState"],
    `${field}.draftState`,
  );
  const activeConfiguration = normalizeNotificationActiveConfiguration(
    source["activeConfiguration"],
    `${field}.activeConfiguration`,
  );
  const actions = readRecord(source["actions"], `${field}.actions`);
  const identity = document.id;
  return {
    document,
    definitionState: enumOrFail(
      source["definitionState"],
      `${field}.definitionState`,
      NOTIFICATION_DEFINITION_STATES,
    ),
    draftState,
    activeConfiguration,
    actions: {
      detail: normalizeNotificationAction(
        actions["detail"],
        `${field}.actions.detail`,
        "webhook-detail",
        identity,
      ),
      test: normalizeNotificationAction(
        actions["test"],
        `${field}.actions.test`,
        "webhook-test",
        identity,
      ),
      edit: normalizeNotificationAction(
        actions["edit"],
        `${field}.actions.edit`,
        "webhook-edit",
        draftState.revisionId,
        identity,
      ),
      copy: normalizeNotificationAction(
        actions["copy"],
        `${field}.actions.copy`,
        "webhook-copy",
        draftState.revisionId,
        identity,
      ),
      enable: normalizeNotificationAction(
        actions["enable"],
        `${field}.actions.enable`,
        "webhook-enable",
        draftState.revisionId,
        identity,
      ),
      disable: normalizeNotificationAction(
        actions["disable"],
        `${field}.actions.disable`,
        "webhook-disable",
        draftState.revisionId,
        identity,
      ),
      draftCreate: normalizeNotificationAction(
        actions["draftCreate"],
        `${field}.actions.draftCreate`,
        "webhook-draft-create",
        activeConfiguration?.revisionId ?? null,
      ),
      activate: normalizeNotificationAction(
        actions["activate"],
        `${field}.actions.activate`,
        "webhook-activate",
        identity,
      ),
    },
  };
}

export interface NotificationDefinitionsPage {
  readonly activeConfiguration: NotificationActiveConfigurationModel | null;
  readonly items: readonly WebhookDefinitionModel[];
  readonly total: number;
  readonly truncated: boolean;
  readonly draftState: NotificationDraftStateModel;
  readonly supportedEvents: readonly NotificationEventType[];
  readonly actions: {
    readonly create: NotificationActionModel;
    readonly createDraft: NotificationActionModel;
  };
}

export function normalizeNotificationDefinitionsPage(
  payload: unknown,
): NotificationDefinitionsPage {
  const source = readRecord(payload, "notification_definitions");
  const rawItems = source["items"];
  if (!Array.isArray(rawItems) || rawItems.length > 100) {
    return fail("items");
  }
  const actions = readRecord(source["actions"], "actions");
  const activeConfiguration = normalizeNotificationActiveConfiguration(
    source["activeConfiguration"],
  );
  const draftState = normalizeNotificationDraftState(source["draftState"]);
  return {
    activeConfiguration,
    items: rawItems.map((item) => normalizeWebhookDefinition(item, "items[]")),
    total: count(source, "total"),
    truncated: flag(source, "truncated"),
    draftState,
    supportedEvents: enumList(
      source,
      "supportedEvents",
      NOTIFICATION_EVENT_TYPES,
      16,
    ),
    actions: {
      create: normalizeNotificationAction(
        actions["create"],
        "actions.create",
        "list-create",
        draftState.revisionId,
      ),
      createDraft: normalizeNotificationAction(
        actions["createDraft"],
        "actions.createDraft",
        "list-create-draft",
        activeConfiguration?.revisionId ?? null,
      ),
    },
  };
}

export interface NotificationDraftDocumentModel {
  readonly webhookId: string;
  readonly activeConfiguration: NotificationActiveConfigurationModel | null;
  /** The Active-definition form values; null for a Draft-only definition. */
  readonly webhook: WebhookDefinitionDocumentModel | null;
  readonly draft: {
    readonly revisionId: string;
    readonly revisionVersion: number;
    readonly revisionStatus: string;
    readonly baseActiveRevisionId: string | null;
    readonly updatedAt: string | null;
    readonly validatedAt: string | null;
    readonly validationErrors: readonly string[];
    readonly webhook: WebhookDefinitionDocumentModel;
  } | null;
  readonly supportedEvents: readonly NotificationEventType[];
  readonly actions: {
    readonly createDraft: NotificationActionModel;
    readonly save: NotificationActionModel;
    readonly validate: NotificationActionModel;
    readonly activate: NotificationActionModel;
    readonly test: NotificationActionModel;
  };
}

export function normalizeNotificationDraftDocument(
  payload: unknown,
): NotificationDraftDocumentModel {
  const source = readRecord(payload, "notification_definition_draft");
  const webhookId = uriSafeSegment(source, "webhookId", 64);
  const activeConfiguration = normalizeNotificationActiveConfiguration(
    source["activeConfiguration"],
  );
  const activeWebhook =
    source["webhook"] === null || source["webhook"] === undefined
      ? null
      : normalizeWebhookDefinitionDocument(source["webhook"], "webhook");
  const rawDraft = optionalRecord(source["draft"], "draft");
  let draft: NotificationDraftDocumentModel["draft"] = null;
  if (rawDraft !== null) {
    const rawWebhook = optionalRecord(rawDraft["webhook"], "draft.webhook");
    if (rawWebhook === null) {
      return fail("draft.webhook");
    }
    const errors = rawDraft["validationErrors"];
    if (!Array.isArray(errors) || errors.length > 100) {
      return fail("draft.validationErrors");
    }
    draft = {
      revisionId: text(rawDraft, "revisionId"),
      revisionVersion: count(rawDraft, "revisionVersion"),
      revisionStatus: enumOrFail(
        rawDraft["revisionStatus"],
        "draft.revisionStatus",
        NOTIFICATION_OPEN_DRAFT_STATUSES,
      ),
      baseActiveRevisionId: optionalText(rawDraft, "baseActiveRevisionId"),
      updatedAt: optionalText(rawDraft, "updatedAt"),
      validatedAt: optionalText(rawDraft, "validatedAt"),
      validationErrors: errors.map((item, index) =>
        normalizeBoundedText(item, `draft.validationErrors[${index}]`),
      ),
      webhook: normalizeWebhookDefinitionDocument(rawWebhook, "draft.webhook"),
    };
  }
  const actions = readRecord(source["actions"], "actions");
  return {
    webhookId,
    activeConfiguration,
    webhook: activeWebhook,
    draft,
    supportedEvents: enumList(
      source,
      "supportedEvents",
      NOTIFICATION_EVENT_TYPES,
      16,
    ),
    actions: {
      createDraft: normalizeNotificationAction(
        actions["createDraft"],
        "actions.createDraft",
        "draft-create",
        activeConfiguration?.revisionId ?? null,
      ),
      save: normalizeNotificationAction(
        actions["save"],
        "actions.save",
        "draft-save",
        draft?.revisionId ?? null,
        draft?.webhook.id ?? webhookId,
      ),
      validate: normalizeNotificationAction(
        actions["validate"],
        "actions.validate",
        "draft-validate",
        draft?.revisionId ?? null,
      ),
      activate: normalizeNotificationAction(
        actions["activate"],
        "actions.activate",
        "draft-activate",
        webhookId,
      ),
      test: normalizeNotificationAction(
        actions["test"],
        "actions.test",
        "draft-test",
        webhookId,
      ),
    },
  };
}

export interface WebhookTestResultModel {
  readonly testId: string | null;
  readonly webhookId: string;
  readonly revisionId: string;
  readonly revisionVersion: number;
  readonly revisionStatus: string;
  readonly outcome: (typeof WEBHOOK_TEST_OUTCOMES)[number];
  readonly category: string;
  readonly responseStatus: number | null;
  readonly message: string;
  readonly durableState: string;
  readonly retrySafe: boolean;
  readonly nextAction: string;
}

/** The exact mutation identity a success document must answer for. */
export interface WebhookTestRequestBinding {
  readonly webhookId: string;
  readonly revisionId: string;
  readonly version: number;
}

export function normalizeWebhookTestResult(
  payload: unknown,
  requested: WebhookTestRequestBinding,
): WebhookTestResultModel {
  const source = readRecord(payload, "webhook_test_result");
  const revision = readRecord(source["revision"], "revision");
  if ("digest" in revision) {
    // The digest is server-side binding evidence; an operator test outcome
    // that carries one is malformed contract data, never rendered.
    return fail("revision.digest");
  }
  const webhook = readRecord(source["webhook"], "webhook");
  const category = text(source, "category", 64);
  const isBoundedCategory =
    (WEBHOOK_TEST_CATEGORIES as readonly string[]).includes(category) ||
    WEBHOOK_TEST_HTTP_CATEGORY.test(category);
  if (!isBoundedCategory) {
    return fail("category");
  }
  const responseStatus = optionalCount(source, "responseStatus");
  if (
    responseStatus !== null &&
    (responseStatus < 100 || responseStatus > 599)
  ) {
    return fail("responseStatus");
  }
  const model = {
    testId: optionalText(source, "testId", 128),
    webhookId: uriSafeSegment(webhook, "id", 64),
    revisionId: text(revision, "revisionId", 128),
    revisionVersion: count(revision, "version"),
    revisionStatus: text(revision, "status", 32),
    outcome: enumOrFail(source["outcome"], "outcome", WEBHOOK_TEST_OUTCOMES),
    category,
    responseStatus,
    message: text(source, "message", 512),
    durableState: text(source, "durableState", 128),
    retrySafe: flag(source, "retrySafe"),
    nextAction: text(source, "nextAction", 512),
  };
  if (
    model.webhookId !== requested.webhookId ||
    model.revisionId !== requested.revisionId ||
    model.revisionVersion !== requested.version
  ) {
    // A response about another Webhook or another revision never renders as
    // the outcome of this explicit test.
    return fail("webhook");
  }
  return model;
}

export interface NotificationActivationModel {
  readonly activatedRevisionId: string;
  readonly activatedVersion: number;
  readonly revisionSequence: number;
  readonly activeConfiguration: NotificationActiveConfigurationModel | null;
  readonly webhook: WebhookDefinitionDocumentModel | null;
}

export interface NotificationActivationRequestBinding {
  readonly webhookId: string;
  readonly revisionId: string;
  readonly version: number;
}

export function normalizeNotificationActivation(
  payload: unknown,
  requested: NotificationActivationRequestBinding,
): NotificationActivationModel {
  const source = readRecord(payload, "notification_activation");
  const rawWebhook = optionalRecord(source["webhook"], "webhook");
  const model = {
    activatedRevisionId: text(source, "activatedRevisionId", 128),
    activatedVersion: count(source, "activatedVersion"),
    revisionSequence: count(source, "revisionSequence"),
    activeConfiguration: normalizeNotificationActiveConfiguration(
      source["activeConfiguration"],
    ),
    webhook:
      rawWebhook === null
        ? null
        : normalizeWebhookDefinitionDocument(rawWebhook, "webhook"),
  };
  if (
    model.webhook === null ||
    model.webhook.id !== requested.webhookId ||
    text(source, "publishedFromRevisionId", 128) !== requested.revisionId ||
    count(source, "publishedFromVersion") !== requested.version ||
    model.activeConfiguration === null ||
    model.activeConfiguration.revisionId !== model.activatedRevisionId ||
    model.activeConfiguration.version !== model.activatedVersion
  ) {
    // A success document about another Webhook, another reviewed revision or
    // an inconsistent Active identity never renders as this activation.
    return fail("webhook");
  }
  return model;
}

/** One durable delivery row as the bounded list/detail operator model. */
export interface NotificationDeliveryModel {
  readonly deliveryId: string;
  readonly webhookId: string;
  readonly eventId: string;
  readonly eventType: NotificationEventType;
  readonly status: NotificationDeliveryStatus;
  readonly attempts: number;
  readonly nextAttemptAt: string;
  readonly createdAt: string;
  readonly updatedAt: string;
  readonly deliveredAt: string | null;
  readonly failureCategory: string | null;
  readonly responseStatus: number | null;
}

function normalizeDeliveryIdentity(
  source: Record<string, unknown>,
  field: string,
): {
  deliveryId: string;
  webhookId: string;
  eventId: string;
  eventType: NotificationEventType;
  status: NotificationDeliveryStatus;
  attempts: number;
  nextAttemptAt: string;
  createdAt: string;
  updatedAt: string;
  deliveredAt: string | null;
  failureCategory: string | null;
  responseStatus: number | null;
} {
  const responseStatus = optionalCount(source, "responseStatus");
  if (
    responseStatus !== null &&
    (responseStatus < 100 || responseStatus > 599)
  ) {
    return fail(`${field}.responseStatus`);
  }
  return {
    deliveryId: uriSafeSegment(source, "deliveryId", 64),
    webhookId: uriSafeSegment(source, "webhookId", 64),
    eventId: uriSafeSegment(source, "eventId", 128),
    eventType: enumOrFail(
      source["eventType"],
      `${field}.eventType`,
      NOTIFICATION_EVENT_TYPES,
    ),
    status: enumOrFail(
      source["status"],
      `${field}.status`,
      NOTIFICATION_DELIVERY_STATUSES,
    ),
    attempts: count(source, "attempts"),
    nextAttemptAt: text(source, "nextAttemptAt", 64),
    createdAt: text(source, "createdAt", 64),
    updatedAt: text(source, "updatedAt", 64),
    deliveredAt: optionalText(source, "deliveredAt", 64),
    failureCategory: optionalText(source, "failureCategory", 64),
    responseStatus,
  };
}

export interface NotificationDeliveriesPage {
  readonly limit: number;
  readonly status: NotificationDeliveryStatus | null;
  readonly nextCursor: string | null;
  readonly previousCursor: string | null;
  readonly items: readonly NotificationDeliveryModel[];
}

export function normalizeNotificationDeliveriesPage(
  payload: unknown,
): NotificationDeliveriesPage {
  const source = readRecord(payload, "notification_deliveries");
  const rawItems = source["items"];
  if (!Array.isArray(rawItems) || rawItems.length > 100) {
    return fail("items");
  }
  const rawStatus = source["status"];
  return {
    limit: count(source, "limit"),
    status:
      rawStatus === null || rawStatus === undefined
        ? null
        : enumOrFail(rawStatus, "status", NOTIFICATION_DELIVERY_STATUSES),
    nextCursor: optionalText(source, "next_cursor", 512),
    previousCursor: optionalText(source, "previous_cursor", 512),
    items: rawItems.map((item, index) =>
      normalizeDeliveryIdentity(
        readRecord(item, `items[${index}]`),
        `items[${index}]`,
      ),
    ),
  };
}

export interface DeliveryLeaseModel {
  readonly state: (typeof DELIVERY_LEASE_STATES)[number];
  readonly leaseSeconds: number | null;
  readonly claimedAt: string | null;
  readonly expiresAt: string | null;
}

function normalizeDeliveryLease(
  value: unknown,
  field: string,
): DeliveryLeaseModel {
  const source = readRecord(value, field);
  const state = enumOrFail(
    source["state"],
    `${field}.state`,
    DELIVERY_LEASE_STATES,
  );
  const leaseSeconds = optionalCount(source, "leaseSeconds");
  const claimedAt = optionalText(source, "claimedAt", 64);
  const expiresAt = optionalText(source, "expiresAt", 64);
  if (
    state !== "not_leased" &&
    (leaseSeconds === null || claimedAt === null || expiresAt === null)
  ) {
    // An active or expired lease is a bounded time window: a lease state
    // without its exact window is malformed evidence.
    return fail(`${field}.leaseSeconds`);
  }
  if (
    state === "not_leased" &&
    (leaseSeconds !== null || claimedAt !== null || expiresAt !== null)
  ) {
    return fail(`${field}.state`);
  }
  return { state, leaseSeconds, claimedAt, expiresAt };
}

/** One backend-advertised recovery action's bounded operator evidence. */
export interface DeliveryRecoveryEvidenceModel {
  readonly name: (typeof DELIVERY_RECOVERY_ACTIONS)[number];
  readonly durableState: string;
  readonly sideEffects: string;
  readonly retrySafe: boolean;
  readonly duplicateImplication: string;
  readonly nextAction: string;
}

function normalizeRecoveryEvidence(
  value: unknown,
  field: string,
): DeliveryRecoveryEvidenceModel {
  const source = readRecord(value, field);
  return {
    name: enumOrFail(
      source["name"],
      `${field}.name`,
      DELIVERY_RECOVERY_ACTIONS,
    ),
    durableState: text(source, "durableState", 256),
    sideEffects: text(source, "sideEffects", 384),
    retrySafe: flag(source, "retrySafe"),
    duplicateImplication: text(source, "duplicateImplication", 512),
    nextAction: text(source, "nextAction", 384),
  };
}

export interface NotificationDeliveryDetailModel {
  readonly delivery: NotificationDeliveryModel;
  readonly lease: DeliveryLeaseModel;
  readonly knownEffects: string;
  readonly retrySafe: boolean;
  readonly nextAction: string;
  readonly recovery: {
    readonly availableActions: readonly (typeof DELIVERY_RECOVERY_ACTIONS)[number][];
    readonly reason: string;
    readonly evidence: readonly DeliveryRecoveryEvidenceModel[];
  };
  readonly actions: {
    readonly requeue: NotificationActionModel | null;
    readonly resolveStale: NotificationActionModel | null;
  };
}

export function normalizeNotificationDeliveryDetail(
  payload: unknown,
): NotificationDeliveryDetailModel {
  const source = readRecord(payload, "notification_delivery_detail");
  const delivery = normalizeDeliveryIdentity(source, "delivery");
  const lease = normalizeDeliveryLease(source["lease"], "lease");
  if ((delivery.status === "delivering") !== (lease.state !== "not_leased")) {
    // A lease window only exists for an in-progress delivery: a lease state
    // inconsistent with the durable status is contradictory evidence.
    return fail("lease.state");
  }
  const recovery = readRecord(source["recovery"], "recovery");
  const rawAvailable = recovery["availableActions"];
  if (!Array.isArray(rawAvailable) || rawAvailable.length > 2) {
    return fail("recovery.availableActions");
  }
  const availableActions = rawAvailable.map((item, index) =>
    enumOrFail(
      item,
      `recovery.availableActions[${index}]`,
      DELIVERY_RECOVERY_ACTIONS,
    ),
  );
  if (
    availableActions.includes("requeue-dead-letter") &&
    delivery.status !== "dead-letter"
  ) {
    // Only a terminal dead-letter delivery is ever eligible for a requeue.
    return fail("recovery.availableActions");
  }
  if (
    availableActions.includes("resolve-stale") &&
    (delivery.status !== "delivering" || lease.state !== "expired")
  ) {
    // Only an expired in-progress lease is ever eligible for stale resolution.
    return fail("recovery.availableActions");
  }
  const rawEvidence = recovery["actions"];
  if (
    rawEvidence !== null &&
    rawEvidence !== undefined &&
    !Array.isArray(rawEvidence)
  ) {
    return fail("recovery.actions");
  }
  if (Array.isArray(rawEvidence) && rawEvidence.length > 2) {
    return fail("recovery.actions");
  }
  const evidence = (rawEvidence ?? []).map((item, index) =>
    normalizeRecoveryEvidence(item, `recovery.actions[${index}]`),
  );
  for (const item of evidence) {
    if (!availableActions.includes(item.name)) {
      // Recovery evidence without the backend's eligibility advertisement is
      // a contradictory document: no control may be rendered from it.
      return fail("recovery.actions");
    }
  }
  const actions = optionalRecord(source["actions"], "actions");
  const requeueAction =
    actions !== null &&
    actions["requeue"] !== undefined &&
    actions["requeue"] !== null
      ? normalizeNotificationAction(
          actions["requeue"],
          "actions.requeue",
          "delivery-requeue",
          delivery.deliveryId,
        )
      : null;
  const resolveStaleAction =
    actions !== null &&
    actions["resolveStale"] !== undefined &&
    actions["resolveStale"] !== null
      ? normalizeNotificationAction(
          actions["resolveStale"],
          "actions.resolveStale",
          "delivery-resolve-stale",
          delivery.deliveryId,
        )
      : null;
  if (
    requeueAction !== null &&
    !availableActions.includes("requeue-dead-letter")
  ) {
    // A recovery transport without the backend's eligibility evidence is a
    // contradictory document: no control may be rendered from it.
    return fail("actions.requeue");
  }
  if (
    resolveStaleAction !== null &&
    !availableActions.includes("resolve-stale")
  ) {
    return fail("actions.resolveStale");
  }
  return {
    delivery,
    lease,
    knownEffects: text(source, "knownEffects", 512),
    retrySafe: flag(source, "retrySafe"),
    nextAction: text(source, "nextAction", 512),
    recovery: {
      availableActions,
      reason: text(recovery, "reason", 256),
      evidence,
    },
    actions: { requeue: requeueAction, resolveStale: resolveStaleAction },
  };
}

export interface NotificationRecoveryResultModel {
  readonly action: (typeof DELIVERY_RECOVERY_ACTIONS)[number];
  readonly outcome: string;
  readonly deliveryId: string;
  readonly previousStatus: NotificationDeliveryStatus;
  readonly status: NotificationDeliveryStatus;
  readonly attempts: number;
  readonly durableState: string;
  readonly atLeastOnce: string;
  readonly nextAction: string;
}

export interface NotificationRecoveryRequestBinding {
  readonly deliveryId: string;
  readonly action: (typeof DELIVERY_RECOVERY_ACTIONS)[number];
  readonly previousStatus: NotificationDeliveryStatus;
}

export function normalizeNotificationRecoveryResult(
  payload: unknown,
  requested: NotificationRecoveryRequestBinding,
): NotificationRecoveryResultModel {
  const source = readRecord(payload, "notification_recovery_result");
  const action = text(source, "action", 64);
  if (!(DELIVERY_RECOVERY_ACTIONS as readonly string[]).includes(action)) {
    return fail("action");
  }
  const model = {
    action: action as (typeof DELIVERY_RECOVERY_ACTIONS)[number],
    outcome: text(source, "outcome", 32),
    deliveryId: uriSafeSegment(source, "deliveryId", 64),
    previousStatus: enumOrFail(
      source["previousStatus"],
      "previousStatus",
      NOTIFICATION_DELIVERY_STATUSES,
    ),
    status: enumOrFail(
      source["status"],
      "status",
      NOTIFICATION_DELIVERY_STATUSES,
    ),
    attempts: count(source, "attempts"),
    durableState: text(source, "durableState", 128),
    atLeastOnce: text(source, "atLeastOnce", 384),
    nextAction: text(source, "nextAction", 384),
  };
  if (
    model.deliveryId !== requested.deliveryId ||
    model.action !== requested.action ||
    model.previousStatus !== requested.previousStatus ||
    model.status !== "pending" ||
    (model.action === "requeue-dead-letter" &&
      model.previousStatus !== "dead-letter") ||
    (model.action === "resolve-stale" && model.previousStatus !== "delivering")
  ) {
    // A result about another delivery, another action or an impossible
    // transition never renders as the outcome of this recovery.
    return fail("deliveryId");
  }
  return model;
}
