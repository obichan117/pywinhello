/*
 * scheduler.c — Schedule parsing and USB remote wakeup
 *
 * Uses NTP time + config schedule to wake the host PC at a
 * specific time on specific days. Falls back to blind-type
 * if the daemon doesn't respond within 30 seconds.
 */

#include "scheduler.h"
#include "hid.h"
#include "log.h"
#include "storage.h"
#include "wifi.h"
#include "serial_proto.h"

#include "pico/stdlib.h"

#include <string.h>

/* ── Internal state ───────────────────────────────────────────────── */

static bool    _active = false;
static bool    _wake_fired_today = false;
static uint8_t _last_wake_day = 0xFF;

/* Minimal day-of-week from epoch seconds (0=Sun, 1=Mon, ..., 6=Sat) */
static uint8_t epoch_to_dow(uint32_t epoch) {
    /* 1970-01-01 was a Thursday (day 4) */
    uint32_t days = epoch / 86400;
    return (uint8_t)((days + 4) % 7);
}

/* Extract hour and minute from epoch seconds */
static void epoch_to_hm(uint32_t epoch, uint8_t *hour, uint8_t *min) {
    uint32_t seconds_in_day = epoch % 86400;
    *hour = (uint8_t)(seconds_in_day / 3600);
    *min  = (uint8_t)((seconds_in_day % 3600) / 60);
}

/* Get day index (0-based from epoch) for reset tracking */
static uint32_t epoch_to_day(uint32_t epoch) {
    return epoch / 86400;
}

/* ── Public API ───────────────────────────────────────────────────── */

void scheduler_init(void) {
    _active = false;
    _wake_fired_today = false;
    _last_wake_day = 0xFF;

    /* Scheduler requires NTP time and a configured schedule */
    uint32_t epoch = wifi_get_epoch();
    if (epoch == 0) return;
    if (g_state.config.schedule_days == 0) return;

    _active = true;
}

bool scheduler_is_active(void) {
    return _active;
}

uint32_t scheduler_next_wake_sec(void) {
    if (!_active) return UINT32_MAX;

    uint32_t epoch = wifi_get_epoch();
    if (epoch == 0) return UINT32_MAX;

    uint8_t target_hour = g_state.config.schedule_hour;
    uint8_t target_min  = g_state.config.schedule_min;

    /* Check each of the next 7 days */
    for (int offset = 0; offset < 7; offset++) {
        uint32_t check_epoch = epoch + (offset * 86400);
        uint8_t dow = epoch_to_dow(check_epoch);

        /* Is this day in the schedule? */
        if (!(g_state.config.schedule_days & (1 << dow))) {
            continue;
        }

        /* Calculate target epoch for this day */
        uint32_t day_start = (check_epoch / 86400) * 86400;
        uint32_t target_epoch = day_start + (target_hour * 3600) + (target_min * 60);

        /* If it's today and the time has passed, skip to next day */
        if (target_epoch <= epoch) {
            continue;
        }

        return target_epoch - epoch;
    }

    return UINT32_MAX;
}

void scheduler_do_wake(void) {
    uint32_t start = to_ms_since_boot(get_absolute_time());

    /* Step 1: USB remote wakeup to wake PC from S3 */
    hid_remote_wakeup();

    /* Step 2: Wait for wake_wait_sec for the PC to finish resuming */
    sleep_ms(g_state.config.wake_wait_sec * 1000);

    /* Step 3: Send Shift to trigger lock screen */
    hid_press_shift();
    sleep_ms(2000);

    /*
     * Step 4: Wait up to 30s for daemon UNLOCK command.
     * If daemon is running, it will send UNLOCK and we're done.
     * If not (e.g., after S3 resume, daemon hasn't started yet),
     * fall back to blind-type.
     */
    uint32_t wait_start = to_ms_since_boot(get_absolute_time());
    bool daemon_handled = false;

    while (to_ms_since_boot(get_absolute_time()) - wait_start < 30000) {
        /* serial_task() is called from main loop, so check the flag */
        if (g_state.boot_unlock_cancelled) {
            /* Daemon sent a command — it's handling things */
            daemon_handled = true;
            break;
        }
        sleep_ms(100);
    }

    if (!daemon_handled && g_state.pin_stored) {
        /* Fallback: blind-type PIN */
        char pin[PIN_MAX_LEN + 1];
        if (storage_load_pin(pin, sizeof(pin))) {
            hid_press_shift();
            sleep_ms(2000);
            hid_press_shift();
            sleep_ms(2000);
            hid_type_string(pin);
            sleep_ms(g_state.config.dialog_wait_sec * 1000);
            hid_press_key(KEY_ENTER);
            memset(pin, 0, sizeof(pin));
        }
    }

    uint32_t dur = to_ms_since_boot(get_absolute_time()) - start;
    log_event(EVENT_SCHEDULE_WAKE,
              daemon_handled ? RESULT_SUCCESS : RESULT_FAIL_TIMEOUT,
              (uint16_t)MIN(dur, 0xFFFF), SOURCE_SCHEDULER);
}

void scheduler_task(void) {
    if (!_active) {
        /* Re-check if NTP has synced since init */
        uint32_t epoch = wifi_get_epoch();
        if (epoch > 0 && g_state.config.schedule_days != 0) {
            _active = true;
        } else {
            return;
        }
    }

    uint32_t epoch = wifi_get_epoch();
    if (epoch == 0) return;

    /* Reset wake_fired flag when the day changes */
    uint32_t today = epoch_to_day(epoch);
    if ((uint8_t)(today & 0xFF) != _last_wake_day) {
        _wake_fired_today = false;
        _last_wake_day = (uint8_t)(today & 0xFF);
    }

    if (_wake_fired_today) return;

    /* Check if it's time to wake */
    uint8_t dow = epoch_to_dow(epoch);
    if (!(g_state.config.schedule_days & (1 << dow))) return;

    uint8_t hour, min;
    epoch_to_hm(epoch, &hour, &min);

    if (hour == g_state.config.schedule_hour &&
        min  == g_state.config.schedule_min) {
        _wake_fired_today = true;
        g_state.boot_unlock_cancelled = false;  /* Reset for new wake */
        scheduler_do_wake();
    }
}

/* storage_load_pin() is available via storage.h */
