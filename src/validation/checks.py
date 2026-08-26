"""Small, reusable building blocks shared by every entity validator."""

from collections import defaultdict

import pandas as pd

EMAIL_PATTERN = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


def is_blank(series: pd.Series) -> pd.Series:
    return series.astype(str).str.strip() == ""


def to_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def to_dates(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce")


def duplicated_nonblank(series: pd.Series) -> pd.Series:
    return series.duplicated(keep=False) & ~is_blank(series)


class ViolationCollector:
    """Accumulates every rule a row violates, keyed by DataFrame index.

    A row is never forced down to a single reason -- flag() can be called
    any number of times, and each matching row simply grows its list.
    """

    def __init__(self, df: pd.DataFrame):
        self._df = df
        self._violations = defaultdict(list)

    def flag(self, mask: pd.Series, code: str, message: str) -> None:
        for idx in self._df.index[mask.fillna(False)]:
            self._violations[idx].append({"code": code, "message": message})

    @property
    def violations(self) -> dict:
        return dict(self._violations)
