#ifndef VGATE_PAN_TOMPKINS_H
#define VGATE_PAN_TOMPKINS_H

/* Streaming Pan-Tompkins QRS detector: a line-for-line port of
 * src/vgate/detectors/pan_tompkins.py (see its docstring for the decision logic).
 *
 * The front end runs in float64 like the reference. Its FIR stages (derivative,
 * integrator) cannot be bit-identical to SciPy, whose lfilter goes through
 * np.convolve and BLAS ddot, so integrator values agree to about one ulp. The
 * detections and QRS widths are discrete and are checked for exact equality.
 *
 * History: the reference trims its look-back history once per pushed chunk
 * (detect_with_widths pushes VGATE_PT_CHUNK samples), so while stepping sample i
 * it can read back to h0(i) = max(0, CHUNK * floor(i / CHUNK) - N_HIST). Reads are
 * clipped at h0(i) exactly as there, which needs a ring of CHUNK + N_HIST samples.
 *
 * No dynamic allocation: all state lives in vgate_pt_t (about 115 KB). */

#include <stdint.h>

#include "vgate/biquad.h"
#include "vgate/params.h"

#define VGATE_PT_RING (VGATE_PT_CHUNK + VGATE_PT_N_HIST)
#define VGATE_PT_RR_N 8
#define VGATE_PT_MAX_OUT 16 /* detections per push; the learning replay is the worst case */

typedef struct {
    int32_t v[VGATE_PT_RR_N];
    int n, head;
} vgate_rr8_t;

typedef struct {
    vgate_sosd_t bp;
    double der_x[VGATE_PT_N_DER]; /* last band-pass samples (ring) */
    double mwi_x[VGATE_PT_N_MWI]; /* last squared derivatives (ring) */
    double h_bp[VGATE_PT_RING], h_der[VGATE_PT_RING], h_mwi[VGATE_PT_RING];
    double scratch[VGATE_PT_N_LEARN];
    int32_t n; /* samples consumed */
    int learning;
    double spki, npki;
    double pk_val;
    int32_t pk_idx;
    int armed;
    double prev;
    int32_t last_qrs; /* integrator peak of the last QRS; -1: none yet */
    double last_slope;
    int32_t last_relearn;
    vgate_rr8_t rr1, rr2;
    int irregular;
    int32_t cand_p; /* best noise peak for search-back; -1: none */
    double cand_v;
    int32_t h0; /* history start while stepping the current sample */
    uint32_t n_stale; /* QRS whose integrator peak had left the history (reference undefined) */
    int n_out;
    int32_t out_r[VGATE_PT_MAX_OUT];
    double out_width[VGATE_PT_MAX_OUT];
} vgate_pt_t;

void vgate_pt_init(vgate_pt_t *d);

/* Feed one raw sample (mV). Returns the number of R peaks detected during this
 * call; they are in d->out_r (sample index) and d->out_width (integrator QRS width,
 * seconds) until the next call. */
int vgate_pt_push(vgate_pt_t *d, double x);

/* Every R peak emitted after this point has an index >= the returned value. */
int32_t vgate_pt_frontier(const vgate_pt_t *d);

#endif
