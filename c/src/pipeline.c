#include "vgate/pipeline.h"

#include <string.h>

#include "vgate/svm.h"

#define DEADLINE (VGATE_RR_CAP_SAMPLES + VGATE_TIMEOUT_SAMPLES)
#define SPAN_AFTER (VGATE_W1 > VGATE_R_SEARCH + VGATE_S_SEARCH ? VGATE_W1 : VGATE_R_SEARCH + VGATE_S_SEARCH)

void vgate_pipeline_init(vgate_pipeline_t *p, vgate_beat_cb on_beat, vgate_window_cb on_window,
                         void *ctx)
{
    memset(p, 0, sizeof *p);
    vgate_pt_init(&p->pt);
    vgate_sos_init(&p->bp, vgate_bp_sos, VGATE_BP_N_SECTIONS);
    vgate_rr_init(&p->rr);
    p->r_prev = -1;
    p->r_bound = -1;
    p->on_beat = on_beat;
    p->on_window = on_window;
    p->ctx = ctx;
}

/* --- windows ------------------------------------------------------------------------ */

static void decide_window(vgate_pipeline_t *p)
{
    if (p->win > 0 || !VGATE_SKIP_FIRST_WINDOW) {
        vgate_window_t w;
        w.start = p->win * VGATE_WINDOW;
        w.n_beats = p->win_beats;
        w.n_v = p->win_v;
        w.state = w.n_beats < VGATE_MIN_BEATS ? VGATE_INSUFFICIENT
                  : w.n_v > 0                 ? VGATE_V_SUSPECTED
                                              : VGATE_NO_V;
        w.decided_at = p->n - 1;
        if (p->on_window) p->on_window(p->ctx, &w);
    }
    ++p->win;
    p->win_beats = p->win_v = 0;
}

/* --- beats ----------------------------------------------------------------------------- */

/* Classify the oldest pending beat. r_next: its successor, or -1 (none / timed out);
 * n: record length if known, else INT32_MAX. */
static void classify_oldest(vgate_pipeline_t *p, int32_t r_next, int32_t n)
{
    vgate_beat_t b;
    int32_t r = p->pend_r[0];
    int32_t x0 = r + VGATE_W0;

    vgate_rr_next(&p->rr, r, r_next, b.features);
    b.features[5] = p->pend_width[0];
    for (int k = 0; k < VGATE_SEG_LEN; ++k) {
        int32_t i = x0 + k;
        p->seg[k] = i >= 0 && i < p->n ? p->x[i % VGATE_X_RING] : 0.0f;
    }
    vgate_morphology(&p->ws, p->seg, r, n, p->r_prev, r_next, b.features + 6);
    b.r = r;
    b.decision = vgate_svm_decision(b.features);
    b.is_v = b.decision > VGATE_THRESHOLD;
    b.decided_at = p->n - 1;
    if (p->on_beat) p->on_beat(p->ctx, &b);

    int32_t w = r / VGATE_WINDOW;
    while (p->win < w) decide_window(p); /* every beat before r is classified */
    if (w == p->win) {
        ++p->win_beats;
        p->win_v += b.is_v;
    }

    p->r_prev = r;
    p->r_bound = r_next >= 0 ? r_next : r + VGATE_RR_CAP_SAMPLES;
    --p->n_pend;
    memmove(p->pend_r, p->pend_r + 1, sizeof(int32_t) * (size_t)p->n_pend);
    memmove(p->pend_width, p->pend_width + 1, sizeof(double) * (size_t)p->n_pend);
}

static void add_detection(vgate_pipeline_t *p, int32_t r, double width)
{
    if (r <= p->r_prev || r + VGATE_W0 < p->n - VGATE_X_RING) {
        ++p->n_late; /* before a classified beat, or its signal is gone: dropped */
        return;
    }
    if (r < p->r_bound || r < p->win * VGATE_WINDOW) ++p->n_late; /* kept, but late */

    int k = 0;
    while (k < p->n_pend && p->pend_r[k] < r) ++k;
    if (k < p->n_pend && p->pend_r[k] == r) { /* same R peak again: the later width wins */
        p->pend_width[k] = width;
        return;
    }
    if (p->n_pend == VGATE_MAX_PENDING) {
        ++p->n_overflow;
        classify_oldest(p, p->pend_r[1], INT32_MAX);
        add_detection(p, r, width);
        return;
    }
    memmove(p->pend_r + k + 1, p->pend_r + k, sizeof(int32_t) * (size_t)(p->n_pend - k));
    memmove(p->pend_width + k + 1, p->pend_width + k, sizeof(double) * (size_t)(p->n_pend - k));
    p->pend_r[k] = r;
    p->pend_width[k] = width;
    ++p->n_pend;
}

/* Classify every pending beat that nothing still to come can change. */
static void classify_ready(vgate_pipeline_t *p)
{
    int32_t t = p->n - 1;
    int32_t frontier = vgate_pt_frontier(&p->pt);
    while (p->n_pend > 0) {
        int32_t r = p->pend_r[0];
        if (t < r + SPAN_AFTER) break;
        if (p->n_pend > 1 && frontier >= p->pend_r[1]) {
            classify_oldest(p, p->pend_r[1], INT32_MAX);
        } else if (t >= r + DEADLINE) {
            classify_oldest(p, p->n_pend > 1 ? p->pend_r[1] : -1, INT32_MAX);
        } else {
            break;
        }
    }
}

static void decide_ready_windows(vgate_pipeline_t *p)
{
    int32_t t = p->n - 1;
    int32_t frontier = vgate_pt_frontier(&p->pt);
    for (;;) {
        int32_t end = (p->win + 1) * VGATE_WINDOW;
        if (t < end - 1) return;
        if (p->n_pend > 0 && p->pend_r[0] < end) return;
        if (frontier < end && t < end + DEADLINE) return;
        decide_window(p);
    }
}

/* --- streaming interface -------------------------------------------------------------- */

void vgate_pipeline_push(vgate_pipeline_t *p, double x)
{
    float xf = (float)x;
    if (p->n == 0) vgate_sos_set_state(&p->bp, vgate_bp_zi, xf);
    p->x[p->n % VGATE_X_RING] = vgate_sos_step(&p->bp, xf);
    ++p->n;

    int k = vgate_pt_push(&p->pt, x);
    for (int j = 0; j < k; ++j) add_detection(p, p->pt.out_r[j], p->pt.out_width[j]);
    classify_ready(p);
    decide_ready_windows(p);
}

void vgate_pipeline_finish(vgate_pipeline_t *p)
{
    while (p->n_pend > 0) classify_oldest(p, p->n_pend > 1 ? p->pend_r[1] : -1, p->n);
    while ((p->win + 1) * VGATE_WINDOW <= p->n) decide_window(p);
}
