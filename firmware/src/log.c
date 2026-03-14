/*
 * log.c — Circular event log (20 entries x 16 bytes)
 *
 * Maintains a ring buffer in RAM, persisted to /log.bin on flash.
 * When the buffer is full, the oldest entry is overwritten.
 */

#include "log.h"
#include "storage.h"

#include "pico/stdlib.h"

#include <string.h>

/* ── Internal state ───────────────────────────────────────────────── */

static log_entry_t _entries[LOG_MAX_ENTRIES];
static int  _write_idx = 0;   /* Next slot to write */
static int  _count     = 0;   /* Total entries stored (max LOG_MAX_ENTRIES) */
static bool _dirty     = false;

/* ── Forward declarations for storage (avoid circular include) ────── */

/* These are implemented in storage.c and called via function pointers
 * to break the circular dependency between log and storage. */
typedef bool (*log_persist_fn)(const log_entry_t *entries, int count, int write_idx);
typedef bool (*log_restore_fn)(log_entry_t *entries, int *count, int *write_idx);

static log_persist_fn _persist_fn = NULL;
static log_restore_fn _restore_fn = NULL;

/* ── Registration (called by storage_init) ────────────────────────── */

void log_register_persistence(log_persist_fn persist, log_restore_fn restore) {
    _persist_fn = persist;
    _restore_fn = restore;
}

/* ── Public API ───────────────────────────────────────────────────── */

void log_init(void) {
    memset(_entries, 0, sizeof(_entries));
    _write_idx = 0;
    _count = 0;
    _dirty = false;

    /* Try to load existing log from flash */
    if (_restore_fn) {
        _restore_fn(_entries, &_count, &_write_idx);
    }
}

uint32_t log_get_timestamp(void) {
    /* Prefer NTP epoch if available */
    if (g_state.ntp_epoch > 0) {
        uint32_t elapsed = to_ms_since_boot(get_absolute_time()) / 1000;
        return g_state.ntp_epoch + elapsed;
    }
    /* Fallback: uptime in seconds */
    return to_ms_since_boot(get_absolute_time()) / 1000;
}

void log_event(event_type_t type, event_result_t result,
               uint16_t dur_ms, event_source_t source) {
    log_entry_t entry;
    memset(&entry, 0, sizeof(entry));

    entry.timestamp   = log_get_timestamp();
    entry.event_type  = (uint8_t)type;
    entry.result      = (uint8_t)result;
    entry.duration_ms = dur_ms;
    entry.source      = (uint8_t)source;

    _entries[_write_idx] = entry;
    _write_idx = (_write_idx + 1) % LOG_MAX_ENTRIES;
    if (_count < LOG_MAX_ENTRIES) {
        _count++;
    }

    _dirty = true;
    log_flush();
}

int log_read_all(log_entry_t *entries, int max_count) {
    if (!entries || max_count <= 0) return 0;

    int out_count = (_count < max_count) ? _count : max_count;

    if (_count < LOG_MAX_ENTRIES) {
        /* Buffer not full: entries are at indices [0..count) */
        memcpy(entries, _entries, out_count * sizeof(log_entry_t));
    } else {
        /* Buffer full: oldest entry is at _write_idx */
        int start = _write_idx;
        for (int i = 0; i < out_count; i++) {
            entries[i] = _entries[(start + i) % LOG_MAX_ENTRIES];
        }
    }

    return out_count;
}

int log_count(void) {
    return _count;
}

bool log_flush(void) {
    if (!_dirty || !_persist_fn) {
        return true;  /* Nothing to flush */
    }

    bool ok = _persist_fn(_entries, _count, _write_idx);
    if (ok) {
        _dirty = false;
    }
    return ok;
}

void log_clear(void) {
    memset(_entries, 0, sizeof(_entries));
    _write_idx = 0;
    _count = 0;
    _dirty = true;
    log_flush();
}
