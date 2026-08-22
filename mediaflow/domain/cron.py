from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class _CronField:
    values: frozenset[int]
    wildcard: bool

    @classmethod
    def parse(cls, source: str, minimum: int, maximum: int, label: str) -> _CronField:
        if not source or any(character.isspace() for character in source):
            raise ValueError(f"Cron {label} field is invalid")
        values: set[int] = set()
        wildcard = source == "*"
        for token in source.split(","):
            if not token:
                raise ValueError(f"Cron {label} list contains an empty item")
            parts = token.split("/")
            if len(parts) > 2:
                raise ValueError(f"Cron {label} step is invalid")
            base = parts[0]
            step = 1
            if len(parts) == 2:
                if not parts[1].isdigit() or int(parts[1]) < 1:
                    raise ValueError(f"Cron {label} step must be positive")
                step = int(parts[1])
                if base != "*" and "-" not in base:
                    raise ValueError(f"Cron {label} stepped value must use * or a range")
            if base == "*":
                start, end = minimum, maximum
            elif "-" in base:
                bounds = base.split("-")
                if len(bounds) != 2 or not all(item.isdigit() for item in bounds):
                    raise ValueError(f"Cron {label} range is invalid")
                start, end = (int(item) for item in bounds)
                if start > end:
                    raise ValueError(f"Cron {label} range must not be reversed")
            elif base.isdigit():
                start = end = int(base)
            else:
                raise ValueError(f"Cron {label} supports numeric values only")
            if start < minimum or end > maximum:
                raise ValueError(f"Cron {label} must be between {minimum} and {maximum}")
            values.update(range(start, end + 1, step))
        if not values:
            raise ValueError(f"Cron {label} has no values")
        return cls(frozenset(values), wildcard)


@dataclass(frozen=True)
class CronExpression:
    source: str
    minutes: _CronField
    hours: _CronField
    days: _CronField
    months: _CronField
    weekdays: _CronField

    @classmethod
    def parse(cls, source: str) -> CronExpression:
        if not isinstance(source, str) or len(source) > 128:
            raise ValueError("Cron expression must be a string of at most 128 characters")
        fields = source.split()
        if len(fields) != 5:
            raise ValueError("Cron expression must contain exactly five fields")
        return cls(
            " ".join(fields),
            _CronField.parse(fields[0], 0, 59, "minute"),
            _CronField.parse(fields[1], 0, 23, "hour"),
            _CronField.parse(fields[2], 1, 31, "day-of-month"),
            _CronField.parse(fields[3], 1, 12, "month"),
            _CronField.parse(fields[4], 0, 6, "day-of-week"),
        )

    def next_at_or_after(self, instant: datetime, timezone: ZoneInfo) -> datetime:
        return self._next(instant, timezone, inclusive=True)

    def next_after(self, instant: datetime, timezone: ZoneInfo) -> datetime:
        return self._next(instant, timezone, inclusive=False)

    def _next(self, instant: datetime, timezone: ZoneInfo, *, inclusive: bool) -> datetime:
        if instant.tzinfo is None:
            raise ValueError("Cron evaluation instant must be timezone-aware")
        boundary = instant.astimezone(UTC)
        local_start = boundary.astimezone(timezone).date()
        for offset in range(366 * 8):
            candidate_date = local_start + timedelta(days=offset)
            if not self._date_matches(candidate_date):
                continue
            for hour in sorted(self.hours.values):
                for minute in sorted(self.minutes.values):
                    naive = datetime(
                        candidate_date.year,
                        candidate_date.month,
                        candidate_date.day,
                        hour,
                        minute,
                    )
                    local = naive.replace(tzinfo=timezone, fold=0)
                    candidate = local.astimezone(UTC)
                    # A nonexistent DST wall time does not round-trip and is skipped. For an
                    # ambiguous wall time fold=0 is deliberately the single emitted occurrence.
                    if candidate.astimezone(timezone).replace(tzinfo=None) != naive:
                        continue
                    if candidate > boundary or (inclusive and candidate == boundary):
                        return candidate
        raise ValueError("Cron expression has no occurrence within the bounded eight-year window")

    def _date_matches(self, value: date) -> bool:
        if value.month not in self.months.values or value.day not in self.days.values:
            day_match = False
        else:
            day_match = True
        # Python Monday=0; Cron Sunday=0.
        weekday_match = ((value.weekday() + 1) % 7) in self.weekdays.values
        if self.days.wildcard and self.weekdays.wildcard:
            selected_day = True
        elif self.days.wildcard:
            selected_day = weekday_match
        elif self.weekdays.wildcard:
            selected_day = day_match
        else:
            selected_day = day_match or weekday_match
        return value.month in self.months.values and selected_day
