/**
 * Local-time display and creation-day boundaries for the task center.
 *
 * The date inputs are calendar days in the operator's own browser timezone;
 * the list shows the same instants in that same timezone with an explicit
 * UTC offset. The backend still receives unambiguous UTC instants, but the
 * browser never hard-codes UTC as the operator's calendar.
 */

const DATE_ONLY = /^(\d{4})-(\d{2})-(\d{2})$/;

function pad(value: number): string {
  return String(value).padStart(2, "0");
}

function parseLocalDate(value: string): {
  readonly year: number;
  readonly month: number;
  readonly day: number;
} | null {
  const match = DATE_ONLY.exec(value);
  if (match === null) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  const date = new Date(year, month - 1, day, 0, 0, 0, 0);
  if (
    date.getFullYear() !== year ||
    date.getMonth() !== month - 1 ||
    date.getDate() !== day
  ) {
    return null;
  }
  return { year, month, day };
}

/** The selected calendar day for one submitted boundary value. */
export function localDateInputValue(value: string): string {
  return DATE_ONLY.test(value) ? value : value.slice(0, 10);
}

/** The inclusive first instant of one local calendar day, as a UTC instant. */
export function localDayStartIso(value: string): string | null {
  const parts = parseLocalDate(value);
  if (parts === null) return null;
  return new Date(
    parts.year,
    parts.month - 1,
    parts.day,
    0,
    0,
    0,
    0,
  ).toISOString();
}

/**
 * The inclusive last microsecond of one local calendar day, as a UTC instant.
 * The backend compares `sort_at <= to`, so the boundary must cover the whole
 * final second including the durable microsecond part, not stop at `:59.999`.
 */
export function localDayEndIso(value: string): string | null {
  const parts = parseLocalDate(value);
  if (parts === null) return null;
  const nextDay = new Date(
    parts.year,
    parts.month - 1,
    parts.day + 1,
    0,
    0,
    0,
    0,
  );
  const lastMillisecond = new Date(nextDay.getTime() - 1).toISOString();
  return lastMillisecond.replace(/\.999Z$/, ".999999Z");
}

/**
 * Render one durable timestamp in the browser's local timezone with its
 * explicit offset, so the list and the local-day filter describe one calendar.
 */
export function formatRunDateTime(value: string): string {
  if (DATE_ONLY.test(value)) return value;
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  const offsetMinutes = -parsed.getTimezoneOffset();
  const sign = offsetMinutes >= 0 ? "+" : "-";
  const absolute = Math.abs(offsetMinutes);
  return (
    `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())}` +
    ` ${pad(parsed.getHours())}:${pad(parsed.getMinutes())}:${pad(parsed.getSeconds())}` +
    ` ${sign}${pad(Math.floor(absolute / 60))}:${pad(absolute % 60)}`
  );
}
