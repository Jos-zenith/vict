#include "vgate/biquad.h"

#include <string.h>

void vgate_sos_init(vgate_sos_t *f, const float (*sos)[6], int n_sections)
{
    f->n_sections = n_sections;
    memcpy(f->sos, sos, sizeof(float) * 6 * (size_t)n_sections);
    memset(f->z, 0, sizeof f->z);
}

/* zi from scipy.signal.sosfilt_zi, scaled by the first sample (steady-state start). */
void vgate_sos_set_state(vgate_sos_t *f, const float (*zi)[2], float x0)
{
    for (int s = 0; s < f->n_sections; ++s) {
        f->z[s][0] = zi[s][0] * x0;
        f->z[s][1] = zi[s][1] * x0;
    }
}

float vgate_sos_step(vgate_sos_t *f, float x)
{
    for (int s = 0; s < f->n_sections; ++s) {
        const float *c = f->sos[s];
        float y = c[0] * x + f->z[s][0];
        f->z[s][0] = c[1] * x - c[4] * y + f->z[s][1];
        f->z[s][1] = c[2] * x - c[5] * y;
        x = y;
    }
    return x;
}
