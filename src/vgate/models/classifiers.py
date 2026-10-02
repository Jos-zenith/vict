"""Base and Robust classifiers: linear SVM, V vs non-V, class-weighted.

C is chosen by record-grouped 5-fold CV on clean DS1-train. Robust reuses the
same hyperparameters, trained on each DS1-train record clean and noisy.
"""

from __future__ import annotations

import numpy as np
from sklearn.pipeline import Pipeline, make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import LinearSVC


def make_svm(C: float = 1.0, seed: int = 0) -> Pipeline:
    return make_pipeline(
        StandardScaler(),
        LinearSVC(C=C, class_weight="balanced", random_state=seed),
    )


def select_C(X: np.ndarray, y: np.ndarray, groups: np.ndarray) -> float:
    """Record-grouped 5-fold CV over a grid of C."""
    raise NotImplementedError
