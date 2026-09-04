from __future__ import annotations

import calendar
from datetime import date
from typing import Optional, Tuple


class DateFilterParams:
    def __init__(
        self,
        year: Optional[int] = None,
        month: Optional[int] = None,
        week: Optional[int] = None,
        date_param: Optional[date] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
    ):
        self.year = year
        self.month = month
        self.week = week
        self.date_param = date_param
        self.date_from = date_from
        self.date_to = date_to


def resolve_date_range(params: DateFilterParams) -> Tuple[date, date]:
    """
    Precedence (highest → lowest):
    1. date        → (date, date)
    2. date_from + date_to → custom range
    3. week + year → ISO week Mon–Sun
    4. month + year → first/last of month
    5. year alone  → Jan 1 – Dec 31
    6. nothing     → (date.min, today)
    """
    if params.date_param is not None:
        return (params.date_param, params.date_param)

    if params.date_from is not None and params.date_to is not None:
        return (params.date_from, params.date_to)

    if params.week is not None:
        year = params.year or date.today().year
        # ISO week: get Monday by parsing iso calendar
        jan4 = date(year, 1, 4)
        week_start = jan4 - __import__("datetime").timedelta(days=jan4.isoweekday() - 1)
        # Move to requested week
        from datetime import timedelta
        week_start = week_start + timedelta(weeks=params.week - 1)
        week_end = week_start + timedelta(days=6)
        return (week_start, week_end)

    if params.month is not None and params.year is not None:
        first = date(params.year, params.month, 1)
        last_day = calendar.monthrange(params.year, params.month)[1]
        last = date(params.year, params.month, last_day)
        return (first, last)

    if params.year is not None:
        return (date(params.year, 1, 1), date(params.year, 12, 31))

    return (date.min, date.today())
