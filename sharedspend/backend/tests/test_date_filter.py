from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.services.date_filter import DateFilterParams, resolve_date_range


def test_specific_date():
    d = date(2025, 7, 15)
    params = DateFilterParams(date_param=d)
    start, end = resolve_date_range(params)
    assert start == d
    assert end == d


def test_custom_range():
    start_d = date(2025, 7, 1)
    end_d = date(2025, 7, 31)
    params = DateFilterParams(date_from=start_d, date_to=end_d)
    start, end = resolve_date_range(params)
    assert start == start_d
    assert end == end_d


def test_week_filter():
    # ISO week 1 of 2024: Mon Jan 1 – Sun Jan 7
    params = DateFilterParams(week=1, year=2024)
    start, end = resolve_date_range(params)
    assert start.weekday() == 0  # Monday
    assert (end - start).days == 6  # 7 days span


def test_month_filter():
    params = DateFilterParams(year=2025, month=2)
    start, end = resolve_date_range(params)
    assert start == date(2025, 2, 1)
    assert end == date(2025, 2, 28)


def test_year_filter():
    params = DateFilterParams(year=2025)
    start, end = resolve_date_range(params)
    assert start == date(2025, 1, 1)
    assert end == date(2025, 12, 31)


def test_no_filter():
    params = DateFilterParams()
    start, end = resolve_date_range(params)
    assert start == date.min
    assert end == date.today()


def test_date_param_takes_precedence_over_range():
    d = date(2025, 7, 10)
    params = DateFilterParams(
        date_param=d,
        date_from=date(2025, 1, 1),
        date_to=date(2025, 12, 31),
    )
    start, end = resolve_date_range(params)
    assert start == d
    assert end == d


def test_week_without_year_uses_current_year():
    params = DateFilterParams(week=1)
    start, end = resolve_date_range(params)
    # Should resolve without error; start should be a Monday
    assert start.weekday() == 0
