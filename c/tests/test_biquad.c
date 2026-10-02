#include <math.h>
#include <stdio.h>

#include "vgate/biquad.h"

/* Pass-through section: output must equal input. Real vectors come from the
 * Python reference once the pipeline is frozen. */
int main(void)
{
    const float identity[1][6] = {{1.0f, 0.0f, 0.0f, 1.0f, 0.0f, 0.0f}};
    vgate_sos_t f;
    vgate_sos_init(&f, identity, 1);
    for (int i = 0; i < 10; ++i) {
        float x = (float)i * 0.5f;
        if (fabsf(vgate_sos_step(&f, x) - x) > 1e-6f) {
            printf("FAIL at %d\n", i);
            return 1;
        }
    }
    printf("OK\n");
    return 0;
}
