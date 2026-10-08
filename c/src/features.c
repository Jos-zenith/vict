#include "vgate/features.h"

#include <math.h>
#include <string.h>

#include "vgate/numeric.h"

/* --- RR ----------------------------------------------------------------------------- */

void vgate_rr_init(vgate_rr_t *t)
{
    memset(t, 0, sizeof *t);
    t->r_last = -1;
}

static double rr_capped(int32_t a, int32_t b)
{
    double rr = (double)(b - a) / VGATE_FS;
    return rr < VGATE_RR_CAP ? rr : VGATE_RR_CAP;
}

void vgate_rr_next(vgate_rr_t *t, int32_t r, int32_t r_next, double out[5])
{
    const int K = VGATE_RR_HISTORY + 1;
    int32_t i = t->n_beats;
    double rr_post = r_next >= 0 ? rr_capped(r, r_next) : VGATE_RR_CAP;
    double rr_pre = t->r_last >= 0 ? rr_capped(t->r_last, r) : rr_post;
    t->csum[(i + 1) % K] = t->csum[i % K] + rr_pre; /* csum[0] = 0 from init */
    int32_t lo = i + 1 - VGATE_RR_HISTORY;
    if (lo < 0) lo = 0;
    double avg = (t->csum[(i + 1) % K] - t->csum[lo % K]) / (double)(i + 1 - lo);
    out[0] = rr_pre;
    out[1] = rr_post;
    out[2] = avg;
    out[3] = rr_pre / avg;
    out[4] = rr_post / avg;
    t->r_last = r;
    t->n_beats = i + 1;
}

/* --- db4 ------------------------------------------------------------------------------ */

/* pywt/_extensions/c/convolution.c.src, downsampling_convolution, MODE_SYMMETRIC,
 * step 2, N >= F; summation order kept term for term. */
int vgate_dwt_symmetric(const double *x, int N, const double *f, double *out)
{
    const int F = VGATE_WAVELET_LEN;
    int i = 1, o = 0;
    for (; i < F && i < N; i += 2) { /* left boundary overhang */
        double s = 0.0;
        int j = 0;
        for (; j <= i; ++j) s += f[j] * x[i - j];
        while (j < F) {
            for (int k = 0; k < N && j < F; ++j, ++k) s += f[j] * x[k];
            for (int k = 0; k < N && j < F; ++k, ++j) s += f[j] * x[N - 1 - k];
        }
        out[o++] = s;
    }
    for (; i < N; i += 2) { /* centre */
        double s = 0.0;
        for (int j = 0; j < F; ++j) s += x[i - j] * f[j];
        out[o++] = s;
    }
    for (; i < N + F - 1; i += 2) { /* right boundary overhang */
        double s = 0.0;
        int j = 0;
        while (i - j >= N) {
            for (int k = 0; k < N && i - j >= N; ++j, ++k) s += f[i - N - j] * x[N - 1 - k];
            for (int k = 0; k < N && i - j >= N; ++j, ++k) s += f[i - N - j] * x[k];
        }
        for (; j < F; ++j) s += f[j] * x[i - j];
        out[o++] = s;
    }
    return o;
}

static double log_energy(double *c, int n) /* np.log(np.sum(c ** 2) + 1e-9), in place */
{
    for (int k = 0; k < n; ++k) c[k] = c[k] * c[k];
    return log(vgate_pairwise_sum(c, n) + 1e-9);
}

/* --- morphology ------------------------------------------------------------------------ */

void vgate_morphology(vgate_morph_ws_t *ws, const float x[VGATE_SEG_LEN], int32_t p,
                      int32_t n, int32_t r_prev, int32_t r_next, double out[8])
{
    const int32_t x0 = p + VGATE_W0; /* absolute index of x[0] */
#define X(i) ((double)x[(i) - x0])

    /* R: maximum within +/- r_search; S: minimum within s_search after R */
    int32_t a = p - VGATE_R_SEARCH > 0 ? p - VGATE_R_SEARCH : 0;
    int32_t b = p + VGATE_R_SEARCH + 1 < n ? p + VGATE_R_SEARCH + 1 : n;
    int32_t ri = a;
    for (int32_t i = a + 1; i < b; ++i)
        if (X(i) > X(ri)) ri = i;
    int32_t s_end = ri + VGATE_S_SEARCH + 1 < n ? ri + VGATE_S_SEARCH + 1 : n;
    double s_amp = X(ri);
    for (int32_t i = ri + 1; i < s_end; ++i)
        if (X(i) < s_amp) s_amp = X(i);
    out[0] = X(ri);
    out[1] = s_amp;

    /* wavelet segment, truncated at the midpoints to the neighbours, zero-padded */
    int32_t left = p + VGATE_W0, right = p + VGATE_W1;
    if (r_prev >= 0 && (r_prev + p) / 2 > left) left = (r_prev + p) / 2;
    if (r_next >= 0 && (p + r_next) / 2 < right) right = (p + r_next) / 2;
    if (left < 0) left = 0;
    if (right > n - 1) right = n - 1;
    memset(ws->seg, 0, sizeof ws->seg);
    for (int32_t i = left; i <= right; ++i) ws->seg[i - x0] = X(i);
#undef X

    /* 5-level db4 decomposition (pywt.wavedec): D1 goes to out[7], ..., D5 to
     * out[3], then A5 to out[2]; approximations alternate between ws->a and ws->b */
    const double *in = ws->seg;
    int len = VGATE_SEG_LEN;
    for (int level = 1; level <= VGATE_WAVELET_LEVEL; ++level) {
        double *approx = level % 2 ? ws->a : ws->b;
        int m = vgate_dwt_symmetric(in, len, vgate_dec_hi, ws->d);
        vgate_dwt_symmetric(in, len, vgate_dec_lo, approx);
        out[3 + VGATE_WAVELET_LEVEL - level] = log_energy(ws->d, m);
        in = approx;
        len = m;
    }
    memcpy(ws->d, in, sizeof(double) * (size_t)len);
    out[2] = log_energy(ws->d, len);
}
