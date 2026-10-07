"""Error-risk gates fitted on DS1-cal on top of Robust.

Gc:  logistic regression on min, mean and 10th percentile of |SVM decision value|
     over the window's beats, plus the beat count.
Gcs: Gc features plus the four log SQIs.
"""

from __future__ import annotations

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import StandardScaler


def confidence_features(decision_values: np.ndarray) -> np.ndarray:
    """Gc features for one window."""
    a = np.abs(decision_values)
    if a.size == 0:
        return np.zeros(4)
    return np.array([a.min(), a.mean(), np.percentile(a, 10), float(a.size)])


def make_gate() -> Pipeline:
    """Standardised logistic regression (margins, counts and log SQIs differ in scale)."""
    return make_pipeline(StandardScaler(), LogisticRegression(max_iter=1000))
