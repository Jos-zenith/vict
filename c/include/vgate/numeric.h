#ifndef VGATE_NUMERIC_H
#define VGATE_NUMERIC_H

/* numpy's float64 add.reduce (np.sum, np.mean): pairwise summation with an
 * 8-way unrolled base case, starting from 0. Same rounding as NumPy. */
double vgate_pairwise_sum(const double *a, int n);

#endif
