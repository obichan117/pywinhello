/*
 * wifi.h — CYW43 WiFi auto-detection and NTP sync
 *
 * Conditionally compiled: WiFi features are only available on Pico W.
 * On non-W boards, all functions are no-ops or return false.
 */

#ifndef WIFI_H
#define WIFI_H

#include "pywinhello.h"

/* ── Public API ───────────────────────────────────────────────────── */

/**
 * Probe for WiFi hardware (CYW43 chip).
 * Sets g_state.device appropriately.
 *
 * @return true if WiFi hardware is present
 */
bool wifi_detect(void);

/**
 * Initialize and connect to WiFi using stored credentials.
 * No-op if WiFi hardware not present or no credentials stored.
 *
 * @return true if connected successfully
 */
bool wifi_connect(void);

/**
 * Disconnect from WiFi.
 */
void wifi_disconnect(void);

/**
 * Check if WiFi is currently connected.
 */
bool wifi_is_connected(void);

/**
 * Perform NTP time sync. Updates g_state.ntp_epoch.
 *
 * @return true if sync succeeded
 */
bool wifi_ntp_sync(void);

/**
 * Get current epoch time (NTP-synced).
 * Returns 0 if NTP has never synced.
 */
uint32_t wifi_get_epoch(void);

/**
 * WiFi periodic task — call from main loop.
 * Handles reconnection and periodic NTP re-sync.
 */
void wifi_task(void);

/**
 * Get WiFi status string for STATUS command.
 * @param buf    Output buffer
 * @param buflen Buffer size
 */
void wifi_status_string(char *buf, size_t buflen);

#endif /* WIFI_H */
