"""Indian-rupee and number formatting for the dashboard presentation
layer.

These helpers only format values for *display* -- they never touch the
numeric values stored in or aggregated by the warehouse. Every monetary
figure the dashboard shows is INR; the ₹ symbol and the Indian
digit-grouping / lakh-crore conventions are applied here so the rest of
the UI code doesn't re-implement them.

Pure functions, no Streamlit import -- unit-tested directly in
tests/test_dashboard.py.
"""

from __future__ import annotations

from typing import Optional


def _coerce(value) -> Optional[float]:
    if value is None:
        return None
    try:
        num = float(value)
    except (TypeError, ValueError):
        return None
    if num != num:  # NaN
        return None
    return num


def indian_grouping(integer_digits: str) -> str:
    """Groups a string of digits the Indian way: the last three, then
    pairs (e.g. "1234567" -> "12,34,567")."""
    if len(integer_digits) <= 3:
        return integer_digits
    head, tail = integer_digits[:-3], integer_digits[-3:]
    # insert a comma every 2 digits from the right of `head`
    parts = []
    while len(head) > 2:
        parts.insert(0, head[-2:])
        head = head[:-2]
    parts.insert(0, head)
    return ",".join(parts) + "," + tail


def format_inr(value, *, decimals: int = 2) -> str:
    """Exact INR with the ₹ symbol and Indian digit grouping, e.g.
    ``₹12,34,567.89``. Used in tables and drill-downs where the precise
    figure matters. Returns ``—`` for a missing value."""
    num = _coerce(value)
    if num is None:
        return "—"
    sign = "-" if num < 0 else ""
    num = abs(num)
    whole = int(num)
    grouped = indian_grouping(str(whole))
    if decimals > 0:
        frac = f"{num - whole:.{decimals}f}"[2:]
        return f"{sign}₹{grouped}.{frac}"
    return f"{sign}₹{grouped}"


def format_inr_compact(value) -> str:
    """Magnitude-aware INR for KPIs, axis ticks and chart labels:
    ``₹1,250`` · ``₹45,000`` · ``₹1.25L`` · ``₹12.4L`` · ``₹1.20Cr``.
    Returns ``—`` for a missing value."""
    num = _coerce(value)
    if num is None:
        return "—"
    sign = "-" if num < 0 else ""
    num = abs(num)

    if num < 1_000:
        return f"{sign}₹{num:,.0f}"
    if num < 1_00_000:
        return f"{sign}₹{indian_grouping(str(int(round(num))))}"
    if num < 1_00_00_000:
        lakhs = num / 1_00_000
        return f"{sign}₹{lakhs:.1f}L" if lakhs >= 10 else f"{sign}₹{lakhs:.2f}L"
    crores = num / 1_00_00_000
    return f"{sign}₹{crores:.1f}Cr" if crores >= 10 else f"{sign}₹{crores:.2f}Cr"


def format_percent(value, *, decimals: int = 1) -> str:
    num = _coerce(value)
    if num is None:
        return "—"
    return f"{num:.{decimals}f}%"


def format_count(value) -> str:
    num = _coerce(value)
    if num is None:
        return "—"
    return f"{int(round(num)):,}"
