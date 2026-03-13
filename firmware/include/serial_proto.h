/*
 * serial_proto.h — Serial command protocol handler
 *
 * Text protocol over USB CDC serial:
 *   Request:  "COMMAND:payload\n"
 *   Response: "OK:response\n" or "ERR:message\n"
 */

#ifndef SERIAL_PROTO_H
#define SERIAL_PROTO_H

#include "pywinhello.h"

/* ── Command IDs (internal) ───────────────────────────────────────── */

typedef enum {
    CMD_UNKNOWN = 0,
    CMD_PING,
    CMD_GET_CONFIG,
    CMD_SET_CONFIG,
    CMD_SETUP_PIN,
    CMD_CLEAR,
    CMD_UNLOCK,      /* Type stored PIN + Enter */
    CMD_HELLO,       /* Type stored PIN only (no Enter) */
    CMD_TYPE,        /* Type arbitrary string (v1 compat) */
    CMD_PRESS,       /* Press special key (v1 compat) */
    CMD_GET_LOG,
    CMD_FLASH,       /* Enter bootloader flash mode */
    CMD_STATUS,
    CMD_BOOT_OK,     /* Confirm new firmware is working */
    CMD_REBOOT,      /* Reboot into BOOTSEL for UF2 flashing */
} command_id_t;

/* ── Public API ───────────────────────────────────────────────────── */

/**
 * Initialize serial protocol handler. Call once after USB init.
 */
void serial_init(void);

/**
 * Process incoming serial data. Call from main loop.
 * Reads available bytes, parses complete lines, dispatches commands.
 */
void serial_task(void);

/**
 * Send a response line over serial.
 * @param prefix  "OK" or "ERR"
 * @param message Response payload (may be NULL for OK with no data)
 */
void serial_respond(const char *prefix, const char *message);

/**
 * Send a raw string over serial (for PROGRESS updates, etc.).
 */
void serial_send_raw(const char *data, size_t len);

/**
 * Check if we are currently in flash/binary receive mode.
 */
bool serial_in_flash_mode(void);

/**
 * Cancel boot unlock sequence (called when daemon sends a command
 * before boot_wait expires, proving the daemon is alive).
 */
void serial_cancel_boot_unlock(void);

#endif /* SERIAL_PROTO_H */
