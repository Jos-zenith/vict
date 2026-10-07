#include <math.h>
#include <stdio.h>

#include "vgate/biquad.h"
#include "vectors/bandpass_vectors.h"

/* The C classifier band-pass matches dsp.filters.bandpass on synthetic signals and
 * MIT-BIH 119 (vectors from scripts/export_c_vectors.py). */
int main(void)
{
    int failed = 0;
    for (int s = 0; s < BP_N_SETS; ++s) {
        vgate_sos_t f;
        float max_err = 0.0f;
        vgate_sos_init(&f, BP_SOS, BP_N_SECTIONS);
        vgate_sos_set_state(&f, BP_ZI, BP_X[s][0]);
        for (int i = 0; i < BP_N; ++i) {
            float err = fabsf(vgate_sos_step(&f, BP_X[s][i]) - BP_Y[s][i]);
            if (err > max_err) max_err = err;
        }
        printf("%-12s max |C - Python| = %.3g\n", BP_NAMES[s], max_err);
        if (max_err > 1e-4f) failed = 1;
    }
    printf(failed ? "FAIL (> 1e-4)\n" : "OK\n");
    return failed;
}
