#include <math.h>
#include <stdio.h>

#include "vectors/pipeline_vectors.h"
#include "vgate/pipeline.h"

/* The streaming C pipeline reproduces vgate.reference on two 60 s excerpts (vectors
 * from scripts/export_c_vectors.py): the detector's R peaks and QRS widths exactly,
 * every feature within 1e-12 relative (bit-identical except possibly log()), the
 * decision values within 1e-12, and the V calls and window states exactly. A flat
 * line must give no beats and only "insufficient" windows. Whole records are
 * checked by scripts/check_c_core.py. */

#define MAX_OUT 256

typedef struct {
    int n_beats, n_windows;
    vgate_beat_t beats[MAX_OUT];
    vgate_window_t windows[MAX_OUT];
} capture_t;

static vgate_pipeline_t pl;
static capture_t cap;

static void on_beat(void *ctx, const vgate_beat_t *b)
{
    capture_t *c = ctx;
    if (c->n_beats < MAX_OUT) c->beats[c->n_beats] = *b;
    ++c->n_beats;
}

static void on_window(void *ctx, const vgate_window_t *w)
{
    capture_t *c = ctx;
    if (c->n_windows < MAX_OUT) c->windows[c->n_windows] = *w;
    ++c->n_windows;
}

static int check_detector(int s)
{
    int n = 0, bad = 0;
    vgate_pt_init(&pl.pt);
    for (int i = 0; i < PV_N; ++i) {
        int k = vgate_pt_push(&pl.pt, PV_X[s][i] / PV_GAIN);
        for (int j = 0; j < k; ++j, ++n) {
            if (n >= PV_N_BEATS[s] || pl.pt.out_r[j] != PV_R[s][n] ||
                pl.pt.out_width[j] != PV_WIDTH[s][n])
                bad = 1;
        }
    }
    if (n != PV_N_BEATS[s]) bad = 1;
    printf("%-11s detector  %3d R peaks (Python %3d)  %s\n", PV_NAMES[s], n, PV_N_BEATS[s],
           bad ? "FAIL" : "exact");
    return bad;
}

static int check_pipeline(int s)
{
    int bad = 0, identical = 0;
    double max_rel = 0.0, max_dec = 0.0;
    cap.n_beats = cap.n_windows = 0;
    vgate_pipeline_init(&pl, on_beat, on_window, &cap);
    for (int i = 0; i < PV_N; ++i) vgate_pipeline_push(&pl, PV_X[s][i] / PV_GAIN);
    vgate_pipeline_finish(&pl);

    if (cap.n_beats != PV_N_BEATS[s] || cap.n_windows != PV_N_WINDOWS[s]) {
        printf("%-11s pipeline  %d beats / %d windows, Python %d / %d  FAIL\n", PV_NAMES[s],
               cap.n_beats, cap.n_windows, PV_N_BEATS[s], PV_N_WINDOWS[s]);
        return 1;
    }
    for (int b = 0; b < cap.n_beats; ++b) {
        const vgate_beat_t *o = &cap.beats[b];
        if (o->r != PV_R[s][b]) bad = 1;
        for (int j = 0; j < VGATE_N_FEATURES; ++j) {
            double want = PV_FEATURES[s][b][j];
            double rel = fabs(o->features[j] - want) / (fabs(want) > 1.0 ? fabs(want) : 1.0);
            if (rel > max_rel) max_rel = rel;
            identical += o->features[j] == want;
        }
        double dd = fabs(o->decision - PV_DECISION[s][b]);
        if (dd > max_dec) max_dec = dd;
        if (o->is_v != (PV_DECISION[s][b] > VGATE_THRESHOLD)) bad = 1;
    }
    for (int w = 0; w < cap.n_windows; ++w)
        if ((int)cap.windows[w].state != PV_STATE[s][w]) bad = 1;
    if (max_rel > 1e-12 || max_dec > 1e-12 || pl.n_late || pl.n_overflow) bad = 1;
    printf("%-11s pipeline  %3d beats, %d/%d features bit-identical, max rel diff %.2g, "
           "max decision diff %.2g, %d windows  %s\n",
           PV_NAMES[s], cap.n_beats, identical, cap.n_beats * VGATE_N_FEATURES, max_rel, max_dec,
           cap.n_windows, bad ? "FAIL" : "OK");
    return bad;
}

static int check_flat_line(void)
{
    const int n = 30 * VGATE_FS;
    cap.n_beats = cap.n_windows = 0;
    vgate_pipeline_init(&pl, on_beat, on_window, &cap);
    for (int i = 0; i < n; ++i) vgate_pipeline_push(&pl, 0.25);
    vgate_pipeline_finish(&pl);
    int bad = cap.n_beats != 0 || cap.n_windows != n / VGATE_WINDOW - VGATE_SKIP_FIRST_WINDOW;
    for (int w = 0; w < cap.n_windows && w < MAX_OUT; ++w)
        if (cap.windows[w].state != VGATE_INSUFFICIENT) bad = 1;
    printf("flat line   pipeline  %d beats, %d windows insufficient  %s\n", cap.n_beats,
           cap.n_windows, bad ? "FAIL" : "OK");
    return bad;
}

int main(void)
{
    int failed = 0;
    for (int s = 0; s < PV_N_SETS; ++s) {
        failed |= check_detector(s);
        failed |= check_pipeline(s);
    }
    failed |= check_flat_line();
    printf(failed ? "FAIL\n" : "OK\n");
    return failed;
}
