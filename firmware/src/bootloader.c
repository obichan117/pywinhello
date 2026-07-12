/*
 * bootloader.c — OTA serial flash with dual partition
 *
 * Flash layout (2MB total):
 *   Partition A: 0x000000 .. 0x100000 (1MB, primary firmware)
 *   Partition B: 0x100000 .. 0x1C0000 (768KB, staging area)
 *   LittleFS:    0x1C0000 .. 0x200000 (256KB, filesystem)
 *   Boot flags:  0x1BF000 .. 0x1C0000 (4KB sector before FS)
 *
 * OTA flow:
 *   1. FLASH:<size> command → erase partition B
 *   2. Receive binary data → write to partition B
 *   3. Final 32 bytes = SHA-256 hash of firmware
 *   4. Verify hash → set pending_verify → swap active partition → reboot
 *   5. New firmware must send BOOT_OK within 10s
 *   6. If no BOOT_OK after 2 boots → rollback to previous partition
 */

#include "bootloader.h"
#include "crypto.h"

#include "pico/stdlib.h"
#include "hardware/flash.h"
#include "hardware/sync.h"
#include "hardware/watchdog.h"
#include "hardware/watchdog.h"

#include <string.h>
#include <stdio.h>

/* ── Internal state ───────────────────────────────────────────────── */

static boot_flags_t _flags;
static bool         _flags_loaded = false;

/* Flash receive state */
static uint32_t _flash_expected_size = 0;  /* Firmware size (excl. 32B hash) */
static uint32_t _flash_received = 0;
static uint32_t _flash_total_size = 0;     /* firmware_size + 32 (SHA hash) */
static uint32_t _flash_write_offset = 0;

/* Page buffer for accumulating data before writing */
#define FLASH_WRITE_BUF_SIZE  FLASH_PAGE_SIZE
static uint8_t  _write_buf[FLASH_WRITE_BUF_SIZE];
static size_t   _write_buf_pos = 0;

/* SHA hash from the end of the received data */
static uint8_t  _received_hash[32];
static bool     _hash_extracted = false;

/* ── Boot flags I/O ───────────────────────────────────────────────── */

static void read_boot_flags(void) {
    const uint8_t *ptr = (const uint8_t *)(XIP_BASE + FLASH_BOOT_FLAG_OFFSET);
    memcpy(&_flags, ptr, sizeof(_flags));

    if (_flags.magic != BOOT_FLAG_MAGIC) {
        /* No valid flags: initialize defaults (partition A active) */
        memset(&_flags, 0, sizeof(_flags));
        _flags.magic = BOOT_FLAG_MAGIC;
        _flags.active_part = 0;
        _flags.pending_verify = 0;
        _flags.boot_count = 0;
    }

    _flags_loaded = true;
}

static void write_boot_flags(void) {
    uint8_t page[FLASH_PAGE_SIZE];
    memset(page, 0xFF, sizeof(page));
    memcpy(page, &_flags, sizeof(_flags));

    uint32_t ints = save_and_disable_interrupts();
    flash_range_erase(FLASH_BOOT_FLAG_OFFSET, FLASH_SECTOR_SIZE);
    flash_range_program(FLASH_BOOT_FLAG_OFFSET, page, FLASH_PAGE_SIZE);
    restore_interrupts(ints);
}

/* ── Flash write helper ───────────────────────────────────────────── */

static bool flash_write_page(uint32_t offset, const uint8_t *data) {
    /*
     * Ensure offset is within partition B bounds.
     * offset is relative to flash start (0x10000000).
     */
    if (offset < FLASH_PART_B_OFFSET ||
        offset + FLASH_PAGE_SIZE > FLASH_PART_B_OFFSET + FLASH_PART_B_SIZE) {
        return false;
    }

    uint32_t ints = save_and_disable_interrupts();
    flash_range_program(offset, data, FLASH_PAGE_SIZE);
    restore_interrupts(ints);
    return true;
}

static bool flush_write_buffer(void) {
    if (_write_buf_pos == 0) return true;

    /* Pad remaining buffer with 0xFF */
    if (_write_buf_pos < FLASH_WRITE_BUF_SIZE) {
        memset(_write_buf + _write_buf_pos, 0xFF,
               FLASH_WRITE_BUF_SIZE - _write_buf_pos);
    }

    if (!flash_write_page(_flash_write_offset, _write_buf)) {
        return false;
    }

    _flash_write_offset += FLASH_PAGE_SIZE;
    _write_buf_pos = 0;
    return true;
}

/* ── Public API ───────────────────────────────────────────────────── */

void bootloader_init(void) {
    read_boot_flags();

    /*
     * Rollback check: if firmware is pending verification and this
     * is boot #2+, the previous firmware failed to send BOOT_OK.
     */
    if (_flags.pending_verify) {
        _flags.boot_count++;
        write_boot_flags();

        if (_flags.boot_count > 1) {
            /* Rollback: revert to previous partition */
            bootloader_rollback();
            /* rollback() reboots, so we won't reach here */
        }
    }
}

bool bootloader_start_flash(uint32_t firmware_size) {
    if (firmware_size == 0 || firmware_size > FLASH_PART_B_SIZE - 32) {
        return false;
    }

    _flash_expected_size = firmware_size;
    _flash_total_size = firmware_size + 32;  /* +32 for SHA-256 hash */
    _flash_received = 0;
    _flash_write_offset = FLASH_PART_B_OFFSET;
    _write_buf_pos = 0;
    _hash_extracted = false;

    /* Erase partition B */
    uint32_t erase_size = ((_flash_total_size + FLASH_SECTOR_SIZE - 1) /
                           FLASH_SECTOR_SIZE) * FLASH_SECTOR_SIZE;
    if (erase_size > FLASH_PART_B_SIZE) {
        erase_size = FLASH_PART_B_SIZE;
    }

    uint32_t ints = save_and_disable_interrupts();
    flash_range_erase(FLASH_PART_B_OFFSET, erase_size);
    restore_interrupts(ints);

    return true;
}

bool bootloader_feed_data(const uint8_t *data, size_t len) {
    if (_flash_received + len > _flash_total_size) {
        return false;  /* Too much data */
    }

    for (size_t i = 0; i < len; i++) {
        _write_buf[_write_buf_pos++] = data[i];
        _flash_received++;

        if (_write_buf_pos >= FLASH_WRITE_BUF_SIZE) {
            /*
             * Only write full pages that contain firmware data
             * (not the trailing SHA hash). We'll handle the hash
             * extraction in finalize().
             */
            if (!flush_write_buffer()) {
                return false;
            }
        }
    }

    return true;
}

bool bootloader_is_complete(void) {
    return (_flash_received >= _flash_total_size);
}

bool bootloader_finalize(void) {
    /* Flush any remaining buffered data */
    if (_write_buf_pos > 0) {
        if (!flush_write_buffer()) {
            return false;
        }
    }

    /*
     * Extract SHA-256 hash: the last 32 bytes of the received data
     * are the expected hash of the firmware.
     *
     * Read the hash from flash (it was written as part of the stream).
     */
    uint32_t hash_offset = FLASH_PART_B_OFFSET + _flash_expected_size;
    const uint8_t *hash_ptr = (const uint8_t *)(XIP_BASE + hash_offset);
    memcpy(_received_hash, hash_ptr, 32);

    /* Compute SHA-256 of the firmware data in partition B */
    const uint8_t *fw_ptr = (const uint8_t *)(XIP_BASE + FLASH_PART_B_OFFSET);
    uint8_t computed_hash[32];

    if (!crypto_sha256(fw_ptr, _flash_expected_size, computed_hash)) {
        return false;
    }

    /* Compare hashes */
    if (memcmp(computed_hash, _received_hash, 32) != 0) {
        return false;  /* Hash mismatch */
    }

    /* Hash verified — swap active partition and reboot */
    _flags.active_part = (_flags.active_part == 0) ? 1 : 0;
    _flags.pending_verify = 1;
    _flags.boot_count = 0;
    write_boot_flags();

    /* Log the firmware update event before rebooting */
    /* (Can't call log_event here because we're about to reboot) */

    /* Reboot via watchdog */
    watchdog_reboot(0, 0, 0);

    /* Should not reach here */
    while (1) { tight_loop_contents(); }
    return false;
}

void bootloader_confirm(void) {
    if (!_flags_loaded) return;

    if (_flags.pending_verify) {
        _flags.pending_verify = 0;
        _flags.boot_count = 0;
        write_boot_flags();
    }
}

void bootloader_rollback(void) {
    if (!_flags_loaded) return;

    /* Swap back to previous partition */
    _flags.active_part = (_flags.active_part == 0) ? 1 : 0;
    _flags.pending_verify = 0;
    _flags.boot_count = 0;
    write_boot_flags();

    /* Reboot */
    watchdog_reboot(0, 0, 0);
    while (1) { tight_loop_contents(); }
}

const boot_flags_t *bootloader_get_flags(void) {
    if (!_flags_loaded) return NULL;
    return &_flags;
}

uint8_t bootloader_progress(void) {
    if (_flash_total_size == 0) return 0;
    return (uint8_t)((_flash_received * 100) / _flash_total_size);
}
