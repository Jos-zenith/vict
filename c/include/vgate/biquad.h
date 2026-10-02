#ifndef VGATE_BIQUAD_H
#define VGATE_BIQUAD_H

/* Cascade of second-order sections, float32, direct form II transposed.
 * Coefficient layout matches scipy's sos: b0 b1 b2 a0 a1 a2 per section (a0 = 1). */

#define VGATE_MAX_SECTIONS 8

typedef struct {
    int n_sections;
    float sos[VGATE_MAX_SECTIONS][6];
    float z[VGATE_MAX_SECTIONS][2];
} vgate_sos_t;

void vgate_sos_init(vgate_sos_t *f, const float (*sos)[6], int n_sections);
void vgate_sos_set_state(vgate_sos_t *f, const float (*zi)[2], float x0);
float vgate_sos_step(vgate_sos_t *f, float x);

#endif
