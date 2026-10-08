#ifndef VGATE_PIPELINE_H
#define VGATE_PIPELINE_H

/* Streaming v1.0 pipeline, one raw sample (mV, 360 Hz) at a time:
 *
 *   sample -> classifier band-pass (float32) -------------------------.
 *          -> Pan-Tompkins -> R peak + QRS width -> pending beats -> features -> SVM
 *                                                                   -> 10 s window state
 *
 * Offline, the Python reference sees the whole record; here a beat is classified
 * as soon as nothing still to come can change its features:
 *   - its successor is known and the detector's frontier (vgate_pt_frontier) has
 *     passed it, so no R peak can still appear between the two, and the signal
 *     up to VGATE_W1 after the beat has arrived; or
 *   - VGATE_RR_CAP_SAMPLES + VGATE_TIMEOUT_SAMPLES after the R peak (2 s RR cap +
 *     2 s decision timeout), using whatever successor is known by then.
 * A window is decided once all its beats are classified and the frontier has
 * passed its end, or the same timeout after its end. A detection that arrives
 * after a decision it would have changed is counted in n_late; on the reference
 * data this must stay 0 for the output to equal Python's.
 *
 * No dynamic allocation: everything lives in vgate_pipeline_t (about 160 KB),
 * which the caller should allocate statically. */

#include <stdint.h>

#include "vgate/biquad.h"
#include "vgate/features.h"
#include "vgate/pan_tompkins.h"
#include "vgate/params.h"

#define VGATE_X_RING 4096    /* classifier-filtered samples kept */
#define VGATE_MAX_PENDING 64 /* detected beats awaiting classification */

typedef enum {
    VGATE_INSUFFICIENT = 0, /* fewer than VGATE_MIN_BEATS beats */
    VGATE_V_SUSPECTED = 1,  /* at least one beat called V */
    VGATE_NO_V = 2
} vgate_state_t;

typedef struct {
    int32_t r; /* R peak, sample index */
    double features[VGATE_N_FEATURES];
    double decision; /* SVM decision value */
    int is_v;        /* decision > VGATE_THRESHOLD */
    int32_t decided_at; /* index of the last sample seen when classified */
} vgate_beat_t;

typedef struct {
    int32_t start; /* first sample of the window */
    int n_beats, n_v;
    vgate_state_t state;
    int32_t decided_at;
} vgate_window_t;

typedef void (*vgate_beat_cb)(void *ctx, const vgate_beat_t *beat);
typedef void (*vgate_window_cb)(void *ctx, const vgate_window_t *window);

typedef struct {
    vgate_pt_t pt;
    vgate_sos_t bp;
    float x[VGATE_X_RING];
    int32_t n; /* samples consumed */

    int n_pend; /* pending beats, sorted by R peak */
    int32_t pend_r[VGATE_MAX_PENDING];
    double pend_width[VGATE_MAX_PENDING];

    vgate_rr_t rr;
    vgate_morph_ws_t ws;
    float seg[VGATE_SEG_LEN];
    int32_t r_prev;  /* last classified R peak; -1: none */
    int32_t r_bound; /* a detection below this would have changed a decision */

    int32_t win; /* index of the next window to decide */
    int win_beats, win_v;

    uint32_t n_late;     /* detections that arrived after a decision they affect */
    uint32_t n_overflow; /* beats classified early because the pending queue was full */

    vgate_beat_cb on_beat;
    vgate_window_cb on_window;
    void *ctx;
} vgate_pipeline_t;

void vgate_pipeline_init(vgate_pipeline_t *p, vgate_beat_cb on_beat, vgate_window_cb on_window,
                         void *ctx);

/* Feed one raw sample (mV). Callbacks fire from inside this call. */
void vgate_pipeline_push(vgate_pipeline_t *p, double x);

/* End of the record: classify all pending beats and decide every full window. */
void vgate_pipeline_finish(vgate_pipeline_t *p);

#endif
