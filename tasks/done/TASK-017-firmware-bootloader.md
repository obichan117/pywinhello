# TASK-017: Firmware Serial Bootloader — OTA Updates

**Status**: todo
**Priority**: medium
**Phase**: 2 — Firmware Features

## Description
Serial bootloader that allows firmware updates from the PC without requiring BOOTSEL button. After initial setup, users never touch the Pico physically again for updates.

## Acceptance Criteria
- [ ] FLASH:<size> serial command triggers bootloader mode:
  1. Pico responds READY
  2. Receives binary data stream (raw bytes, not text)
  3. Writes to secondary flash partition
  4. Verifies SHA-256 hash (sent as final 32 bytes)
  5. On success: swaps active partition, reboots
  6. On failure: stays on current firmware, responds ERR
- [ ] Dual-partition flash layout:
  - Partition A: active firmware
  - Partition B: staging area for new firmware
  - Boot selector: reads flag to determine which partition to boot
- [ ] Rollback safety:
  - After flashing new firmware, set "pending verification" flag
  - New firmware must send BOOT_OK within 10s of startup
  - If no BOOT_OK → revert to previous partition on next power cycle
- [ ] Flash progress reported over serial:
  - `PROGRESS:<percent>\n` every 10%
- [ ] Total update time < 10 seconds for typical firmware size (~200KB)
- [ ] PC-side `serial/flasher.py` implementation (sends .uf2 payload)

## Notes
- Pico SDK has `flash_range_program()` for writing to flash
- Must disable interrupts during flash writes (Pico SDK requirement)
- Serial baud rate may need increase for OTA (115200 → 921600 during flash)
- First flash (BOOTSEL) is still required — bootloader is part of the initial firmware
- Subsequent updates go through this serial bootloader
