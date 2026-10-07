"""Base and Robust classifiers: linear SVM, V vs non-V, class-weighted.

C is chosen by record-grouped 5-fold CV on clean DS1-train. Robust reuses the
same hyperparameters, trained on each DS1-train record clean and noisy.
"""

from __future__ import annotations

import numpy as np
from sklearn.metrics import balanced_accuracy_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import LinearSVC


def make_svm(C: float = 1.0, seed: int = 0) -> Pipeline:
    return make_pipeline(
        StandardScaler(),
        LinearSVC(C=C, class_weight="balanced", random_state=seed, dual=False),
    )


C_GRID = (0.001, 0.01, 0.1, 1.0, 10.0)


def grouped_cv_predictions(
    X: np.ndarray, y: np.ndarray, groups: np.ndarray, C: float, n_splits: int = 5
) -> np.ndarray:
    """Out-of-fold decision values, folds split by record."""
    out = np.zeros(len(y))
    for tr, te in GroupKFold(n_splits=n_splits).split(X, y, groups):
        out[te] = make_svm(C).fit(X[tr], y[tr]).decision_function(X[te])
    return out


def select_C(X: np.ndarray, y: np.ndarray, groups: np.ndarray) -> float:
    """Record-grouped 5-fold CV over a grid of C; highest balanced accuracy wins."""
    scores = {C: balanced_accuracy_score(y, grouped_cv_predictions(X, y, groups, C) > 0)
              for C in C_GRID}  # fmt: skip
    return max(scores, key=scores.get)
