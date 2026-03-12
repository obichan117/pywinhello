/*
 * storage.h — LittleFS flash storage for config, PIN, and logs
 *
 * Uses LittleFS on the last 256KB of Pico flash for
 * wear-leveled persistent storage.
 */

#ifndef STORAGE_H
#define STORAGE_H

#include "pywinhello.h"

/* ── Public API ───────────────────────────────────────────────────── */

/**
 * Initialize LittleFS filesystem. Formats on first use.
 * @return true on success
 */
bool storage_init(void);

/**
 * Load config.json from flash into g_state.config.
 * If file doesn't exist, writes default config.
 * @return true on success
 */
bool storage_load_config(void);

/**
 * Save g_state.config to config.json on flash.
 * @return true on success
 */
bool storage_save_config(void);

/**
 * Get config.json as raw JSON string.
 * @param buf    Output buffer
 * @param buflen Buffer size
 * @return Number of bytes written, or -1 on error
 */
int storage_get_config_json(char *buf, size_t buflen);

/**
 * Set config from raw JSON string. Parses and saves.
 * @param json  Null-terminated JSON string
 * @return true on success
 */
bool storage_set_config_json(const char *json);

/**
 * Store encrypted PIN to /pin.enc.
 * @param pin  Null-terminated PIN string (cleartext, 4-16 digits)
 * @return true on success
 */
bool storage_save_pin(const char *pin);

/**
 * Load and decrypt stored PIN into buffer.
 * @param buf    Output buffer (must be at least PIN_MAX_LEN+1)
 * @param buflen Buffer size
 * @return true on success, false if no PIN stored or decrypt fails
 */
bool storage_load_pin(char *buf, size_t buflen);

/**
 * Check if a PIN is stored.
 */
bool storage_has_pin(void);

/**
 * Erase all stored data (pin.enc, config.json, log.bin).
 * @return true on success
 */
bool storage_clear_all(void);

/**
 * Append a log entry to the circular log buffer.
 */
bool storage_append_log(const log_entry_t *entry);

/**
 * Read all log entries. Returns count of entries read.
 * @param entries  Output array (must hold LOG_MAX_ENTRIES)
 * @param max_entries  Size of output array
 * @return Number of entries read
 */
int storage_read_log(log_entry_t *entries, int max_entries);

/**
 * Get log as base64-encoded string for serial transmission.
 * @param buf    Output buffer
 * @param buflen Buffer size
 * @return Number of bytes written, or -1 on error
 */
int storage_get_log_base64(char *buf, size_t buflen);

/* ── Constants ────────────────────────────────────────────────────── */

#define LOG_MAX_ENTRIES  20

#endif /* STORAGE_H */
