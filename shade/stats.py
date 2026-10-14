"""Inequality measures over sections: concentration index, quintiles, rank correlation."""
from __future__ import annotations

import numpy as np
import pandas as pd


def concentration_index(value, income, weight) -> float:
    """Population-weighted concentration index of `value` along the income ranking.

    Twice the weighted covariance between the value and the fractional income rank, over the
    mean value. Ranges from −1 to 1: positive when the value (shade) piles up in richer
    sections, negative when in poorer ones, 0 when it is spread evenly. Same measure that
    health economics uses for income-related inequality (Wagstaff, van Doorslaer & Paci 1989;
    O'Donnell et al. 2008).
    """
    df = pd.DataFrame({"h": value, "y": income, "w": weight}).dropna()
    df = df[df.w > 0].sort_values("y", kind="mergesort")
    if len(df) < 10 or df.h.mean() == 0:
        return float("nan")
    w = df.w.to_numpy(float) / df.w.sum()
    rank = np.cumsum(w) - w / 2   # fractional rank of each section's residents
    mu = np.sum(w * df.h.to_numpy(float))
    cov = np.sum(w * (df.h.to_numpy(float) - mu) * (rank - 0.5))
    return float(2 * cov / mu)


def income_quintiles(income, weight) -> pd.Series:
    """Quintile (1 poorest … 5 richest) of each section, so each holds a fifth of the residents."""
    df = pd.DataFrame({"y": income, "w": weight}).dropna().sort_values("y", kind="mergesort")
    share = (df.w.cumsum() - df.w / 2) / df.w.sum()
    return pd.Series(np.minimum((share * 5).astype(int) + 1, 5), index=df.index).reindex(
        pd.Index(income.index if hasattr(income, "index") else range(len(income))))


def weighted_mean(value, weight) -> float:
    df = pd.DataFrame({"v": value, "w": weight}).dropna()
    return float(np.average(df.v, weights=df.w)) if df.w.sum() > 0 else float("nan")


def spearman(a, b) -> float:
    df = pd.DataFrame({"a": a, "b": b}).dropna()
    return float(df.a.rank().corr(df.b.rank())) if len(df) > 2 else float("nan")
