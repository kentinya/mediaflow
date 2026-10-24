/**
 * Per-field recovery of a focused Automation settings submission.
 *
 * A retained submission (or an edit whose target moved) must never be re-armed
 * as a whole against a newer publication: that silently reverts whatever another
 * writer changed in the fields this operator did not touch. Recovery therefore
 * works one field at a time, comparing three values:
 *
 * - **B** — the published value the edit started from (the baseline),
 * - **I** — what the operator typed,
 * - **C** — the value published now.
 *
 * | case | result |
 * |---|---|
 * | `I` equals `B` (not changed) | use `C`: another writer's change is kept |
 * | `I` differs and `C` equals `B` | keep `I`: it is simply not saved yet |
 * | `I` differs and `C` equals `I` | use `C`: nothing to publish for this field |
 * | `I`, `C` and `B` all differ | a real same-field conflict → explicit choice |
 *
 * A missing baseline (a context retained by an older build) cannot be guessed,
 * so every field whose typed value differs from `C` becomes an explicit choice.
 * Nothing here publishes, retries or infers an identity: it only decides what
 * the form should show and whether a Save may be offered.
 */

import {
  AUTOMATION_ENGINE_FIELDS,
  type AutomationEngineField,
} from "../../entities/operations/automation-settings";

export type FormValues = Readonly<Record<string, string>>;

/** Which side of a same-field conflict the operator picked. */
export type FieldResolution = "current" | "mine";

export interface RecoveryPlan {
  /** The values the form should show: deterministic merges already applied. */
  readonly input: Record<string, string>;
  /** Fields a real conflict (or an unknown baseline) left undecided. */
  readonly conflicts: readonly AutomationEngineField[];
  /** One human-readable line per decided/undecided field, for the form's copy. */
  readonly notes: readonly string[];
  /** True while any field still needs an explicit choice. */
  readonly blocked: boolean;
}

/**
 * Text equality that respects numbers without ever truncating them.
 *
 * `"5.0"` and `"5"` are the same number, so a formatting difference is not a
 * pending edit; `"3.5"` and `"3"` are not, and `Number()` (never `parseInt`)
 * keeps a fractional entry intact so the backend's real validation sees it.
 */
export function sameTypedValue(
  a: string | undefined,
  b: string | undefined,
): boolean {
  if (a === undefined || b === undefined) return a === b;
  const left = a.trim();
  const right = b.trim();
  if (left === right) return true;
  const leftNumber = left === "" ? Number.NaN : Number(left);
  const rightNumber = right === "" ? Number.NaN : Number(right);
  if (!Number.isFinite(leftNumber) || !Number.isFinite(rightNumber))
    return false;
  return leftNumber === rightNumber;
}

function fieldLabel(field: AutomationEngineField): string {
  switch (field) {
    case "automation.maximumActiveJobs":
      return "并行任务上限";
    case "automation.staleJobAgeSeconds":
      return "任务失效判定时间";
    case "automation.workerPollSeconds":
      return "Worker 轮询间隔";
    case "automation.schedulerPollSeconds":
      return "调度器轮询间隔";
    default:
      return field;
  }
}

export interface RecoveryOptions {
  /** The operator's typed input (text, so an invalid entry survives). */
  readonly typed: FormValues;
  /**
   * The published values the edit started from, or `null` when the retained
   * context predates this field. A missing baseline is *not* inferred.
   */
  readonly baseline: FormValues | null;
  /** The values published right now. */
  readonly current: FormValues;
  /** Choices the operator already made for conflicting fields. */
  readonly resolutions?: Readonly<Record<string, FieldResolution | undefined>>;
}

/**
 * Merge only what the operator actually changed into the current target.
 *
 * Deterministic cases complete without any confirmation; only a genuine
 * same-field conflict (or an unknown baseline) leaves `blocked` true, and the
 * form then requires an explicit "keep mine" / "use current" choice before a
 * Save is offered.
 */
export function planRecovery(options: RecoveryOptions): RecoveryPlan {
  const input: Record<string, string> = {};
  const conflicts: AutomationEngineField[] = [];
  const notes: string[] = [];
  const resolutions = options.resolutions ?? {};
  for (const field of AUTOMATION_ENGINE_FIELDS) {
    const current = options.current[field] ?? "";
    const typed = options.typed[field] ?? current;
    input[field] = current;
    if (options.baseline === null) {
      if (sameTypedValue(typed, current)) continue;
      const choice = resolutions[field];
      if (choice === "mine") {
        input[field] = typed;
        continue;
      }
      if (choice === "current") continue;
      input[field] = typed;
      conflicts.push(field);
      notes.push(
        `${fieldLabel(field)}:本次提交没有可用的原始编辑基线,当前发布值为 ${current},你输入的值是 ${typed}。请明确选择采用当前值或保留你的修改。`,
      );
      continue;
    }
    const baseline = options.baseline[field] ?? "";
    const edited = !sameTypedValue(typed, baseline);
    if (!edited) {
      // Not changed by this operator: the other writer's value wins.
      continue;
    }
    if (sameTypedValue(current, baseline)) {
      // Still not saved: keep the operator's value.
      input[field] = typed;
      notes.push(`${fieldLabel(field)}:你修改的值 ${typed} 尚未保存。`);
      continue;
    }
    if (sameTypedValue(current, typed)) {
      // Someone already published exactly this value.
      continue;
    }
    const choice = resolutions[field];
    if (choice === "mine") {
      input[field] = typed;
      continue;
    }
    if (choice === "current") {
      continue;
    }
    input[field] = typed;
    conflicts.push(field);
    notes.push(
      `${fieldLabel(field)}:当前发布值为 ${current},你输入的值是 ${typed}。请明确选择采用当前值或保留你的修改。`,
    );
  }
  return { input, conflicts, notes, blocked: conflicts.length > 0 };
}
