# TASK-012: Firmware Storage — LittleFS, Config, Encrypted PIN

**Status**: todo
**Priority**: high
**Phase**: 1 — Foundation

## Description
Implement persistent storage on Pico flash using LittleFS. Stores config (schedule, timing, app whitelist, locale), encrypted PIN, and event log. The Pico is the sole data owner — PC stores nothing.

## Acceptance Criteria
- [ ] LittleFS filesystem initialized on Pico flash (reserved region after firmware)
- [ ] `storage.c/h` — read/write/delete files on LittleFS
- [ ] `config.json` schema implemented:
  ```json
  {
    "version": 2,
    "firmware": "1.0.0",
    "device": "pico_w",
    "locale": "ja",
    "schedule": { "time": "07:45", "days": [1,2,3,4,5] },
    "timing": {
      "boot_wait_sec": 45,
      "wake_wait_sec": 5,
      "keystroke_ms": 50,
      "retry_count": 3,
      "retry_interval_sec": 10,
      "dialog_wait_sec": 1
    },
    "apps": { "lock_screen": true, "MarketSpeed2.exe": true }
  }
  ```
- [ ] `crypto.c/h` — AES-256 PIN encryption using mbedtls
  - Key derived from RP2040 unique ID + salt via HKDF
  - PIN encrypted at rest in `/pin.enc`
  - Decrypt only into RAM when typing
  - No `GET_PIN` serial command (PIN never sent back to PC)
- [ ] `log.c/h` — circular buffer (20 entries × 16 bytes) in `/log.bin`
  - Event types: BOOT_UNLOCK, WAKE_UNLOCK, HELLO, SCHEDULE_WAKE, FIRMWARE_UPDATE
  - Results: SUCCESS, FAIL_TIMEOUT, FAIL_WRONG_PIN, FAIL_NO_FOCUS
  - Timestamp (4B), event_type (1B), result (1B), duration_ms (2B), source (1B)
- [ ] Serial commands wired up:
  - GET_CONFIG → returns config.json contents
  - SET_CONFIG:<json> → writes config.json
  - SETUP_PIN:<pin> → encrypts and stores
  - CLEAR → wipes pin.enc + config.json + log.bin
  - GET_LOG → returns base64-encoded log
- [ ] Config survives power cycle (write + read back test)

## Notes
- RP2040 unique ID: `pico_get_unique_board_id()` — 8 bytes, unique per chip
- mbedtls is bundled with Pico SDK — use `pico_mbedtls` CMake target
- LittleFS flash region: last 256KB of 2MB flash (or configurable via linker script)
- PIN is typically 4-8 digits — small payload, AES-256 is overkill but standard
- SETUP_PIN sends PIN in cleartext over serial — acceptable since it's a local USB cable
