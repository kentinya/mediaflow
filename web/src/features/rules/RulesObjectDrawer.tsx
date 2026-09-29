/**
 * The rules Add/Copy drawer (Slice 41, Task 41.2).
 *
 * One explicit `保存` publishes the typed candidate as the new Active successor:
 * the backend composes it against the exact Active the drawer captured on open,
 * validates the whole document, runs the applicable read-only checks and
 * activates atomically. The operator never sees a separate Draft/Validate/
 * Activate ceremony or a raw revision token.
 *
 * A known failure keeps the previous Active and the correctable input; an
 * unknown outcome (transport failure, unparseable success, persistence outage)
 * only ever offers Active verification — never an automatic replay.
 */

import { useEffect, useRef, useState } from "react";
import {
  authorityIdentity,
  ruleCandidateFields,
  ruleFailureCopy,
  validateRuleCandidate,
  type RuleFormAuthority,
  type RuleFormFamily,
  type RuleFormValue,
} from "../../entities/rules/rules-form";
import {
  fetchRuleActiveAuthority,
  fetchRuleFormAuthority,
  saveRuleObject,
  type ActiveAuthorityIdentity,
  type RulesCommandResult,
} from "../../shared/api/api-client";
import { useAuthToken } from "../../shared/api/auth-context";
import { RulesObjectForm, type FormValues } from "./RulesObjectForm";
import { RulesPreviewPanel } from "./RulesPreviewPanel";
import {
  clearRuleDraft,
  readRuleDraft,
  RULE_DRAWER_LABELS,
  writeRuleDraft,
} from "./rules-workspace-labels";

export interface RulesDrawerSession {
  readonly family: RuleFormFamily;
  readonly mode: "create" | "copy";
  readonly sourceId?: string;
  /** Open intent only: prefill and identity are fetched over the read APIs. */
  readonly candidate?: Readonly<Record<string, RuleFormValue>>;
}

interface Props {
  readonly session: RulesDrawerSession;
  readonly onClose: () => void;
  readonly onPublished: (message: string) => void;
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
  | { kind: "verifying" }
  | { kind: "verified"; summary: string }
  | SaveFailureState;

export function RulesObjectDrawer({ session, onClose, onPublished }: Props) {
  const token = useAuthToken();
  const headingRef = useRef<HTMLHeadingElement>(null);
  const [authority, setAuthority] = useState<RuleFormAuthority | null>(null);
  const [authorityError, setAuthorityError] = useState<string | null>(null);
  // A previous attempt may have left a correctable candidate for this exact
  // intent; restoring it is what makes a failed Save recoverable rather than a
  // reason to retype. An explicit discard clears it.
  const draftKey = session.mode === "copy" ? (session.sourceId ?? null) : null;
  const [values, setValues] = useState<FormValues>(() => {
    const stored = readRuleDraft(session.family, draftKey);
    if (stored !== undefined) return stored;
    return { ...(session.candidate ?? {}) } as FormValues;
  });
  const [dirty, setDirty] = useState(session.candidate !== undefined);
  const [discardArmed, setDiscardArmed] = useState(false);
  const [state, setState] = useState<SaveState>({ kind: "idle" });
  const [localIssues, setLocalIssues] = useState<ReadonlyMap<string, string>>(
    new Map(),
  );
  // The exact Active observed when this form opened. The Save composes against
  // it, so a concurrent publication fails as a stale-authority conflict instead
  // of silently rewriting over whatever became Active in the meantime.
  const [observed, setObserved] = useState<ActiveAuthorityIdentity | null>(
    null,
  );

  useEffect(() => {
    headingRef.current?.focus();
  }, []);

  useEffect(() => {
    let active = true;
    if (session.candidate === undefined) {
      void fetchRuleFormAuthority(token).then((outcome) => {
        if (!active) return;
        if (outcome.ok) {
          setAuthority(outcome.model);
          setObserved(authorityIdentity(outcome.model.active));
          const defaults = outcome.model.families[session.family];
          setValues((current) => {
            if (Object.keys(current).length > 0) return current;
            const seeded: FormValues = {};
            for (const field of defaults.fields) {
              if (defaults.values[field] !== undefined)
                seeded[field] = defaults.values[field];
            }
            return seeded;
          });
        } else {
          setAuthorityError(ruleFailureCopy(outcome.code));
        }
      });
    } else {
      // A copy candidate came from the backend projection; the form still needs
      // the field authority to render, which the same read provides.
      void fetchRuleFormAuthority(token).then((outcome) => {
        if (!active) return;
        if (outcome.ok) {
          setAuthority(outcome.model);
          setObserved(authorityIdentity(outcome.model.active));
        } else {
          setAuthorityError(ruleFailureCopy(outcome.code));
        }
      });
    }
    return () => {
      active = false;
    };
  }, [session.family, session.candidate, token]);

  const issues = localIssues;

  const change = (field: string, value: RuleFormValue) => {
    setValues((current) => {
      const next = { ...current, [field]: value };
      writeRuleDraft(session.family, draftKey, next);
      return next;
    });
    setDirty(true);
    setLocalIssues((current) => {
      if (!current.has(field)) return current;
      const next = new Map(current);
      next.delete(field);
      return next;
    });
  };

  /**
   * The warning's own discard action. It is a distinct intent from `attemptClose`
   * — which only arms the warning on the first click — so it forgets the
   * correctable candidate directly instead of routing back through the arming
   * logic.
   */
  const discardAndClose = () => {
    clearRuleDraft(session.family, draftKey);
    onClose();
  };

  const attemptClose = () => {
    if (dirty && state.kind !== "saving") {
      if (!discardArmed) {
        setDiscardArmed(true);
        return;
      }
      // The second close intent is an explicit discard, so it forgets the
      // candidate exactly like the warning's own discard action.
      clearRuleDraft(session.family, draftKey);
    }
    onClose();
  };

  const save = async () => {
    if (authority === null) return;
    const candidate = ruleCandidateFields(session.family, values);
    const problems = validateRuleCandidate(
      session.family,
      candidate,
      authority,
    );
    if (problems.length > 0) {
      setLocalIssues(
        new Map(problems.map((item) => [item.field, item.message])),
      );
      return;
    }
    setLocalIssues(new Map());
    setState({ kind: "saving" });
    if (observed === null) {
      setState({
        kind: "known-failure",
        code: "configuration_unavailable",
        nextAction: "重新打开表单以读取当前 Active 后再保存",
        durable: "active_unchanged",
      });
      return;
    }
    const outcome: RulesCommandResult = await saveRuleObject(
      token,
      session.family,
      candidate,
      observed,
    );
    if (outcome.ok) {
      clearRuleDraft(session.family, draftKey);
      onPublished(
        `${RULE_DRAWER_LABELS[session.family]}已发布为新的 Active,清单与就绪状态已刷新。`,
      );
      onClose();
      return;
    }
    const failure = classifySaveFailure(outcome);
    setState(failure);
  };

  const verify = async () => {
    setState({ kind: "verifying" });
    const observed = await fetchRuleActiveAuthority(token);
    if (observed.ok) {
      setState({
        kind: "verified",
        summary: `当前 Active 序号 ${observed.model.expectedVersion};若上次的保存已经生效,刷新后即可在清单中看到,请勿重复提交相同内容。`,
      });
    } else {
      setState({ kind: "unknown", code: observed.code });
    }
  };

  return (
    <div className="mf-rules-drawer-layer">
      <div
        className="mf-rules-drawer-backdrop"
        onClick={attemptClose}
        aria-hidden="true"
      />
      <section
        className="mf-files-drawer mf-rules-drawer"
        aria-label={
          session.mode === "copy"
            ? `复制${RULE_DRAWER_LABELS[session.family]}`
            : `添加${RULE_DRAWER_LABELS[session.family]}`
        }
        role="dialog"
        aria-modal="true"
      >
        <div className="mf-files-drawer-header">
          <div>
            <h2 ref={headingRef} tabIndex={-1}>
              {session.mode === "copy"
                ? `复制${RULE_DRAWER_LABELS[session.family]}`
                : `添加${RULE_DRAWER_LABELS[session.family]}`}
            </h2>
            <p className="mf-files-drawer-helper">
              保存会用一次操作校验完整后继配置并原子激活;失败时旧 Active
              保持不变,表单输入可以修正后重试。
            </p>
          </div>
          <button
            type="button"
            className="mf-files-drawer-close"
            aria-label="关闭规则表单"
            onClick={attemptClose}
            disabled={state.kind === "saving"}
          >
            ×
          </button>
        </div>
        <div className="mf-files-drawer-body">
          {authorityError !== null && (
            <p className="mf-storage-drawer-error" role="alert">
              表单权限读取失败:{authorityError}
            </p>
          )}
          {discardArmed && dirty && (
            <div className="mf-rules-discard" role="alert">
              <p>表单中有未保存的输入;关闭会丢弃这些修改。</p>
              <div className="mf-actions">
                <button type="button" onClick={discardAndClose}>
                  放弃并关闭
                </button>
                <button type="button" onClick={() => setDiscardArmed(false)}>
                  继续编辑
                </button>
              </div>
            </div>
          )}
          {state.kind === "known-failure" && (
            <div className="mf-rules-save-failure" role="alert">
              <p>
                保存未生效:{ruleFailureCopy(state.code)}
                {state.nextAction ? ` 下一步:${state.nextAction}` : ""}
              </p>
              <p className="mf-rules-durable">
                旧 Active 保持不变;当前输入已保留,可直接修正后重试。
              </p>
            </div>
          )}
          {state.kind === "unknown" && (
            <div className="mf-rules-save-unknown" role="status">
              <p>
                无法确认上次保存是否生效(结果未知)。系统不会自动重发;请先核实当前
                Active,再决定是否手动重试。
              </p>
              <div className="mf-actions">
                <button type="button" onClick={() => void verify()}>
                  核实当前 Active
                </button>
              </div>
            </div>
          )}
          {state.kind === "verifying" && (
            <p role="status">正在读取当前 Active...</p>
          )}
          {state.kind === "verified" && (
            <p className="mf-rules-verified" role="status">
              {state.summary}
            </p>
          )}
          {authority === null ? (
            <p role="status">正在读取表单字段权限...</p>
          ) : (
            <RulesObjectForm
              family={session.family}
              authority={authority}
              values={values}
              issues={issues}
              editing={false}
              disabled={state.kind === "saving"}
              onChange={change}
            />
          )}
          {authority !== null && token !== null ? (
            <RulesPreviewPanel
              token={token}
              family={session.family}
              objectId={null}
              authority={authority}
              values={values}
            />
          ) : null}
        </div>
        <div className="mf-rules-drawer-actions">
          <button
            type="button"
            className="mf-button mf-button-primary"
            onClick={() => void save()}
            disabled={authority === null || state.kind === "saving"}
          >
            {state.kind === "saving" ? "保存中..." : "保存"}
          </button>
          <button
            type="button"
            onClick={attemptClose}
            disabled={state.kind === "saving"}
          >
            取消
          </button>
        </div>
      </section>
    </div>
  );
}

/**
 * Split a failed Save into the two operator-visible outcomes the contract
 * requires. A known rejection keeps the prior Active and the correctable
 * candidate; a transport or unconfirmable result is never presented as a plain
 * failure, because the publication may or may not have happened — only an
 * explicit Active verification resolves it, and no automatic replay is offered.
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
