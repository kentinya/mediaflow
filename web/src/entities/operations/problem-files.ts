/**
 * The aggregate Attention problem-file page (Slice 59 / V2-OPS-022).
 *
 * One entry joins the exact Task Center run document with the same durable
 * TaskItem the native detail/recovery surface reads.  The aggregate counts are
 * deliberately split: `total` is the current filter's file count, while
 * `problemFileTotal` deduplicates a file that carries several current
 * problems and each `problemFileCounts` value keeps its real overlapping
 * membership.  Normalization fails closed so an approximate count or an item
 * without its owning Task is never rendered.
 */

import {
  normalizeBoundedCount,
  normalizeEnum,
  normalizeOptionalText,
  readRecord,
} from "../shared/normalize";
import {
  RUN_PROBLEM_TYPES,
  normalizeRunSummary,
  type RunProblemType,
  type RunSummary,
} from "./run";
import { normalizeTaskItemSummary, type TaskItemSummary } from "./task";

export interface RunProblemFileEntry {
  readonly run: RunSummary;
  readonly item: TaskItemSummary;
  readonly problemTypes: readonly RunProblemType[];
}

export interface RunProblemFilesPage {
  readonly problem: RunProblemType | null;
  readonly limit: number;
  readonly items: readonly RunProblemFileEntry[];
  /** The current filter's complete matching file count. */
  readonly total: number;
  /** Distinct Task/file entries across all four current problem types. */
  readonly problemFileTotal: number;
  readonly taskTotal: number;
  readonly problemFileCounts: Readonly<Record<RunProblemType, number>>;
  readonly from: string | null;
  readonly to: string | null;
  readonly truncated: boolean;
  readonly previousCursor: string | null;
  readonly nextCursor: string | null;
}

function fail(): never {
  throw new Error(
    "operations problem file response did not match the contract",
  );
}

function optionalText(
  source: Record<string, unknown>,
  field: string,
): string | null {
  try {
    return normalizeOptionalText(source[field], field);
  } catch {
    return fail();
  }
}

function count(source: Record<string, unknown>, field: string): number {
  try {
    return normalizeBoundedCount(source[field], field);
  } catch {
    return fail();
  }
}

function flag(source: Record<string, unknown>, field: string): boolean {
  const value = source[field];
  if (typeof value !== "boolean") fail();
  return value;
}

function normalizeProblemTypes(value: unknown): readonly RunProblemType[] {
  if (!Array.isArray(value) || value.length === 0) fail();
  const problems = value.map((entry) => {
    try {
      return normalizeEnum(entry, "problem_types", RUN_PROBLEM_TYPES);
    } catch {
      return fail();
    }
  });
  if (new Set(problems).size !== problems.length) fail();
  return problems;
}

function normalizeProblemCounts(
  value: unknown,
): Readonly<Record<RunProblemType, number>> {
  const source = readRecord(value, "problem_file_counts");
  const counts: Record<string, number> = {};
  for (const problem of RUN_PROBLEM_TYPES) {
    counts[problem] = count(source, problem);
  }
  return counts as Readonly<Record<RunProblemType, number>>;
}

export function normalizeRunProblemFilesPage(
  payload: unknown,
): RunProblemFilesPage {
  const source = readRecord(payload, "problem_files");
  let problem: RunProblemType | null = null;
  if (source["problem"] !== null && source["problem"] !== undefined) {
    try {
      problem = normalizeEnum(
        source["problem"],
        "problem_files.problem",
        RUN_PROBLEM_TYPES,
      );
    } catch {
      fail();
    }
  }
  const rawItems = source["items"];
  if (!Array.isArray(rawItems) || rawItems.length > 100) fail();
  const items: RunProblemFileEntry[] = rawItems.map((entry) => {
    const record = readRecord(entry, "problem_files.items");
    const run = normalizeRunSummary(record["run"]);
    const item = normalizeTaskItemSummary(
      readRecord(record["item"], "problem_files.items.item"),
    );
    const problemTypes = normalizeProblemTypes(record["problem_types"]);
    // The entry's owning Task is the exact persisted identity on both sides;
    // a run without that identity cannot own an item row.
    if (run.taskId === null || run.taskId !== item.taskId) fail();
    if (problem !== null && !problemTypes.includes(problem)) fail();
    return { run, item, problemTypes };
  });
  const total = count(source, "total");
  const problemFileTotal = count(source, "problem_file_total");
  const taskTotal = count(source, "task_total");
  const problemFileCounts = normalizeProblemCounts(
    source["problem_file_counts"],
  );
  if (items.length > total || total > problemFileTotal) fail();
  if (problem === null && total !== problemFileTotal) fail();
  if (problem !== null && problemFileCounts[problem] < total) fail();
  const pageTasks = new Set(items.map((entry) => entry.run.runId));
  if (pageTasks.size > taskTotal) fail();
  return {
    problem,
    limit: count(source, "limit"),
    items,
    total,
    problemFileTotal,
    taskTotal,
    problemFileCounts,
    from: optionalText(source, "from"),
    to: optionalText(source, "to"),
    truncated: flag(source, "truncated"),
    previousCursor: optionalText(source, "previous_cursor"),
    nextCursor: optionalText(source, "next_cursor"),
  };
}
