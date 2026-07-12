/*
 * main.c — PyWinHello Pico firmware entry point
 *
 * Initialization sequence:
 *   1. Init USB (TinyUSB device stack)
 *   2. Init crypto (read board unique ID)
 *   3. Init storage (LittleFS mount/format)
 *   4. Load config + check for stored PIN
 *   5. Init log subsystem
 *   6. Detect WiFi hardware (Pico W auto-detect)
 *   7. Connect WiFi + NTP sync (if Pico W)
 *   8. Init scheduler (if NTP available)
 *   9. Init bootloader (check for pending verify / rollback)
 *   10. Start boot unlock timer (if PIN stored)
 *
 * Main loop:
 *   - tud_task() — TinyUSB device processing
 *   - serial_task() — Serial command processing
 *   - hid_task() — HID periodic work
 *   - wifi_task() — WiFi reconnect + NTP re-sync
 *   - scheduler_task() — Check for scheduled wake
 *   - Boot unlock countdown (one-shot on cold boot)
 *   - Uptime tracking
 */

#include "pywinhello.h"
#include "hid.h"
#include "serial_proto.h"
#include "storage.h"
#include "crypto.h"
#include "log.h"
#include "wifi.h"
#include "scheduler.h"
#include "bootloader.h"

#include "pico/stdlib.h"
#include "pico/unique_id.h"
#include "pico/bootrom.h"
#include "bsp/board_api.h"
#include "tusb.h"

#ifdef PYWINHELLO_HAS_CYW43
#include "pico/cyw43_arch.h"
#endif

#include <stdio.h>
#include <string.h>

/* ── Global application state ─────────────────────────────────────── */

app_state_t g_state;

/* ── Boot unlock state machine ────────────────────────────────────── */

typedef enum {
    BOOT_IDLE,        /* No boot unlock pending */
    BOOT_WAITING,     /* Waiting for boot_wait_sec to expire */
    BOOT_SHIFT_1,     /* First Shift sent, waiting 2s */
    BOOT_SHIFT_2,     /* Second Shift sent, waiting 2s */
    BOOT_TYPING,      /* PIN typed, waiting for result */
    BOOT_RETRY_WAIT,  /* Waiting before retry */
    BOOT_DONE,        /* Complete (success or max retries) */
} boot_state_t;

static boot_state_t _boot_state = BOOT_IDLE;
static uint32_t     _boot_timer_start = 0;
static uint32_t     _boot_step_start = 0;
static uint8_t      _boot_attempt = 0;

static void boot_unlock_start(void) {
    if (!g_state.pin_stored) {
        _boot_state = BOOT_DONE;
        return;
    }

    _boot_state = BOOT_WAITING;
    _boot_timer_start = to_ms_since_boot(get_absolute_time());
    _boot_attempt = 0;
    g_state.boot_unlock_cancelled = false;
    g_state.boot_unlock_done = false;
}

static void boot_unlock_do_attempt(void) {
    _boot_state = BOOT_SHIFT_1;
    _boot_step_start = to_ms_since_boot(get_absolute_time());
    hid_press_shift();
}

static void boot_unlock_task(void) {
    if (_boot_state == BOOT_IDLE || _boot_state == BOOT_DONE) {
        return;
    }

    /* Daemon sent a command — cancel boot unlock */
    if (g_state.boot_unlock_cancelled) {
        _boot_state = BOOT_DONE;
        g_state.boot_unlock_done = true;
        return;
    }

    uint32_t now = to_ms_since_boot(get_absolute_time());

    switch (_boot_state) {
    case BOOT_WAITING: {
        uint32_t wait_ms = g_state.config.boot_wait_sec * 1000U;
        if (now - _boot_timer_start >= wait_ms) {
            boot_unlock_do_attempt();
        }
        break;
    }

    case BOOT_SHIFT_1:
        if (now - _boot_step_start >= 2000) {
            /* Send second Shift to ensure PIN field focused */
            hid_press_shift();
            _boot_state = BOOT_SHIFT_2;
            _boot_step_start = now;
        }
        break;

    case BOOT_SHIFT_2:
        if (now - _boot_step_start >= 2000) {
            /* Type PIN + Enter */
            char pin[PIN_MAX_LEN + 1];
            if (storage_load_pin(pin, sizeof(pin))) {
                hid_type_string(pin);
                sleep_ms(g_state.config.dialog_wait_sec * 1000);
                hid_press_key(KEY_ENTER);
                memset(pin, 0, sizeof(pin));
            }
            _boot_state = BOOT_TYPING;
            _boot_step_start = now;
        }
        break;

    case BOOT_TYPING:
        if (now - _boot_step_start >= 5000) {
            _boot_attempt++;

            if (_boot_attempt < g_state.config.retry_count) {
                /* Retry after interval */
                _boot_state = BOOT_RETRY_WAIT;
                _boot_step_start = now;
            } else {
                /* Max retries reached */
                _boot_state = BOOT_DONE;
                g_state.boot_unlock_done = true;

                uint32_t dur = now - _boot_timer_start;
                log_event(EVENT_BOOT_UNLOCK, RESULT_FAIL_TIMEOUT,
                          (uint16_t)MIN(dur, 0xFFFF), SOURCE_FIRMWARE);
            }
        }
        break;

    case BOOT_RETRY_WAIT:
        if (now - _boot_step_start >=
            (uint32_t)(g_state.config.retry_interval_sec * 1000U)) {
            boot_unlock_do_attempt();
        }
        break;

    default:
        break;
    }
}

/* ── TinyUSB callbacks ────────────────────────────────────────────── */

/* Called when device is mounted (USB enumeration complete) */
void tud_mount_cb(void) {
    /* USB is ready — start boot unlock if cold boot */
}

/* Called when device is unmounted */
void tud_umount_cb(void) {
}

/* Called when USB bus is suspended */
void tud_suspend_cb(bool remote_wakeup_en) {
    (void)remote_wakeup_en;
}

/* Called when USB bus is resumed */
void tud_resume_cb(void) {
}

/* ── Uptime tracking ──────────────────────────────────────────────── */

static uint32_t _last_uptime_check = 0;

static void update_uptime(void) {
    uint32_t now = to_ms_since_boot(get_absolute_time());
    if (now - _last_uptime_check >= 1000) {
        _last_uptime_check = now;
        g_state.uptime_sec++;
    }
}

/* ── Yield to USB during init ─────────────────────────────────────── */

/*
 * USB enumeration requires tud_task() to process host descriptor
 * requests. Call this between init steps so enumeration can complete
 * even if initialization takes a while (e.g., first-boot LittleFS
 * format erases 64 flash sectors with interrupts disabled).
 */
static void usb_yield(void) {
    for (int i = 0; i < 10; i++) {
        tud_task();
        sleep_ms(1);
    }
}

/* ── Main ─────────────────────────────────────────────────────────── */

int main(void) {
    /* Initialize global state */
    memset(&g_state, 0, sizeof(g_state));
    g_state.device = DEVICE_UNKNOWN;

    /* Board-level init (clocks, GPIO) — matches TinyUSB BSP pattern */
    board_init();

    /* Initialize TinyUSB device stack.
     * dcd_init() handles VBUS detect override, USB PHY muxing,
     * and D+ pull-up internally. */
    tud_init(BOARD_TUD_RHPORT);

    /*
     * Wait for USB enumeration with auto-BOOTSEL fallback.
     * If the host doesn't mount us within 8 seconds, reboot into
     * BOOTSEL so the user can reflash without holding the button.
     */
    for (int i = 0; i < 800 && !tud_mounted(); i++) {
        tud_task();
        sleep_ms(10);
    }
    if (!tud_mounted()) {
        reset_usb_boot(0, 0);
        /* Never reached */
    }

    /* ── USB is live — proceed with subsystem init ────────────── */

    bool has_wifi = wifi_detect();
    usb_yield();

    /* Crypto must come before storage (for PIN encryption) */
    crypto_init();
    usb_yield();

    /* Mount filesystem (first boot: formats flash — slow) */
    if (!storage_init()) {
        /* Cannot access flash storage — continue with defaults */
    }
    usb_yield();

    /* Load config from flash */
    storage_load_config();

    /* Initialize log (loads existing log from flash) */
    log_init();

    /* Check if PIN is stored */
    g_state.pin_stored = storage_has_pin();

    usb_yield();

    /* Update device string in config */
    switch (g_state.device) {
    case DEVICE_PICO:     snprintf(g_state.config.device_str, 16, "pico"); break;
    case DEVICE_PICO_W:   snprintf(g_state.config.device_str, 16, "pico_w"); break;
    case DEVICE_PICO_2:   snprintf(g_state.config.device_str, 16, "pico_2"); break;
    case DEVICE_PICO_2_W: snprintf(g_state.config.device_str, 16, "pico_2_w"); break;
    default:              snprintf(g_state.config.device_str, 16, "unknown"); break;
    }

    /* WiFi: connect and sync NTP (Pico W only) */
    if (has_wifi) {
        wifi_connect();
        usb_yield();
        if (wifi_is_connected()) {
            wifi_ntp_sync();
        }
    }

    /* Initialize HID keyboard */
    hid_init();

    /* Initialize serial protocol */
    serial_init();

    /* Initialize bootloader (check for pending verify / rollback) */
    bootloader_init();

    /* Initialize scheduler (requires NTP) */
    scheduler_init();

    /* Start boot unlock sequence (cold boot detected by fresh USB enum) */
    boot_unlock_start();

    /* Log boot event */
    log_event(EVENT_BOOT_UNLOCK, RESULT_SUCCESS, 0, SOURCE_FIRMWARE);

    /* ── Main loop ────────────────────────────────────────────────── */

    while (true) {
        /* TinyUSB device task (must be called frequently) */
        tud_task();

        /* Process serial commands */
        serial_task();

        /* HID periodic work */
        hid_task();

        /* Boot unlock state machine */
        boot_unlock_task();

        /* WiFi maintenance (reconnect, NTP re-sync) */
        wifi_task();

        /* Scheduler (check for wake time) */
        scheduler_task();

        /* Track uptime */
        update_uptime();
    }

    return 0;
}
