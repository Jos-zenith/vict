#include "vgate/numeric.h"

/* numpy/_core/src/umath/loops_utils.h.src, pairwise_sum (PW_BLOCKSIZE 128). */
double vgate_pairwise_sum(const double *a, int n)
{
    if (n < 8) {
        double res = 0.0;
        for (int i = 0; i < n; ++i) res += a[i];
        return res;
    }
    if (n <= 128) {
        double r[8], res;
        int i;
        for (i = 0; i < 8; ++i) r[i] = a[i];
        for (i = 8; i < n - (n % 8); i += 8) {
            r[0] += a[i + 0];
            r[1] += a[i + 1];
            r[2] += a[i + 2];
            r[3] += a[i + 3];
            r[4] += a[i + 4];
            r[5] += a[i + 5];
            r[6] += a[i + 6];
            r[7] += a[i + 7];
        }
        res = ((r[0] + r[1]) + (r[2] + r[3])) + ((r[4] + r[5]) + (r[6] + r[7]));
        for (; i < n; ++i) res += a[i];
        return res;
    }
    int n2 = n / 2;
    n2 -= n2 % 8;
    return vgate_pairwise_sum(a, n2) + vgate_pairwise_sum(a + n2, n - n2);
}
