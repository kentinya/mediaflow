/**
 * The unified Rules Add/Copy/Edit card (Slice54 RO-1/RO-2/RO-3).
 *
 * One centered card over the originating inventory serves all seven families
 * and all three modes: Create and Copy ride the inventory route search, Edit
 * rides the pre-existing `/rules/edit/$family/$objectId` address whose
 * background is the matching-family inventory. It reuses the business-free
 * shared modal shell/lifecycle (`ModalCardShell`, `useModalLayer`,
 * `useModalCardExit`); every rule-specific decision — subject-bound reads,
 * drafts, discard/in-flight/unknown-verification and publication — lives here
 * with the Rules feature.
 *
 * One explicit `保存` validates and atomically publishes the exact successor.
 * A known rejection keeps the prior Active and the correctable input; an
 * unknown outcome (lost response, unparseable success, persistence outage)
 * freezes the exact submitted candidate and baseline in a principal-scoped
 * record that survives close/reopen/refresh, blocks any unprotected re-submit
 * and is only cleared by an explicit verification decision — never an
 * automatic replay. A stale baseline keeps the input too, and only an explicit
 * "use the current value" or "keep input after re-check" may re-pair the
 * baseline.
 *
 * The card owns no inventory state: publishing hands one truthful message back
 * to the workspace, which returns to the exact list the operator came from.
 */

import { useEffect, useRef, useState, type ReactNode } from "react";
import { useBlocker } from "@tanstack/react-router";
import {
  ModalCardShell,
  useModalCardExit,
  useModalLayer,
} from "../../shared/ui/modal-card";
import {
  authorityIdentity,
  ruleCandidateFields,
  ruleFailureCopy,
  validateRuleCandidate,
  type ActiveAuthorityIdentity,
  type FieldIssue,
  type RuleFormAuthority,
  type RuleFormValue,
} from "../../entities/rules/rules-form";
import {
  editRuleObject,
  fetchRuleCopy,
  fetchRuleEdit,
  fetchRuleFormAuthority,
  saveRuleObject,
  type RulesCommandResult,
} from "../../shared/api/api-client";
import { useAuthToken } from "../../shared/api/auth-context";
import { usePrincipalIdentity } from "../operations/principal-identity-query";
import {
  RulesObjectForm,
  ruleFieldLabel,
  type FormValues,
} from "./RulesObjectForm";
import { RulesObjectTestPanel } from "./RulesObjectTestPanel";
import {
  RULE_DRAWER_LABELS,
  clearRuleDraft,
  readRuleDraft,
  writeRuleDraft,
} from "./rules-workspace-labels";
import {
  rulesCardDraftKey,
  sectionNavigationInProgress,
  type RulesCardSession,
} from "./rules-card-session";
import {
  readRulesUnknownSave,
  writeRulesUnknownSave,
  type RulesUnknownSaveRecord,
} from "./rules-unknown-save";

export interface RulesCardProps {
  readonly session: RulesCardSession;
  /** Inventory RBAC: a read-only principal keeps the card but never saves. */
  readonly canManage: boolean;
  /** The owner's close: it performs the return navigation to the inventory. */
  readonly onClose: () => void;
  /** A durable publication with a truthful message for the inventory. */
  readonly onPublished: (message: string) => void;
  /** A non-publication notice (verification decisions) for the inventory. */
  readonly onNotice: (message: string) => void;
}

export type SaveFailureState =
  | {
      kind: "known-failure";
      code: string;
      nextAction: string | null;
      durable: string | null;
    }
  | { kind: "unknown"; code: string };

export type SaveState =
  | { kind: "idle" }
  | { kind: "saving" }
  | { kind: "invalid"; issues: readonly FieldIssue[] }
  | { kind: "known-failure"; code: string; nextAction: string | null };

/**
 * Split a failed Save into the two operator-visible outcomes the contract
 * requires. A known rejection keeps the prior Active and the correctable
 * candidate; a transport or unconfirmable result is never presented as a plain
 * failure, because the publication may or may not have happened — only an
 * explicit Active verification resolves it, and no automatic replay exists.
 */
export function classifySaveFailure(
  outcome: RulesCommandResult & { ok: false },
): SaveFailureState {
  if (
    outcome.code === "transport_unavailable" ||
    outcome.code === "malformed_response" ||
    outcome.code === "rules_persistence_failed" ||
    outcome.status === 503
  )
    return { kind: "unknown", code: outcome.code };
  return {
    kind: "known-failure",
    code: outcome.code,
    nextAction: outcome.details?.nextAction ?? null,
    durable: outcome.details?.durableState ?? null,
  };
}

/** Codes that state the Active moved under the submitted baseline (stale). */
function isStaleAuthorityCode(code: string): boolean {
  return (
    code === "configuration_version_conflict" ||
    code === "configuration_conflict"
  );
}

function modeLabel(mode: RulesCardSession["mode"]): string {
  return mode === "create" ? "添加" : mode === "copy" ? "复制" : "编辑";
}

/** Order-insensitive structural equality for two candidate documents. */
function stableJson(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(stableJson).join(",")}]`;
  if (value !== null && typeof value === "object") {
    const entries = Object.entries(value as Record<string, unknown>)
      .filter(([, item]) => item !== undefined)
      .sort(([a], [b]) => (a < b ? -1 : a > b ? 1 : 0))
      .map(([key, item]) => `${JSON.stringify(key)}:${stableJson(item)}`);
    return `{${entries.join(",")}}`;
  }
  return JSON.stringify(value) ?? "null";
}

function sameCandidate(
  a: Readonly<Record<string, unknown>>,
  b: Readonly<Record<string, unknown>>,
): boolean {
  return stableJson(a) === stableJson(b);
}

/** The frozen facts of one submitted command, independent of today's draft. */
interface FrozenSubmit {
  readonly objectId: string;
  readonly candidate: Readonly<Record<string, RuleFormValue>>;
  readonly baseline: ActiveAuthorityIdentity;
  readonly submittedAt: number;
}

interface VerifyPanelState {
  /** Why the panel exists: a lost response, or a stale baseline refusal. */
  readonly reason: "unknown" | "stale";
  readonly verdict:
    | "unverified"
    | "reading"
    | "matched"
    | "modified"
    | "absent"
    | "unreadable";
  readonly readCode: string | null;
  /** The freshly read current value + the exact baseline it was read with. */
  readonly current: {
    readonly values: FormValues;
    readonly baseline: ActiveAuthorityIdentity;
  } | null;
  /** Current Active identity observed by the verification read. */
  readonly active: ActiveAuthorityIdentity | null;
  readonly failureCode: string | null;
  readonly busy: "adopt" | "recheck" | null;
}

const EMPTY_VERIFY: VerifyPanelState = {
  reason: "unknown",
  verdict: "unverified",
  readCode: null,
  current: null,
  active: null,
  failureCode: null,
  busy: null,
};

function formatSubmitTime(at: number): string {
  try {
    return new Date(at).toLocaleString("zh-CN", { hour12: false });
  } catch {
    return new Date(at).toISOString();
  }
}

export function RulesObjectCard({
  session,
  canManage,
  onClose,
  onPublished,
  onNotice,
}: RulesCardProps) {
  const token = useAuthToken();
  const principal = usePrincipalIdentity();
  const principalId = principal.resolved ? principal.principalId : null;
  const label = RULE_DRAWER_LABELS[session.family];
  const draftKey = rulesCardDraftKey(session);
  const subjectId =
    session.mode === "create"
      ? null
      : session.mode === "copy"
        ? session.sourceId
        : session.objectId;

  const [retry, setRetry] = useState(0);
  const [authority, setAuthority] = useState<RuleFormAuthority | null>(null);
  const [authorityError, setAuthorityError] = useState<string | null>(null);
  const [projection, setProjection] = useState<
    | {
        readonly ok: true;
        readonly baseline: ActiveAuthorityIdentity;
        readonly name: string | null;
      }
    | { readonly ok: false; readonly code: string; readonly nextAction: string | null }
    | null
  >(null);
  const [values, setValues] = useState<FormValues | null>(null);
  const [dirty, setDirty] = useState(false);
  const [state, setState] = useState<SaveState>({ kind: "idle" });
  const [issues, setIssues] = useState<ReadonlyMap<string, string>>(new Map());
  const [panel, setPanel] = useState<"settings" | "test">("settings");
  const [verify, setVerify] = useState<VerifyPanelState | null>(null);
  const [frozenState, setFrozenState] = useState<FrozenSubmit | null>(null);
  const [discardArmed, setDiscardArmed] = useState(false);
  const [saving, setSaving] = useState(false);
  const savingRef = useRef(false);
  const dirtyRef = useRef(dirty);
  const principalRef = useRef<string | null>(null);
  useEffect(() => {
    savingRef.current = saving;
    dirtyRef.current = dirty;
    principalRef.current = principalId;
  });
  // The retained unknown record is read from its external session store on
  // every render (never into state), so close/reopen/refresh always shows the
  // durable record itself rather than a stale copy of it.
  const storedRecord: RulesUnknownSaveRecord | null =
    principal.resolved
      ? readRulesUnknownSave(principal.principalId, session.family, {
          mode: session.mode,
          subjectId,
        })
      : null;
  const frozen: FrozenSubmit | null =
    frozenState ??
    (storedRecord !== null
      ? {
          objectId: storedRecord.objectId,
          candidate: storedRecord.candidate,
          baseline: storedRecord.baseline,
          submittedAt: storedRecord.submittedAt,
        }
      : null);
  const mountedRef = useRef(true);
  useEffect(
    () => () => {
      mountedRef.current = false;
    },
    [],
  );

  // --- subject-bound reads: one card instance, one subject; every late
  // response is fenced by this mount and can never populate another object.
  useEffect(() => {
    let active = true;
    void fetchRuleFormAuthority(token).then((outcome) => {
      if (!active || !mountedRef.current) return;
      if (outcome.ok) {
        setAuthority(outcome.model);
        if (session.mode === "create") {
          // Prefill defaults and baseline come from this one read, so the
          // candidate is always paired with the Active it was seeded from.
          const defaults = outcome.model.families[session.family];
          const seeded: FormValues = {};
          for (const field of defaults.fields) {
            if (defaults.values[field] !== undefined)
              seeded[field] = defaults.values[field];
          }
          setProjection({
            ok: true,
            baseline: authorityIdentity(outcome.model.active),
            name: null,
          });
          setValues((current) => {
            if (current !== null && Object.keys(current).length > 0)
              return current;
            return seeded;
          });
        }
      } else {
        setAuthorityError(ruleFailureCopy(outcome.code));
      }
    });
    if (session.mode === "edit") {
      void fetchRuleEdit(token, session.family, session.objectId).then(
        (outcome) => {
          if (!active || !mountedRef.current) return;
          if (outcome.ok) {
            const value = { ...(outcome.model.value as FormValues) };
            setProjection({
              ok: true,
              // The prefill and its baseline are one read: Save composes
              // against exactly what the operator is looking at.
              baseline: authorityIdentity(outcome.model.active),
              name:
                typeof value.name === "string" ? (value.name as string) : null,
            });
            setValues((current) =>
              current !== null && dirtyRef.current ? current : value,
            );
          } else {
            setProjection({
              ok: false,
              code: outcome.code,
              nextAction: outcome.details?.nextAction ?? null,
            });
          }
        },
      );
    }
    if (session.mode === "copy") {
      void fetchRuleCopy(token, session.family, session.sourceId).then(
        (outcome) => {
          if (!active || !mountedRef.current) return;
          if (outcome.ok) {
            const seeded = { ...(outcome.model.value as FormValues) };
            setProjection({
              ok: true,
              // The copy candidate and the Active it was computed from are
              // one read: pairing them keeps the new-ID candidate savable
              // without stitching across versions.
              baseline: authorityIdentity(outcome.model.active),
              name:
                typeof seeded.name === "string"
                  ? (seeded.name as string)
                  : null,
            });
            setValues((current) =>
              current !== null && Object.keys(current).length > 0
                ? current
                : seeded,
            );
          } else {
            setProjection({
              ok: false,
              code: outcome.code,
              nextAction: outcome.details?.nextAction ?? null,
            });
          }
        },
      );
    }
    return () => {
      active = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [retry, token]);

  // --- principal-scoped draft restore: a principal that has not resolved can
  // neither be shown another identity's draft nor write one.
  const draftTriedRef = useRef(false);
  useEffect(() => {
    if (draftTriedRef.current) return;
    if (principal.resolved === false) return;
    draftTriedRef.current = true;
    const principalValue = principal.resolved ? principal.principalId : null;
    const stored = readRuleDraft(principalValue, session.family, draftKey);
    if (stored !== undefined && !dirtyRef.current) {
      setValues((current) => {
        if (dirtyRef.current) return current;
        return { ...stored } as FormValues;
      });
      setDirty(true);
    } else if (stored === undefined && dirtyRef.current) {
      // Input typed before the identity resolved is persisted as soon as it
      // can be scoped, so a refresh never silently drops it.
      setValues((current) => {
        if (current !== null)
          writeRuleDraft(
            principalValue,
            session.family,
            draftKey,
            current as Record<string, RuleFormValue>,
          );
        return current;
      });
    }
  }, [principal, session.family, draftKey]);

  // A retained record for this subject keeps the verification panel open even
  // before any local action: `verifyState` is the local decision state or the
  // durable record itself.
  const verifyState: VerifyPanelState | null =
    verify ??
    (storedRecord !== null && principal.resolved
      ? { ...EMPTY_VERIFY, reason: "unknown" }
      : null);

  // Leaving with unsaved input warns the browser; the in-app exits below are
  // the coordinated Continue/Discard decision.
  useEffect(() => {
    if (!dirty) return;
    const handler = (event: BeforeUnloadEvent) => {
      event.preventDefault();
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);

  const savingLocked = saving || state.kind === "saving";

  // --- route/browser-back protection: a Back gesture receives exactly the
  // blocked-navigation decision the close button makes.
  const bypassBlockerRef = useRef(false);
  const blocker = useBlocker({
    shouldBlockFn: () =>
      !bypassBlockerRef.current &&
      // The workspace's own section-tab switch is not a close gesture: its
      // draft stays in the session store. Every real close — button, cancel,
      // backdrop, Escape and browser Back — still reaches the decision below.
      !sectionNavigationInProgress() &&
      (savingRef.current || dirtyRef.current),
    withResolver: true,
  });
  const blockerRef = useRef(blocker);
  useEffect(() => {
    blockerRef.current = blocker;
  });
  const exit = useModalCardExit();

  /** Release the route blocker before this card performs its own navigate. */
  const releaseBlocker = () => {
    bypassBlockerRef.current = true;
    const current = blockerRef.current;
    if (current.status === "blocked") current.reset();
  };

  const clearDraft = () => {
    clearRuleDraft(principalRef.current, session.family, draftKey);
  };

  const commitClose = () => {
    if (savingRef.current) return;
    const currentBlocker = blockerRef.current;
    if (dirtyRef.current) {
      // Discard is one explicit decision: the correctable input is forgotten
      // exactly once, here — a repeated close gesture never discards.
      clearDraft();
      setDirty(false);
    }
    setDiscardArmed(false);
    if (currentBlocker.status === "blocked") {
      // The blocked Back resumes as the close: the operator's own navigation
      // destination is honoured rather than replaced.
      bypassBlockerRef.current = true;
      const proceed = currentBlocker.proceed;
      exit.beginClose(() => proceed());
      return;
    }
    releaseBlocker();
    exit.beginClose(onClose);
  };

  const attemptClose = () => {
    if (savingRef.current || exit.closing) return;
    if (discardArmed || blockerRef.current.status === "blocked") {
      // A repeated close gesture while the choice is open keeps the input and
      // returns to the card; two closes are never an implicit discard.
      setDiscardArmed(false);
      if (blockerRef.current.status === "blocked") blockerRef.current.reset();
      return;
    }
    if (dirtyRef.current) {
      setDiscardArmed(true);
      return;
    }
    commitClose();
  };

  const card = useModalLayer({
    onEscape: attemptClose,
    escapeDisabled: () => savingRef.current,
    fallbackFocusId: "rules-family-title",
  });

  // Keyboard entry lands inside the card: the close control is the stable
  // first target while the subject read is still in flight.
  useEffect(() => {
    card.layerRef.current
      ?.querySelector<HTMLElement>(".mf-modal-close")
      ?.focus({ preventScroll: true });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const discardPromptOpen =
    !savingLocked && (discardArmed || blocker.status === "blocked");

  // The safe close decision pins focus on "continue editing" while open.
  useEffect(() => {
    if (!discardPromptOpen) return;
    const timer = window.requestAnimationFrame(() => {
      document
        .getElementById("mf-rules-discard-continue")
        ?.focus({ preventScroll: true });
    });
    return () => window.cancelAnimationFrame(timer);
  }, [discardPromptOpen]);

  const change = (field: string, value: RuleFormValue) => {
    if (values === null) return;
    const next = { ...values, [field]: value };
    setValues(next);
    setDirty(true);
    if (principalRef.current !== null) {
      writeRuleDraft(
        principalRef.current,
        session.family,
        draftKey,
        next as Record<string, RuleFormValue>,
      );
    }
    setIssues((current) => {
      // A nested change rewrites the whole `rules` array, so every issue that
      // belonged to one of those internal rules describes replaced input.
      const owned = (key: string) =>
        key === field || (field === "rules" && /^rules\[\d+\]\./.test(key));
      if (!Array.from(current.keys()).some(owned)) return current;
      const merged = new Map(current);
      for (const key of Array.from(merged.keys())) {
        if (owned(key)) merged.delete(key);
      }
      return merged;
    });
    setState((current) =>
      current.kind === "invalid" ? { kind: "idle" } : current,
    );
  };

  // ------------------------------------------------------------------
  // Verification of a lost or stale publication (never an automatic replay)
  // ------------------------------------------------------------------
  const verifyObjectId =
    session.mode === "edit" ? session.objectId : (frozen?.objectId ?? null);

  const runVerification = async (): Promise<void> => {
    const base = verifyState ?? EMPTY_VERIFY;
    if (verifyObjectId === null || token === null) {
      setVerify({
        ...base,
        verdict: "unreadable",
        readCode: "invalid_request",
        busy: null,
      });
      return;
    }
    const [activeOutcome, objectOutcome] = await Promise.all([
      fetchRuleFormAuthority(token),
      fetchRuleEdit(token, session.family, verifyObjectId),
    ]);
    if (!mountedRef.current) return;
    if (!activeOutcome.ok) {
      setVerify({
        ...base,
        verdict: "unreadable",
        readCode: activeOutcome.code,
        busy: null,
      });
      return;
    }
    const active = authorityIdentity(activeOutcome.model.active);
    if (!objectOutcome.ok) {
      const missing =
        objectOutcome.code === "not_found" ||
        objectOutcome.code === "rules_object_not_found" ||
        objectOutcome.status === 404;
      setVerify({
        ...base,
        verdict: missing ? "absent" : "unreadable",
        readCode: missing ? null : objectOutcome.code,
        active,
        current: null,
        busy: null,
      });
      return;
    }
    const current: FormValues = { ...(objectOutcome.model.value as FormValues) };
    const baseline = authorityIdentity(objectOutcome.model.active);
    const frozenCandidate = frozen?.candidate ?? null;
    const matched =
      frozenCandidate !== null &&
      sameCandidate(frozenCandidate, current as Record<string, unknown>);
    setVerify({
      ...base,
      verdict: matched ? "matched" : "modified",
      current: { values: current, baseline },
      active,
      readCode: null,
      busy: null,
    });
  };

  const beginVerify = async () => {
    if (verifyState === null) return;
    setVerify({ ...verifyState, verdict: "reading", busy: null });
    await runVerification();
  };

  const clearUnknownRecord = () => {
    writeRulesUnknownSave(
      principalRef.current,
      session.family,
      { mode: session.mode, subjectId },
      null,
    );
  };

  /**
   * "Adopt the current value": the freshly read value and the baseline it was
   * read with are applied together as one explicit decision, and the retained
   * record is cleared. Nothing is re-sent and no background refresh ever
   * swaps the baseline under the operator's input.
   */
  const adoptCurrentValue = () => {
    if (verifyState === null || verifyState.current === null) return;
    const adopted = verifyState.current;
    if (verifyState.reason === "unknown") clearUnknownRecord();
    clearDraft();
    setValues(adopted.values);
    setProjection({ ok: true, baseline: adopted.baseline, name: null });
    setDirty(false);
    setFrozenState(null);
    setVerify(null);
    onNotice(
      session.mode === "edit"
        ? "已采用当前 Active 中的该对象值与配套基线;未保存的候选输入已按你的选择放弃,本次没有发布任何修改。"
        : "已采用当前 Active 中的该对象值与配套基线;本卡片仍是新建/复制入口,该 ID 已存在于清单,请在清单中编辑它。",
    );
  };

  /**
   * "Keep my input after a re-check": the record is cleared only after this
   * explicit review, and the Save baseline is paired at that moment with a
   * fresh Active read — never through a background refresh.
   */
  const recheckKeepInput = async () => {
    if (verifyState === null) return;
    const reason = verifyState.reason;
    setVerify({ ...verifyState, busy: "recheck" });
    const activeOutcome = await fetchRuleFormAuthority(token);
    if (!mountedRef.current) return;
    if (!activeOutcome.ok) {
      setVerify({
        ...(verifyState ?? EMPTY_VERIFY),
        verdict: "unreadable",
        readCode: activeOutcome.code,
        busy: null,
      });
      return;
    }
    const fresh = authorityIdentity(activeOutcome.model.active);
    if (reason === "unknown") clearUnknownRecord();
    setProjection({ ok: true, baseline: fresh, name: null });
    setFrozenState(null);
    setVerify(null);
    onNotice(
      "已按你的复核保留输入,保存基线已与刚刚读取的 Active 配对;输入保持你在表单中的内容,可再次显式保存。",
    );
  };

  // ------------------------------------------------------------------
  // Save
  // ------------------------------------------------------------------
  const ready =
    authority !== null && values !== null && projection !== null && projection.ok;
  const projectionFailed = projection !== null && !projection.ok;

  const saveDisabled =
    !ready ||
    savingLocked ||
    verifyState !== null ||
    principal.resolved === false ||
    !canManage ||
    exit.closing;

  const save = async () => {
    if (values === null || authority === null) return;
    if (saveDisabled) return;
    const candidate = ruleCandidateFields(session.family, values);
    const problems = validateRuleCandidate(
      session.family,
      candidate,
      authority,
    );
    if (problems.length > 0) {
      setIssues(new Map(problems.map((item) => [item.field, item.message])));
      setState({ kind: "invalid", issues: problems });
      return;
    }
    setIssues(new Map());
    const observed = projection !== null && projection.ok ? projection.baseline : null;
    if (observed === null) {
      setState({
        kind: "known-failure",
        code: "configuration_unavailable",
        nextAction: "重新打开表单以读取当前 Active 后再保存",
      });
      return;
    }
    // Freeze the exact command identity before the request leaves: mode,
    // subject, candidate and baseline are what a lost response must retain.
    const submission: FrozenSubmit = {
      objectId: String(candidate.id ?? subjectId ?? ""),
      candidate,
      baseline: observed,
      submittedAt: Date.now(),
    };
    setState({ kind: "saving" });
    setSaving(true);
    savingRef.current = true;
    const outcome: RulesCommandResult =
      session.mode === "edit"
        ? await editRuleObject(
            token,
            session.family,
            session.objectId,
            candidate,
            observed,
          )
        : await saveRuleObject(token, session.family, candidate, observed);
    savingRef.current = false;
    setSaving(false);
    if (!mountedRef.current) return;
    if (outcome.ok) {
      clearDraft();
      clearUnknownRecord();
      setFrozenState(null);
      setVerify(null);
      releaseBlocker();
      exit.beginClose(() =>
        onPublished(`${label}已发布为新的 Active,清单与就绪状态已刷新。`),
      );
      return;
    }
    const failure = classifySaveFailure(outcome);
    if (failure.kind === "unknown") {
      // Retain the frozen command principal-scoped: closing, reopening,
      // refreshing or editing the form never re-sends or loses it.
      const record: RulesUnknownSaveRecord = {
        mode: session.mode,
        family: session.family,
        subjectId,
        objectId: submission.objectId,
        candidate: submission.candidate,
        baseline: submission.baseline,
        submittedAt: submission.submittedAt,
      };
      setFrozenState(submission);
      writeRulesUnknownSave(
        principalRef.current,
        session.family,
        { mode: session.mode, subjectId },
        record,
      );
      setState({ kind: "idle" });
      setVerify({
        ...EMPTY_VERIFY,
        reason: "unknown",
        failureCode: failure.code,
      });
      return;
    }
    if (isStaleAuthorityCode(failure.code)) {
      setFrozenState(submission);
      setState({ kind: "idle" });
      setVerify({
        ...EMPTY_VERIFY,
        reason: "stale",
        failureCode: failure.code,
      });
      return;
    }
    setState({
      kind: "known-failure",
      code: failure.code,
      nextAction: failure.nextAction,
    });
  };

  // ------------------------------------------------------------------
  // Presentation
  // ------------------------------------------------------------------
  const title =
    session.mode === "edit"
      ? `编辑${label} · ${
          projection !== null && projection.ok && projection.name
            ? projection.name
            : session.objectId
        }`
      : `${modeLabel(session.mode)}${label}`;

  const description =
    session.mode === "edit"
      ? `ID ${session.objectId} 不可更改;保存会用一次操作校验完整后继配置并原子激活,失败时旧 Active 与你的输入都保持不变。`
      : session.mode === "copy"
        ? `复制自 ${session.sourceId}${
            projection !== null && projection.ok && projection.name
              ? `(${String(projection.name)})`
              : ""
          };保存时以新的稳定 ID 发布为新的 Active。`
        : "保存会用一次操作校验完整后继配置并原子激活;失败时旧 Active 保持不变,表单输入可以修正后重试。";

  const footer = (
    <>
      <button
        type="button"
        className="mf-button mf-button-secondary"
        onClick={attemptClose}
        disabled={savingLocked || exit.closing}
      >
        取消
      </button>
      <button
        type="button"
        className="mf-button mf-button-primary"
        onClick={() => void save()}
        disabled={saveDisabled}
      >
        {savingLocked ? "保存中..." : "保存"}
      </button>
    </>
  );

  const verifyPanel = (verifyState: VerifyPanelState): ReactNode => {
    const subjectName =
      frozen?.objectId ??
      (session.mode === "edit" ? session.objectId : verifyObjectId ?? "");
    const facts = (
      <>
        <p>
          {verifyState.reason === "unknown"
            ? "无法确认上次保存是否生效(结果未知)。系统不会自动重发;核对完成之前,普通保存已被阻止。"
            : "当前 Active 与保存时的基线不一致(stale),本次没有发布任何内容,输入已保留。"}
        </p>
        <p className="mf-rules-verify-facts">
          原请求:{modeLabel(session.mode)} {subjectName}
          {frozen !== null
            ? `,提交于 ${formatSubmitTime(frozen.submittedAt)},提交时 Active 序号 ${frozen.baseline.expectedVersion}`
            : ""}
          。
        </p>
        {verifyState.failureCode ? (
          <p className="mf-rules-verify-facts">
            结果分类:{ruleFailureCopy(verifyState.failureCode)}
          </p>
        ) : null}
      </>
    );

    let body: ReactNode;
    if (verifyState.verdict === "reading") {
      body = <p role="status">正在读取当前 Active 与该对象...</p>;
    } else if (verifyState.verdict === "unverified") {
      body = (
        <div className="mf-actions">
          <button
            type="button"
            className="mf-button mf-button-primary"
            onClick={() => void beginVerify()}
          >
            读取当前 Active 核对
          </button>
        </div>
      );
    } else if (verifyState.verdict === "unreadable") {
      body = (
        <>
          <p role="alert">
            读回当前状态失败:
            {ruleFailureCopy(verifyState.readCode ?? "transport_unavailable")}
            未知记录原样保留,没有重发任何命令。
          </p>
          <div className="mf-actions">
            <button
              type="button"
              className="mf-button mf-button-primary"
              onClick={() => void beginVerify()}
            >
              重新核对
            </button>
          </div>
        </>
      );
    } else if (verifyState.verdict === "absent") {
      body = (
        <>
          <p>
            当前 Active 序号 {verifyState.active?.expectedVersion ?? "-"};该对象
            <strong>已不在当前 Active 中</strong>。这既可能是原保存没有生效,也可能是
            它之后被其他管理员移除;读取结果不能单独证明原请求的成功或失败。
          </p>
          <div className="mf-actions">
            <button type="button" className="mf-button" disabled>
              采用当前值(当前没有可采用的值)
            </button>
            <button
              type="button"
              className="mf-button mf-button-secondary"
              onClick={() => void recheckKeepInput()}
              disabled={verifyState.busy !== null}
            >
              {verifyState.busy === "recheck" ? "正在复核..." : "保留输入,重新复核"}
            </button>
          </div>
        </>
      );
    } else {
      const matched = verifyState.verdict === "matched";
      body = (
        <>
          <p>
            当前 Active 序号 {verifyState.active?.expectedVersion ?? "-"};该对象
            <strong>{matched ? "与原提交内容一致" : "与原提交内容不同"}</strong>
            {matched
              ? ";这与原保存生效相符,但当前同值本身不能单独证明原请求已成功。"
              : ";当前值来自另一次发布,它不是原请求成功或失败的证明。"}
          </p>
          {verifyState.current ? (
            <details className="mf-rules-verify-current">
              <summary>查看当前值</summary>
              <dl>
                <dt>ID</dt>
                <dd>{String(verifyState.current.values.id ?? "-")}</dd>
                <dt>名称</dt>
                <dd>{String(verifyState.current.values.name ?? "-")}</dd>
              </dl>
              <pre>
                {JSON.stringify(verifyState.current.values, null, 2)}
              </pre>
            </details>
          ) : null}
          <div className="mf-actions">
            <button
              type="button"
              className="mf-button mf-button-primary"
              onClick={adoptCurrentValue}
              disabled={verifyState.busy !== null}
            >
              {verifyState.busy === "adopt" ? "正在采用..." : "采用当前值"}
            </button>
            <button
              type="button"
              className="mf-button mf-button-secondary"
              onClick={() => void recheckKeepInput()}
              disabled={verifyState.busy !== null}
            >
              {verifyState.busy === "recheck" ? "正在复核..." : "保留输入,重新复核"}
            </button>
          </div>
        </>
      );
    }

    return (
      <div
        className={
          verifyState.reason === "unknown"
            ? "mf-rules-save-unknown"
            : "mf-rules-save-failure"
        }
        role={verifyState.reason === "unknown" ? "status" : "alert"}
        data-testid="rules-verify-panel"
      >
        <h3>
          {verifyState.reason === "unknown"
            ? "上次保存结果未知,需要核对"
            : "保存被拒绝:当前 Active 已变化"}
        </h3>
        {facts}
        {body}
      </div>
    );
  };

  let content: ReactNode;
  if (projectionFailed || (authorityError !== null && !ready)) {
    const message =
      authorityError !== null
        ? `表单字段权限读取失败:${authorityError}`
        : projection !== null && !projection.ok
          ? `无法读取该对象:${ruleFailureCopy(projection.code)}${
              projection.nextAction ? ` 下一步:${projection.nextAction}` : ""
            }`
          : "暂时无法读取该表单。";
    content = (
      <div className="mf-modal-card-status mf-modal-card-status-error">
        <p role="alert">{message}</p>
        <p>本次没有发布任何内容;已输入的内容会保留在会话草稿中。</p>
        <div className="mf-actions">
          <button
            type="button"
            className="mf-button mf-button-primary"
            onClick={() => setRetry((value) => value + 1)}
          >
            重新读取
          </button>
          <button type="button" className="mf-button" onClick={attemptClose}>
            返回清单
          </button>
        </div>
      </div>
    );
  } else if (!ready) {
    content = (
      <div className="mf-modal-card-status" role="status">
        <p>
          {session.mode === "copy"
            ? "正在读取复制候选与表单字段权限..."
            : session.mode === "edit"
              ? "正在读取该对象的 Active 投影与表单字段权限..."
              : "正在读取表单字段权限..."}
        </p>
      </div>
    );
  } else if (values !== null && authority !== null) {
    content = (
      <div className="mf-rules-card-scroll">
        {discardPromptOpen ? (
          <div
            className="mf-rules-discard"
            role="alertdialog"
            aria-labelledby="mf-rules-discard-question"
            aria-describedby="mf-rules-discard-detail"
          >
            <p id="mf-rules-discard-question">
              表单中有未保存的输入;关闭会放弃这些修改。
            </p>
            <p id="mf-rules-discard-detail" className="mf-rules-discard-hint">
              放弃后本次输入不会继续保留;继续编辑则一切保持不变。
            </p>
            <div className="mf-actions">
              <button
                type="button"
                className="mf-button mf-button-secondary"
                id="mf-rules-discard-continue"
                onClick={() => setDiscardArmed(false)}
              >
                继续编辑
              </button>
              <button type="button" className="mf-button" onClick={commitClose}>
                放弃并关闭
              </button>
            </div>
          </div>
        ) : null}
        {verifyState !== null ? verifyPanel(verifyState) : null}
        {state.kind === "invalid" ? (
          <div className="mf-rules-save-invalid" role="alert">
            <p>
              保存未生效:有 {state.issues.length} 处输入未通过校验,Active
              没有发生任何变化。请修正下面列出的字段后重新保存。
            </p>
            <ul>
              {state.issues.map((item) => (
                <li key={item.field}>
                  <span>{ruleFieldLabel(item.field)}</span>:{item.message}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
        {state.kind === "known-failure" ? (
          <div className="mf-rules-save-failure" role="alert">
            <p>
              保存未生效:{ruleFailureCopy(state.code)}
              {state.nextAction ? ` 下一步:${state.nextAction}` : ""}
            </p>
            <p className="mf-rules-durable">
              旧 Active 保持不变;当前输入已保留,可直接修正后重试。
            </p>
          </div>
        ) : null}
        {!canManage ? (
          <p className="mf-rules-card-principal" role="status">
            当前身份只能查看;保存与发布需要配置管理与激活权限。
          </p>
        ) : principal.resolved === false ? (
          <p className="mf-rules-card-principal" role="status">
            {principal.reason === "loading"
              ? "正在确认当前身份,保存暂不可用..."
              : "当前身份无法确认,保存已暂停以避免重复发布;请刷新页面重试。"}
          </p>
        ) : null}
        <div className="mf-rules-card-tabs" role="tablist" aria-label="卡片区域">
          <button
            type="button"
            role="tab"
            id="mf-rules-tab-settings"
            aria-selected={panel === "settings"}
            aria-controls="mf-rules-panel-settings"
            onClick={() => setPanel("settings")}
          >
            设置
          </button>
          <button
            type="button"
            role="tab"
            id="mf-rules-tab-test"
            aria-selected={panel === "test"}
            aria-controls="mf-rules-panel-test"
            onClick={() => setPanel("test")}
          >
            单项测试
          </button>
        </div>
        <div
          role="tabpanel"
          id="mf-rules-panel-settings"
          aria-labelledby="mf-rules-tab-settings"
          hidden={panel !== "settings"}
        >
          <RulesObjectForm
            family={session.family}
            authority={authority}
            values={values}
            issues={issues}
            editing={session.mode === "edit"}
            disabled={savingLocked}
            onChange={change}
          />
        </div>
        {/* Both areas stay mounted so switching preserves fields, samples and
            evidence; only visibility changes. */}
        <div
          role="tabpanel"
          id="mf-rules-panel-test"
          aria-labelledby="mf-rules-tab-test"
          hidden={panel !== "test"}
        >
          <RulesObjectTestPanel
            token={token ?? ""}
            family={session.family}
            objectId={session.mode === "edit" ? session.objectId : null}
            authority={authority}
            values={values}
          />
          <p className="mf-rules-test-scope-note">
            单项测试只检查当前未保存的候选与必要样本;完整流程检查只在「概览」的完整流程
            检查 中进行,它读取已发布的 Active,未保存的候选不会被代入。
          </p>
        </div>
      </div>
    );
  }

  return (
    <ModalCardShell
      layerRef={card.layerRef}
      closing={exit.closing}
      busy={savingLocked}
      title={title}
      titleId="mf-rules-card-title"
      accessibleName={title}
      description={description}
      closeLabel="关闭规则表单"
      closeDisabled={savingLocked || exit.closing}
      onRequestClose={attemptClose}
      size="form"
      cardClassName={`mf-rules-card${
        session.family === "recognitionRules" ||
        session.family === "classificationPolicies"
          ? " mf-rules-card-complex"
          : ""
      }`}
      bodyClassName="mf-rules-card-body"
      footer={footer}
    >
      {content ?? (
        <div className="mf-modal-card-status" role="status">
          <p>正在准备表单...</p>
        </div>
      )}
    </ModalCardShell>
  );
}