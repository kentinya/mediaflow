/**
 * The refresh-safe full-page rules editor (Slice 41, Task 41.2).
 *
 * Route identity (`/rules/edit/$family/$objectId`) carries the editing subject,
 * so a browser refresh, a deep link or a reconnect resumes the same object
 * without borrowing state from the list page. The exact Active identity for the
 * eventual Save is always re-read fresh from the server projection; it is never
 * transferred through the URL and never asked of the operator.
 *
 * Unsaved input is kept in the session-memory correctable draft across failed
 * Save, navigation, refresh and reconnect, and leaving with unsaved input warns
 * before discarding. A known failure preserves the prior Active and the input;
 * an unknown outcome offers Active verification only — never a silent replay.
 */

import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "@tanstack/react-router";
import {
  authorityIdentity,
  ruleCandidateFields,
  ruleFailureCopy,
  validateRuleCandidate,
  type RuleFormAuthority,
  type RuleFormFamily,
  type RuleFormValue,
} from "../../entities/rules/rules-form";
import { RULE_FORM_FAMILIES } from "../../entities/rules/rules-form";
import {
  editRuleObject,
  fetchRuleEdit,
  fetchRuleFormAuthority,
  fetchRulesInventory,
  type RulesCommandResult,
} from "../../shared/api/api-client";
import { useAuthToken } from "../../shared/api/auth-context";
import { classifySaveFailure } from "./RulesObjectDrawer";
import { RulesObjectForm, type FormValues } from "./RulesObjectForm";
import {
  readRuleDraft,
  RULE_DRAWER_LABELS,
  RULE_RETURN_TO_LABEL,
  writeRuleDraft,
  clearRuleDraft,
} from "./rules-workspace-labels";

const FAMILY_SET: ReadonlySet<string> = new Set(RULE_FORM_FAMILIES);

export function isRuleEditFamily(value: string): value is RuleFormFamily {
  return FAMILY_SET.has(value);
}

export function RulesEditPage() {
  // Route identity carries the editing subject, so refresh / deep link /
  // reconnect all resolve to this same object without borrowed list state.
  const { family = "", objectId = "" } = useParams({ strict: false }) as {
    family?: string;
    objectId?: string;
  };
  const token = useAuthToken();
  const headingRef = useRef<HTMLHeadingElement>(null);
  const [authority, setAuthority] = useState<RuleFormAuthority | null>(null);
  const [projection, setProjection] = useState<{
    readonly subject: string;
    readonly outcome: Awaited<ReturnType<typeof fetchRuleEdit>>;
  } | null>(null);
  const [loaded, setLoaded] = useState<{
    readonly subject: string;
    readonly values: FormValues | null;
    readonly dirty: boolean;
  } | null>(null);

  const [state, setState] = useState<
    | { kind: "idle" }
    | { kind: "saving" }
    | { kind: "known-failure"; code: string; nextAction: string | null }
    | { kind: "unknown"; code: string }
    | { kind: "published"; message: string }
  >({ kind: "idle" });
  const [issues, setIssues] = useState<ReadonlyMap<string, string>>(new Map());

  const validFamily = isRuleEditFamily(family);

  useEffect(() => {
    headingRef.current?.focus();
  }, [objectId]);

  useEffect(() => {
    if (!validFamily || token === null) return;
    let active = true;
    // Every result lands in one typed snapshot keyed by the subject it was
    // fetched for, so a refresh or navigation to a different object never shows
    // a stale projection and no state reset is needed in the effect body.
    void Promise.all([
      fetchRuleFormAuthority(token),
      fetchRuleEdit(token, family, objectId),
    ]).then(([authorityOutcome, editOutcome]) => {
      if (!active) return;
      if (authorityOutcome.ok) setAuthority(authorityOutcome.model);
      const subject = `${family}/${objectId}`;
      setProjection({ subject, outcome: editOutcome });
      if (editOutcome.ok) {
        // A failed Save left a correctable draft for this exact object: restore
        // it across refresh/navigation instead of silently discarding input.
        const draft = readRuleDraft(family as RuleFormFamily, objectId);
        setLoaded({
          subject,
          values: (draft ?? editOutcome.model.value) as unknown as FormValues,
          dirty: draft !== undefined,
        });
      } else {
        setLoaded({ subject, values: null, dirty: false });
      }
    });
    return () => {
      active = false;
    };
  }, [validFamily, family, objectId, token]);

  // Leaving with unsaved input is never silent: the browser warns, and the
  // in-app return clears the draft only after an explicit confirmation below.
  const dirty =
    loaded?.dirty === true && loaded.subject === `${family}/${objectId}`;
  useEffect(() => {
    if (!dirty) return;
    const handler = (event: BeforeUnloadEvent) => {
      event.preventDefault();
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [dirty]);

  const change = (field: string, value: RuleFormValue) => {
    if (!validFamily) return;
    const subject = `${family}/${objectId}`;
    const next = { ...(loaded?.values ?? {}), [field]: value };
    // The correctable draft mirrors the input on every keystroke, so a failed
    // Save, refresh, reconnect or navigation never silently discards it.
    writeRuleDraft(family as RuleFormFamily, objectId, next);
    setLoaded({ subject, values: next, dirty: true });
    setIssues((current) => {
      if (!current.has(field)) return current;
      const merged = new Map(current);
      merged.delete(field);
      return merged;
    });
  };

  const saved = state.kind === "published";

  const returnTo = useMemo(
    () => (
      <div className="mf-actions">
        <Link
          className="mf-button"
          to="/rules"
          onClick={(event) => {
            if (dirty && validFamily) {
              if (!window.confirm("表单中有未保存的修改,确定离开并丢弃吗?")) {
                event.preventDefault();
                return;
              }
              clearRuleDraft(family as RuleFormFamily, objectId);
            }
          }}
        >
          {RULE_RETURN_TO_LABEL}
        </Link>
      </div>
    ),
    [dirty, family, objectId, validFamily],
  );

  if (!validFamily || !/^[A-Za-z0-9._:-]{1,256}$/.test(objectId)) {
    return (
      <section className="mf-rules-state" role="alert">
        <h2>无法打开该对象</h2>
        <p>
          编辑路由的分类或对象 ID 不符合受支持的形态;Active 未发生任何变化。
        </p>
        <Link to="/rules">{RULE_RETURN_TO_LABEL}</Link>
      </section>
    );
  }

  if (token === null) {
    return (
      <section className="mf-rules-state" role="status">
        <p>需要连接 API 身份后才能编辑规则。</p>
      </section>
    );
  }

  const subject = `${family}/${objectId}`;
  if (
    projection === null ||
    projection.subject !== subject ||
    loaded === null ||
    loaded.subject !== subject
  ) {
    return (
      <section className="mf-rules-state" role="status">
        <p>正在读取该对象的 Active 投影...</p>
      </section>
    );
  }

  const values = loaded.values;
  const projectionOutcome = projection.outcome;
  if (!projectionOutcome.ok || authority === null || values === null) {
    const code = projectionOutcome.ok
      ? "malformed_response"
      : projectionOutcome.code;
    return (
      <section className="mf-rules-state" role="alert">
        <h2>无法读取该对象</h2>
        <p>{ruleFailureCopy(code)}</p>
        {!projectionOutcome.ok && projectionOutcome.details?.nextAction ? (
          <p>{projectionOutcome.details.nextAction}</p>
        ) : null}
        {returnTo}
      </section>
    );
  }

  const typedFamily = family as RuleFormFamily;

  const save = async () => {
    const candidate = ruleCandidateFields(typedFamily, values);
    const problems = validateRuleCandidate(typedFamily, candidate, authority);
    if (problems.length > 0) {
      setIssues(new Map(problems.map((item) => [item.field, item.message])));
      return;
    }
    setIssues(new Map());
    setState({ kind: "saving" });
    // The Save composes against the exact Active identity this projection was
    // read from, so a concurrent publication fails as a stale conflict instead
    // of rewriting over whatever became Active since the page opened.
    const observed = authorityIdentity(projectionOutcome.model.active);
    const command: RulesCommandResult = await editRuleObject(
      token,
      typedFamily,
      objectId,
      candidate,
      observed,
    );
    if (command.ok) {
      clearRuleDraft(typedFamily, objectId);
      // Re-read the shared Active inventory/readiness projection after the
      // publication. The edit page does not own a second inventory authority;
      // this refresh confirms the new Active is what the workspace will show.
      await fetchRulesInventory(token).catch(() => undefined);
      setState({
        kind: "published",
        message: "已发布为新的 Active;返回清单即可看到新对象,或继续编辑。",
      });
      // The published successor is now durable state, not unsaved input.
      setLoaded({
        subject,
        values: command.model.value as unknown as FormValues,
        dirty: false,
      });
      return;
    }
    const failure = classifySaveFailure(command);
    setState(
      failure.kind === "unknown"
        ? { kind: "unknown", code: failure.code }
        : {
            kind: "known-failure",
            code: failure.code,
            nextAction: failure.nextAction,
          },
    );
  };

  const reloadActive = async () => {
    const fresh = await fetchRuleEdit(token, typedFamily, objectId);
    setProjection({ subject, outcome: fresh });
    if (fresh.ok) {
      const discard = window.confirm(
        "已读取当前 Active。确认后丢弃当前候选输入并采用 Active 吗?",
      );
      if (!discard) return;
      clearRuleDraft(typedFamily, objectId);
      setLoaded({
        subject,
        values: fresh.model.value as unknown as FormValues,
        dirty: false,
      });
    }
  };

  return (
    <section className="mf-rules-edit-page">
      <header className="mf-rules-header">
        <div>
          <p className="mf-eyebrow">
            编辑{RULE_DRAWER_LABELS[typedFamily]} · Active 序号{" "}
            {(projectionOutcome.model.active.revisionSequence as number) ?? "-"}
          </p>
          <h1 ref={headingRef} tabIndex={-1}>
            {objectId}
          </h1>
          <p>
            ID 不可更改;保存会用一次操作校验完整后继配置并原子激活,失败时旧
            Active 与你的输入都保持不变。
          </p>
        </div>
        {returnTo}
      </header>
      {saved && (
        <div className="mf-rules-published" role="status">
          <p>{state.kind === "published" ? state.message : ""}</p>
        </div>
      )}
      {state.kind === "known-failure" && (
        <div className="mf-rules-save-failure" role="alert">
          <p>
            保存未生效:{ruleFailureCopy(state.code)}
            {state.nextAction ? ` 下一步:${state.nextAction}` : ""}
          </p>
          <p className="mf-rules-durable">
            旧 Active 保持不变;当前输入已保留,可修正后重试。
          </p>
        </div>
      )}
      {state.kind === "unknown" && (
        <div className="mf-rules-save-unknown" role="status">
          <p>
            无法确认上次保存是否生效。系统不会自动重发;请先读取当前 Active
            核实结果,再决定是否手动重试。
          </p>
          <div className="mf-actions">
            <button type="button" onClick={() => void reloadActive()}>
              读取当前 Active 核实
            </button>
          </div>
        </div>
      )}
      <RulesObjectForm
        family={typedFamily}
        authority={authority}
        values={values}
        issues={issues}
        editing
        disabled={state.kind === "saving"}
        onChange={change}
      />
      <div className="mf-rules-drawer-actions">
        <button
          type="button"
          className="mf-button mf-button-primary"
          onClick={() => void save()}
          disabled={state.kind === "saving"}
        >
          {state.kind === "saving" ? "保存中..." : "保存"}
        </button>
        {returnTo}
      </div>
    </section>
  );
}
