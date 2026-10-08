#ifndef VGATE_SVM_H
#define VGATE_SVM_H

/* Robust linear SVM of the frozen v1.0 design (src/vgate/design.py):
 *   decision = ((f - mean) / scale) . coef + intercept,  V when decision > VGATE_THRESHOLD. */

#include "vgate/params.h"

double vgate_svm_decision(const double f[VGATE_N_FEATURES]);

#endif
