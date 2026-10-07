#include <math.h>
#include <stdio.h>

#include "vgate/biquad.h"
#include "vectors/bandpass_119.h"

/* Pre-freeze check: the C classifier band-pass matches dsp.filters.bandpass on
 * 10 s of MIT-BIH 119 (vectors from scripts/export_c_vectors.py). */
int main(void)
{
    vgate_sos_t f;
    float max_err = 0.0f;
    vgate_sos_init(&f, BP_SOS, BP_N_SECTIONS);
    vgate_sos_set_state(&f, BP_ZI, BP_X[0]);
    for (int i = 0; i < BP_N; ++i) {
        float err = fabsf(vgate_sos_step(&f, BP_X[i]) - BP_Y[i]);
        if (err > max_err) max_err = err;
    }
    printf("band-pass max |C - Python| = %.3g mV over %d samples\n", max_err, BP_N);
    if (max_err > 1e-4f) {
        printf("FAIL (> 1e-4)\n");
        return 1;
    }
    printf("OK\n");
    return 0;
}
