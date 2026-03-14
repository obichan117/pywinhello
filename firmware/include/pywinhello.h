/*
 * pywinhello.h — Shared types, constants, and forward declarations
 *
 * This is the top-level header for the pywinhello Pico firmware.
 * All modules include this for common definitions.
 */

#ifndef PYWINHELLO_H
#define PYWINHELLO_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>

/* ── Firmware version ─────────────────────────────────────────────── */

#define FW_VERSION_MAJOR  1
#define FW_VERSION_MINOR  0
#define FW_VERSION_PATCH  0
#define FW_VERSION_STRING "1.0.0"

/* ── Device types (detected at runtime) ───────────────────────────── */

typedef enum {
    DEVICE_PICO       = 0,
    DEVICE_PICO_W     = 1,
    DEVICE_PICO_2     = 2,
    DEVICE_PICO_2_W   = 3,
    DEVICE_UNKNOWN    = 0xFF
} device_type_t;

/* ── Log event types ──────────────────────────────────────────────── */

typedef enum {
    EVENT_BOOT_UNLOCK    = 0x01,
    EVENT_WAKE_UNLOCK    = 0x02,
    EVENT_HELLO          = 0x03,
    EVENT_SCHEDULE_WAKE  = 0x04,
    EVENT_FIRMWARE_UPDATE = 0x05,
} event_type_t;

/* ── Log result codes ─────────────────────────────────────────────── */

typedef enum {
    RESULT_SUCCESS          = 0x00,
    RESULT_FAIL_TIMEOUT     = 0x01,
    RESULT_FAIL_WRONG_PIN   = 0x02,
    RESULT_FAIL_NO_FOCUS    = 0x03,
    RESULT_FAIL_NO_PIN      = 0x04,
    RESULT_FAIL_CANCELLED   = 0x05,
    RESULT_FAIL_GENERIC     = 0xFF,
} event_result_t;

/* ── Log source identifiers ──────────────────────────────────────── */

typedef enum {
    SOURCE_FIRMWARE  = 0x00,
    SOURCE_DAEMON    = 0x01,
    SOURCE_SCHEDULER = 0x02,
} event_source_t;

/* ── Log entry: 16 bytes, packed ──────────────────────────────────── */

typedef struct __attribute__((packed)) {
    uint32_t timestamp;      /* Unix epoch seconds (or 0 if no RTC) */
    uint8_t  event_type;     /* event_type_t */
    uint8_t  result;         /* event_result_t */
    uint16_t duration_ms;    /* How long the operation took */
    uint8_t  source;         /* event_source_t */
    uint8_t  reserved[7];    /* Pad to 16 bytes */
} log_entry_t;

_Static_assert(sizeof(log_entry_t) == 16, "log_entry_t must be 16 bytes");

/* ── Config structure (mirrors config.json) ───────────────────────── */

#define CONFIG_MAX_APPS      8
#define CONFIG_APP_NAME_LEN  64
#define CONFIG_SSID_LEN      33
#define CONFIG_PASS_LEN      65

typedef struct {
    /* top-level */
    uint8_t  version;
    char     firmware[16];
    char     device_str[16];
    char     locale[8];

    /* schedule */
    uint8_t  schedule_hour;
    uint8_t  schedule_min;
    uint8_t  schedule_days;  /* Bitmask: bit0=Sun, bit1=Mon, ... bit6=Sat */

    /* timing */
    uint16_t boot_wait_sec;
    uint16_t wake_wait_sec;
    uint16_t keystroke_ms;
    uint8_t  retry_count;
    uint16_t retry_interval_sec;
    uint16_t dialog_wait_sec;

    /* apps whitelist */
    struct {
        char name[CONFIG_APP_NAME_LEN];
        bool enabled;
    } apps[CONFIG_MAX_APPS];
    uint8_t app_count;

    /* wifi (Pico W only) */
    char     wifi_ssid[CONFIG_SSID_LEN];
    char     wifi_password[CONFIG_PASS_LEN];
} config_t;

/* ── Global state ─────────────────────────────────────────────────── */

typedef struct {
    device_type_t device;
    bool          wifi_connected;
    bool          pin_stored;
    bool          boot_unlock_done;
    bool          boot_unlock_cancelled;
    uint32_t      uptime_sec;
    uint32_t      ntp_epoch;        /* Last NTP-synced epoch, or 0 */
    config_t      config;
} app_state_t;

extern app_state_t g_state;

/* ── Flash layout constants ───────────────────────────────────────── */

/*
 * RP2040 has 2MB flash. Layout:
 *   0x10000000 .. 0x10100000  Partition A (firmware, 1MB)
 *   0x10100000 .. 0x10200000  Partition B (staging, 768KB) + FS (256KB)
 *
 * LittleFS occupies the last 256KB.
 */
#define FLASH_TOTAL_SIZE       (2 * 1024 * 1024)
#define FLASH_FS_SIZE          (256 * 1024)
#define FLASH_FS_OFFSET        (FLASH_TOTAL_SIZE - FLASH_FS_SIZE)
/* FLASH_SECTOR_SIZE and FLASH_PAGE_SIZE come from hardware/flash.h */
#include "hardware/flash.h"

/* Dual-partition layout for OTA */
#define FLASH_PART_A_OFFSET    0x00000000
#define FLASH_PART_A_SIZE      (1024 * 1024)     /* 1MB */
#define FLASH_PART_B_OFFSET    FLASH_PART_A_SIZE
#define FLASH_PART_B_SIZE      (FLASH_TOTAL_SIZE - FLASH_PART_A_SIZE - FLASH_FS_SIZE)

/* Boot flags stored in last sector before FS */
#define FLASH_BOOT_FLAG_OFFSET (FLASH_FS_OFFSET - FLASH_SECTOR_SIZE)
#define BOOT_FLAG_MAGIC        0x50574831  /* "PWH1" */

/* ── Encrypted PIN constraints ────────────────────────────────────── */

#define PIN_MAX_LEN        16     /* Max PIN digits */
#define PIN_ENC_BLOCK_SIZE 16     /* AES block size */
#define PIN_SALT_SIZE      16
#define PIN_IV_SIZE        16
#define AES_KEY_SIZE       32     /* AES-256 */

/* ── USB identifiers ──────────────────────────────────────────────── */

#define USB_VID  0x2E8A  /* Raspberry Pi */
#define USB_PID  0x4001  /* Custom composite: HID + CDC */

/* ── Serial protocol ──────────────────────────────────────────────── */

#define SERIAL_BUF_SIZE    4096
#define SERIAL_LINE_MAX    2048

/* ── Utility macros ───────────────────────────────────────────────── */

#define MIN(a, b) ((a) < (b) ? (a) : (b))
#define MAX(a, b) ((a) > (b) ? (a) : (b))

#endif /* PYWINHELLO_H */
