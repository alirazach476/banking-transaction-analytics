import numpy as np
import pandas as pd
from src.monitoring.drift import group_rates, psi


def test_psi_identical_is_near_zero():
    x = np.random.default_rng(0).normal(size=5000)
    assert psi(x, x) < 1e-3


def test_psi_detects_shift():
    r = np.random.default_rng(1)
    assert psi(r.normal(0, 1, 5000), r.normal(1.5, 1, 5000)) > 0.25


def test_psi_binary_feature():
    assert psi(np.r_[np.zeros(900), np.ones(100)], np.r_[np.zeros(500), np.ones(500)]) > 0.25


def test_group_rates():
    df = pd.DataFrame({"g": ["a", "a", "b", "b"], "y": [1, 0, 1, 0], "f": [1, 1, 0, 0]})
    r = group_rates(df, "g", "y", "f").set_index("g")
    assert r.loc["a", "tpr"] == 1 and r.loc["a", "fpr"] == 1 and r.loc["b", "tpr"] == 0
