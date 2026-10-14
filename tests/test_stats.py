import numpy as np
import pandas as pd

from shade import stats


def test_concentration_index_signs():
    income = pd.Series(np.arange(100, dtype=float))
    w = pd.Series(np.ones(100))
    assert stats.concentration_index(income + 1, income, w) > 0.3     # shade where the rich are
    assert stats.concentration_index(101 - income, income, w) < -0.3  # shade where the poor are
    assert abs(stats.concentration_index(pd.Series(np.full(100, 7.0)), income, w)) < 1e-12


def test_concentration_index_extreme():
    # All shade in the richest section of n equal ones: C = 1 - 1/n.
    n = 50
    income = pd.Series(np.arange(n, dtype=float))
    h = pd.Series(np.r_[np.zeros(n - 1), 1.0])
    assert abs(stats.concentration_index(h, income, pd.Series(np.ones(n))) - (1 - 1 / n)) < 1e-9


def test_concentration_index_weights_matter():
    income = pd.Series(np.arange(20, dtype=float))
    h = pd.Series(np.arange(20, dtype=float))
    even = stats.concentration_index(h, income, pd.Series(np.ones(20)))
    # Doubling everyone's weight changes nothing; it is a share of residents, not a count.
    assert abs(even - stats.concentration_index(h, income, pd.Series(np.full(20, 2.0)))) < 1e-12


def test_quintiles_split_residents():
    income = pd.Series(np.arange(10, dtype=float))
    q = stats.income_quintiles(income, pd.Series(np.ones(10)))
    assert q.tolist() == [1, 1, 2, 2, 3, 3, 4, 4, 5, 5]
