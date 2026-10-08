#include "vgate/svm.h"

double vgate_svm_decision(const double f[VGATE_N_FEATURES])
{
    double dot = 0.0;
    for (int j = 0; j < VGATE_N_FEATURES; ++j)
        dot += (f[j] - vgate_svm_mean[j]) / vgate_svm_scale[j] * vgate_svm_coef[j];
    return dot + vgate_svm_intercept;
}
