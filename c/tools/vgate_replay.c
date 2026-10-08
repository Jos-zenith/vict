/* Replay a record through the C core on the laptop.
 *
 *   vgate_replay [--detector] samples.f64 > out.txt
 *
 * samples.f64: raw samples (mV) as little-endian float64. Output, one line each,
 * with doubles at 17 significant digits (exact round trip):
 *   D r width                                    detector only (--detector)
 *   B r decided_at decision is_v f0 ... f13      classified beat
 *   W start n_beats n_v state decided_at         decided window (state: vgate_state_t)
 *   E n_samples n_late n_overflow n_stale        end of record
 * The ESP32 replay firmware prints the same lines (scripts/check_c_core.py reads both). */

#include <stdio.h>
#include <string.h>

#include "vgate/pipeline.h"

static vgate_pipeline_t pl; /* ~160 KB: static, never on the stack */

static void on_beat(void *ctx, const vgate_beat_t *b)
{
    FILE *out = ctx;
    fprintf(out, "B %ld %ld %.17g %d", (long)b->r, (long)b->decided_at, b->decision, b->is_v);
    for (int j = 0; j < VGATE_N_FEATURES; ++j) fprintf(out, " %.17g", b->features[j]);
    fputc('\n', out);
}

static void on_window(void *ctx, const vgate_window_t *w)
{
    fprintf(ctx, "W %ld %d %d %d %ld\n", (long)w->start, w->n_beats, w->n_v, (int)w->state,
            (long)w->decided_at);
}

int main(int argc, char **argv)
{
    int detector_only = argc > 2 && strcmp(argv[1], "--detector") == 0;
    const char *path = argv[argc - 1];
    if (argc < 2) {
        fprintf(stderr, "usage: vgate_replay [--detector] samples.f64\n");
        return 2;
    }
    FILE *in = fopen(path, "rb");
    if (!in) {
        perror(path);
        return 2;
    }
    vgate_pipeline_init(&pl, on_beat, on_window, stdout);
    double buf[4096];
    size_t got;
    while ((got = fread(buf, sizeof(double), 4096, in)) > 0) {
        for (size_t i = 0; i < got; ++i) {
            if (detector_only) {
                int k = vgate_pt_push(&pl.pt, buf[i]);
                for (int j = 0; j < k; ++j)
                    printf("D %ld %.17g\n", (long)pl.pt.out_r[j], pl.pt.out_width[j]);
            } else {
                vgate_pipeline_push(&pl, buf[i]);
            }
        }
    }
    fclose(in);
    if (detector_only) {
        printf("E %ld 0 0 %lu\n", (long)pl.pt.n, (unsigned long)pl.pt.n_stale);
    } else {
        vgate_pipeline_finish(&pl);
        printf("E %ld %lu %lu %lu\n", (long)pl.n, (unsigned long)pl.n_late,
               (unsigned long)pl.n_overflow, (unsigned long)pl.pt.n_stale);
    }
    return 0;
}
