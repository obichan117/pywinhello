/*
 * log.h — Circular event log (20 entries x 16 bytes)
 *
 * Stored in RAM during runtime, persisted to /log.bin on flash.
 * Oldest entries are overwritten when buffer is full.
 */

#ifndef LOG_H
#define LOG_H

#include "pywinhello.h"

/* ── Public API ───────────────────────────────────────────────────── */

/**
 * Initialize log subsystem. Loads existing log from flash.
 */
void log_init(void);

/**
 * Record an event.
 *
 * @param type     Event type
 * @param result   Event result code
 * @param dur_ms   Duration of operation in milliseconds
 * @param source   Source of event (firmware, daemon, scheduler)
 */
void log_event(event_type_t type, event_result_t result,
               uint16_t dur_ms, event_source_t source);

/**
 * Get all log entries (oldest first).
 *
 * @param entries   Output array
 * @param max_count Size of output array
 * @return Number of entries copied
 */
int log_read_all(log_entry_t *entries, int max_count);

/**
 * Get current number of stored entries.
 */
int log_count(void);

/**
 * Persist current log buffer to flash.
 * Called automatically by log_event(), but can be forced.
 */
bool log_flush(void);

/**
 * Clear all log entries (RAM + flash).
 */
void log_clear(void);

/**
 * Get current timestamp (NTP epoch if available, else uptime).
 */
uint32_t log_get_timestamp(void);

#endif /* LOG_H */
