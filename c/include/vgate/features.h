#ifndef VGATE_FEATURES_H
#define VGATE_FEATURES_H

/* Per-beat features, a port of src/vgate/features.py (column order FEATURE_NAMES):
 *   0 rr_pre  1 rr_post  2 rr_avg10  3 rr_pre_ratio  4 rr_post_ratio  5 qrs_width
 *   6 r_amp   7 s_amp    8 e_a5  9 e_d5  10 e_d4  11 e_d3  12 e_d2  13 e_d1
 * Arithmetic follows the reference operation by operation (NumPy pairwise sums,
 * PyWavelets' symmetric-mode convolution), so everything except log() is
 * bit-identical; log() may differ from NumPy's by an ulp. */

#include <stdint.h>

#include "vgate/params.h"

#define VGATE_DWT_MAX ((VGATE_SEG_LEN + VGATE_WAVELET_LEN - 1) / 2)

/* RR features in beat order. */
typedef struct {
    int32_t n_beats; /* beats taken so far */
    int32_t r_last;  /* R peak of the last beat taken; -1: none */
    double csum[VGATE_RR_HISTORY + 1]; /* cumulative rr_pre sums (ring), as np.cumsum */
} vgate_rr_t;

void vgate_rr_init(vgate_rr_t *t);

/* Take the next beat (R peak r; r_next: the following R peak, or -1 if there is none
 * or the decision timed out) and write rr_pre, rr_post, rr_avg10 and the two ratios. */
void vgate_rr_next(vgate_rr_t *t, int32_t r, int32_t r_next, double out[5]);

/* Scratch space for vgate_morphology (kept off the stack for small MCU tasks). */
typedef struct {
    double seg[VGATE_SEG_LEN];
    double a[VGATE_DWT_MAX], b[VGATE_DWT_MAX], d[VGATE_DWT_MAX];
} vgate_morph_ws_t;

/* R amplitude, S amplitude and the six db4 band energies (A5, D5..D1) of the beat
 * at R peak p, written to out[0..7].
 *   x:      classifier-filtered signal, x[k] = signal[p + VGATE_W0 + k]
 *   n:      samples in the record (clips the windows at its end); INT32_MAX if open
 *   r_prev: previous R peak or -1; r_next: next R peak or -1
 * Entries of x outside the record are never read. */
void vgate_morphology(vgate_morph_ws_t *ws, const float x[VGATE_SEG_LEN], int32_t p,
                      int32_t n, int32_t r_prev, int32_t r_next, double out[8]);

/* One level of pywt.dwt(x, "db4", mode="symmetric"): writes (N + 7) / 2 coefficients. */
int vgate_dwt_symmetric(const double *x, int N, const double *filter, double *out);

#endif
