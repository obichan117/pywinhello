/*
 * scheduler.h — Schedule parsing and USB remote wakeup
 *
 * Calculates next wake time from config schedule + NTP time.
 * Triggers USB remote wakeup at scheduled time (Pico W only).
 */

#ifndef SCHEDULER_H
#define SCHEDULER_H

#include "pywinhello.h"

/* ── Public API ───────────────────────────────────────────────────── */

/**
 * Initialize scheduler. Requires NTP to be synced first.
 */
void scheduler_init(void);

/**
 * Scheduler periodic task — call from main loop.
 * Checks if current time matches schedule, triggers wake if so.
 */
void scheduler_task(void);

/**
 * Calculate seconds until next scheduled wake.
 *
 * @return Seconds until next wake, or UINT32_MAX if no schedule configured
 */
uint32_t scheduler_next_wake_sec(void);

/**
 * Check if schedule is active (NTP synced + schedule configured).
 */
bool scheduler_is_active(void);

/**
 * Perform the scheduled wake sequence:
 *   1. USB remote wakeup
 *   2. Wait wake_wait_sec
 *   3. If no daemon UNLOCK within 30s, do blind-type fallback
 */
void scheduler_do_wake(void);

#endif /* SCHEDULER_H */
