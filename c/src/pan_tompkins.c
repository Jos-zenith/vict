#include "vgate/pan_tompkins.h"

#include <math.h>
#include <string.h>

#include "vgate/numeric.h"

#define RING(buf, i) ((buf)[(i) % VGATE_PT_RING])

/* --- small helpers ------------------------------------------------------------ */

static void rr_append(vgate_rr8_t *q, int32_t v)
{
    q->v[q->head] = v;
    q->head = (q->head + 1) % VGATE_PT_RR_N;
    if (q->n < VGATE_PT_RR_N) ++q->n;
}

static double rr_mean(const vgate_rr8_t *q) /* sum(deque) / len(deque); q->n > 0 */
{
    int32_t s = 0;
    for (int k = 0; k < q->n; ++k) s += q->v[k];
    return (double)s / (double)q->n;
}

/* Absolute start of the reference's history while stepping sample i. */
static int32_t history_start(int32_t i)
{
    int32_t h0 = (i / VGATE_PT_CHUNK) * VGATE_PT_CHUNK - VGATE_PT_N_HIST;
    return i < VGATE_PT_CHUNK || h0 < 0 ? 0 : h0;
}

/* --- thresholds ----------------------------------------------------------------- */

static double thr1(const vgate_pt_t *d)
{
    double t = d->npki + 0.25 * (d->spki - d->npki);
    return d->irregular ? 0.5 * t : t;
}

static double missed_limit(const vgate_pt_t *d)
{
    const vgate_rr8_t *rr = d->rr2.n ? &d->rr2 : &d->rr1;
    return 1.66 * (rr->n ? rr_mean(rr) : (double)VGATE_FS);
}

static void learn(vgate_pt_t *d, int32_t end)
{
    int32_t lo = end - VGATE_PT_N_LEARN;
    if (lo < d->h0) lo = d->h0;
    int n = (int)(end - lo);
    double mx = RING(d->h_mwi, lo);
    for (int k = 0; k < n; ++k) {
        d->scratch[k] = RING(d->h_mwi, lo + k);
        if (d->scratch[k] > mx) mx = d->scratch[k];
    }
    d->spki = mx / 3;
    d->npki = vgate_pairwise_sum(d->scratch, n) / n / 2;
}

/* --- history reads, clipped at h0 like _hist ------------------------------------ */

static double max_abs(const double *buf, int32_t lo, int32_t p)
{
    double m = 0.0;
    for (int32_t i = lo; i <= p; ++i) {
        double v = fabs(RING(buf, i));
        if (v > m) m = v;
    }
    return m;
}

/* QRS width (s): integrator rising edge from 10 % to 90 % of the peak, / 0.8. */
static double integrator_width(const vgate_pt_t *d, int32_t p)
{
    int32_t lo = p - 2 * VGATE_PT_N_MWI;
    if (lo < d->h0) lo = d->h0;
    int32_t len = p - lo + 1;
    if (len < 2) return 0.0;
    double v = RING(d->h_mwi, p);
    if (v <= 0) return 0.0;
    double v10 = 0.1 * v, v90 = 0.9 * v;
    int32_t t10 = 0, t90;
    for (int32_t k = len - 1; k >= 0; --k) {
        if (RING(d->h_mwi, lo + k) < v10) {
            t10 = k + 1;
            break;
        }
    }
    t90 = t10;
    for (int32_t k = t10; k < len; ++k) {
        if (RING(d->h_mwi, lo + k) >= v90) {
            t90 = k;
            break;
        }
    }
    return (double)(t90 - t10) / 0.8 / VGATE_FS;
}

/* --- events --------------------------------------------------------------------- */

static void qrs(vgate_pt_t *d, int32_t p, double v, int searchback)
{
    double a = searchback ? 0.25 : 0.125;
    d->spki += a * (v - d->spki);
    int32_t lo = p - VGATE_PT_N_MWI - VGATE_PT_BP_DELAY - 5;
    int32_t start = lo > d->h0 ? lo : d->h0;
    int32_t r = p;
    if (p >= start) {
        int32_t best = start;
        double m = fabs(RING(d->h_bp, start));
        for (int32_t i = start + 1; i <= p; ++i) {
            double av = fabs(RING(d->h_bp, i));
            if (av > m) {
                m = av;
                best = i;
            }
        }
        r = best - VGATE_PT_BP_DELAY;
    }
    d->last_slope = max_abs(d->h_der, start, p);
    if (d->last_qrs >= 0) {
        int32_t rr = p - d->last_qrs;
        rr_append(&d->rr1, rr);
        double avg2 = d->rr2.n ? rr_mean(&d->rr2) : (double)rr;
        int ok = 0.92 * avg2 <= rr && rr <= 1.16 * avg2;
        if (ok || !d->rr2.n) rr_append(&d->rr2, rr);
        d->irregular = !ok;
    }
    d->last_qrs = p;
    d->cand_p = -1;
    if (r < 0) r = 0;
    if (p < d->h0) ++d->n_stale;
    if (d->n_out < VGATE_PT_MAX_OUT) {
        d->out_r[d->n_out] = r;
        d->out_width[d->n_out] = p < d->h0 ? 0.0 : integrator_width(d, p);
        ++d->n_out;
    }
}

static void peak(vgate_pt_t *d, int32_t p, double v)
{
    int32_t last = d->last_qrs;
    if (last >= 0 && p - last < VGATE_PT_REFRACTORY) return;
    if (last >= 0 && p - last < VGATE_PT_T_WAVE) {
        int32_t lo = p - VGATE_PT_N_MWI - VGATE_PT_BP_DELAY - 5;
        double slope = max_abs(d->h_der, lo > d->h0 ? lo : d->h0, p);
        if (slope < 0.5 * d->last_slope) {
            d->npki += 0.125 * (v - d->npki);
            return;
        }
    }
    if (v > thr1(d)) {
        qrs(d, p, v, 0);
    } else {
        d->npki += 0.125 * (v - d->npki);
        if (d->cand_p < 0 || v > d->cand_v) {
            d->cand_p = p;
            d->cand_v = v;
        }
    }
}

static void step(vgate_pt_t *d, int32_t i)
{
    double v = RING(d->h_mwi, i);
    d->h0 = history_start(i);
    if (v > d->pk_val && d->armed) {
        d->pk_val = v;
        d->pk_idx = i;
    } else if (d->pk_val > 0 && v < 0.5 * d->pk_val) {
        peak(d, d->pk_idx, d->pk_val);
        d->pk_val = 0.0;
        d->armed = 0;
    }
    if (!d->armed && v > d->prev) {
        d->armed = 1;
        d->pk_val = v;
        d->pk_idx = i;
    }
    d->prev = v;

    int32_t ref = d->last_qrs >= 0 ? d->last_qrs : VGATE_PT_N_LEARN;
    int32_t gap = i - ref;
    double limit = missed_limit(d);
    if (gap > limit && d->cand_p >= 0 && d->cand_v > 0.5 * thr1(d)) {
        qrs(d, d->cand_p, d->cand_v, 1);
    } else if (gap > 2 * limit && i - d->last_relearn > VGATE_PT_N_LEARN) {
        learn(d, i + 1);
        d->last_relearn = i;
    }
}

/* --- streaming interface ---------------------------------------------------------- */

void vgate_pt_init(vgate_pt_t *d)
{
    memset(d, 0, sizeof *d);
    vgate_sosd_init(&d->bp, vgate_pt_sos, VGATE_PT_N_SECTIONS);
    d->learning = 1;
    d->armed = 1;
    d->last_qrs = -1;
    d->cand_p = -1;
}

int vgate_pt_push(vgate_pt_t *d, double x)
{
    int32_t i = d->n;
    d->n_out = 0;
    if (i == 0) vgate_sosd_set_state(&d->bp, vgate_pt_zi, x);

    /* band-pass, derivative (FIR), squaring, moving-window integrator (FIR) */
    double bp = vgate_sosd_step(&d->bp, x);
    d->der_x[i % VGATE_PT_N_DER] = bp;
    double der = 0.0;
    for (int k = VGATE_PT_N_DER - 1; k >= 0; --k) /* oldest first, as np.convolve */
        der += i - k >= 0 ? d->der_x[(i - k) % VGATE_PT_N_DER] * vgate_pt_der[k] : 0.0;
    d->mwi_x[i % VGATE_PT_N_MWI] = der * der;
    double mwi = 0.0;
    for (int k = VGATE_PT_N_MWI - 1; k >= 0; --k)
        mwi += i - k >= 0 ? d->mwi_x[(i - k) % VGATE_PT_N_MWI] * vgate_pt_mwi_b : 0.0;

    RING(d->h_bp, i) = bp;
    RING(d->h_der, i) = der;
    RING(d->h_mwi, i) = mwi;
    d->n = i + 1;

    if (d->learning) {
        if (d->n < VGATE_PT_N_LEARN) return 0;
        d->learning = 0;
        d->h0 = 0;
        learn(d, VGATE_PT_N_LEARN);
        d->last_relearn = VGATE_PT_N_LEARN;
        for (int32_t k = 0; k < d->n; ++k) step(d, k); /* replay the learning phase */
    } else {
        step(d, i);
    }
    return d->n_out;
}

int32_t vgate_pt_frontier(const vgate_pt_t *d)
{
    /* A later QRS has its integrator peak >= last_qrs + refractory, and its R peak
     * at most N_MWI + 5 + 2 * BP_DELAY samples before that peak. */
    if (d->last_qrs < 0) return 0;
    int32_t f = d->last_qrs + VGATE_PT_REFRACTORY - (VGATE_PT_N_MWI + 5 + 2 * VGATE_PT_BP_DELAY);
    return f > 0 ? f : 0;
}
