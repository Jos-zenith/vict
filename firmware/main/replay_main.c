/* ESP32-S3 replay: MIT-BIH samples in over the native USB port, v1.0 decisions out.
 *
 * Host -> board (scripts/check_c_core.py --serial PORT):
 *   "VGR1", uint32 n (little-endian), then n raw samples (mV) as little-endian float64
 * Board -> host, the lines of c/tools/vgate_replay (B ..., W ..., E ...) and then
 *   T n_samples max_sample_us mean_sample_us max_window_ms
 * where the window time is the processing time summed over each 10 s of input
 * (time spent writing to USB excluded).
 * The pipeline and its output are identical to the laptop build; only the transport
 * differs. Records are replayed as fast as USB delivers them, not in real time. */

#include <stdint.h>
#include <stdio.h>
#include <string.h>

#include "driver/usb_serial_jtag.h"
#include "esp_cpu.h"
#include "freertos/FreeRTOS.h"
#include "sdkconfig.h"
#include "vgate/pipeline.h"

#define CYCLES_PER_US CONFIG_ESP_DEFAULT_CPU_FREQ_MHZ

static vgate_pipeline_t pl; /* ~160 KB in internal RAM; no heap use by the core */
static char line[640];
static uint32_t io_cycles; /* time spent writing to USB, excluded from the timings */

static void put(int n)
{
    uint32_t t0 = esp_cpu_get_cycle_count();
    if (n > (int)sizeof line) n = sizeof line;
    usb_serial_jtag_write_bytes(line, (size_t)n, portMAX_DELAY);
    io_cycles += esp_cpu_get_cycle_count() - t0;
}

static void on_beat(void *ctx, const vgate_beat_t *b)
{
    (void)ctx;
    int n = snprintf(line, sizeof line, "B %ld %ld %.17g %d", (long)b->r, (long)b->decided_at,
                     b->decision, b->is_v);
    for (int j = 0; j < VGATE_N_FEATURES; ++j)
        n += snprintf(line + n, sizeof line - (size_t)n, " %.17g", b->features[j]);
    n += snprintf(line + n, sizeof line - (size_t)n, "\n");
    put(n);
}

static void on_window(void *ctx, const vgate_window_t *w)
{
    (void)ctx;
    put(snprintf(line, sizeof line, "W %ld %d %d %d %ld\n", (long)w->start, w->n_beats, w->n_v,
                 (int)w->state, (long)w->decided_at));
}

static void read_exact(void *dst, size_t n)
{
    uint8_t *p = dst;
    while (n > 0) {
        int k = usb_serial_jtag_read_bytes(p, (uint32_t)n, portMAX_DELAY);
        if (k > 0) {
            p += k;
            n -= (size_t)k;
        }
    }
}

static void wait_for_magic(void)
{
    uint8_t w[4] = {0};
    while (memcmp(w, "VGR1", 4) != 0) {
        memmove(w, w + 1, 3);
        read_exact(&w[3], 1);
    }
}

static void replay_one(void)
{
    uint32_t n;
    uint8_t buf[8 * 64];
    uint32_t max_cycles = 0, window_cycles = 0, max_window = 0;
    uint64_t total = 0;

    wait_for_magic();
    read_exact(&n, sizeof n); /* the S3 is little-endian, as the protocol */
    vgate_pipeline_init(&pl, on_beat, on_window, NULL);
    for (uint32_t i = 0; i < n;) {
        uint32_t k = n - i < 64 ? n - i : 64;
        read_exact(buf, 8 * k);
        for (uint32_t j = 0; j < k; ++j, ++i) {
            double x;
            memcpy(&x, buf + 8 * j, sizeof x);
            io_cycles = 0;
            uint32_t t0 = esp_cpu_get_cycle_count();
            vgate_pipeline_push(&pl, x);
            uint32_t dt = esp_cpu_get_cycle_count() - t0 - io_cycles;
            total += dt;
            if (dt > max_cycles) max_cycles = dt;
            window_cycles += dt;
            if ((i + 1) % VGATE_WINDOW == 0) {
                if (window_cycles > max_window) max_window = window_cycles;
                window_cycles = 0;
            }
        }
    }
    vgate_pipeline_finish(&pl);
    put(snprintf(line, sizeof line, "E %ld %lu %lu %lu\n", (long)pl.n, (unsigned long)pl.n_late,
                 (unsigned long)pl.n_overflow, (unsigned long)pl.pt.n_stale));
    put(snprintf(line, sizeof line, "T %lu %.1f %.2f %.1f\n", (unsigned long)n,
                 (double)max_cycles / CYCLES_PER_US,
                 n ? (double)total / n / CYCLES_PER_US : 0.0,
                 (double)max_window / CYCLES_PER_US / 1000.0));
}

void app_main(void)
{
    usb_serial_jtag_driver_config_t cfg = USB_SERIAL_JTAG_DRIVER_CONFIG_DEFAULT();
    cfg.rx_buffer_size = 4096;
    cfg.tx_buffer_size = 4096;
    ESP_ERROR_CHECK(usb_serial_jtag_driver_install(&cfg));
    for (;;) replay_one();
}
