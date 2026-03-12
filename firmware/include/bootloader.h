/*
 * bootloader.h — OTA serial flash with dual partition
 *
 * Receives firmware binary over serial, writes to staging partition,
 * verifies SHA-256, and swaps active partition on success.
 */

#ifndef BOOTLOADER_H
#define BOOTLOADER_H

#include "pywinhello.h"

/* ── Boot flags ───────────────────────────────────────────────────── */

typedef struct __attribute__((packed)) {
    uint32_t magic;           /* BOOT_FLAG_MAGIC */
    uint8_t  active_part;     /* 0 = partition A, 1 = partition B */
    uint8_t  pending_verify;  /* 1 = new firmware, needs BOOT_OK */
    uint8_t  boot_count;      /* Incremented each boot, reset on BOOT_OK */
    uint8_t  reserved;
} boot_flags_t;

/* ── Public API ───────────────────────────────────────────────────── */

/**
 * Initialize bootloader subsystem. Reads boot flags.
 * If pending_verify and boot_count > 1, triggers rollback.
 */
void bootloader_init(void);

/**
 * Enter flash receive mode. Called when FLASH:<size> command received.
 *
 * @param firmware_size  Expected size of firmware binary (excluding 32-byte SHA)
 * @return true if ready to receive
 */
bool bootloader_start_flash(uint32_t firmware_size);

/**
 * Feed received binary data to the bootloader.
 * Called repeatedly as serial data arrives during flash mode.
 *
 * @param data  Raw binary data
 * @param len   Length of data
 * @return true to continue, false on error (aborts flash)
 */
bool bootloader_feed_data(const uint8_t *data, size_t len);

/**
 * Check if flash receive is complete.
 */
bool bootloader_is_complete(void);

/**
 * Finalize flash: verify SHA-256, swap partitions, reboot.
 * Only call after bootloader_is_complete() returns true.
 *
 * @return false on verification failure (stays on current firmware)
 *         Does not return on success (reboots).
 */
bool bootloader_finalize(void);

/**
 * Confirm new firmware is working (BOOT_OK command).
 * Clears pending_verify flag.
 */
void bootloader_confirm(void);

/**
 * Rollback to previous partition.
 * Swaps active partition flag and reboots.
 */
void bootloader_rollback(void);

/**
 * Get current boot flags (for STATUS).
 */
const boot_flags_t *bootloader_get_flags(void);

/**
 * Get flash progress percentage (0-100).
 */
uint8_t bootloader_progress(void);

#endif /* BOOTLOADER_H */
