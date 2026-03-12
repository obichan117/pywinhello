# TASK-022: PC Monitor — Auto-Updater

**Status**: todo
**Priority**: medium
**Phase**: 3 — PC Monitor

## Description
Silent auto-update mechanism that checks GitHub Releases daily and applies software + firmware updates without user interaction.

## Acceptance Criteria
- [ ] `monitor/updater.py` — GitHub release checker + applier
- [ ] Daily check (on monitor startup + every 24h):
  1. GET `api.github.com/repos/obichan117/pywinhello/releases/latest`
  2. Use ETag / If-None-Match for caching (avoid rate limits)
  3. Parse `manifest.json` from release assets
  4. Compare software_version vs installed version
  5. Compare firmware_version vs Pico-reported version
- [ ] Software update:
  1. Download new .exe to temp directory
  2. Save as `pywinhello-monitor.exe.new`
  3. On next monitor startup: rename `.exe` → `.exe.old`, `.exe.new` → `.exe`, restart
  4. Cleanup: delete `.old` after successful start
- [ ] Firmware update:
  1. Download correct .uf2 (based on Pico device type)
  2. Verify SHA-256 hash from manifest
  3. Wait for Pico idle (not mid-unlock, >5 min until next schedule)
  4. Send FLASH command → Pico OTA updates (TASK-017)
  5. Verify new version via PING after reboot
  6. Rollback: if verification fails, log error (Pico bootloader handles revert)
- [ ] `manifest.json` schema:
  ```json
  {
    "version": "1.2.0",
    "software_version": "1.2.0",
    "firmware_version": "1.1.0",
    "firmware_hash_rp2040": "sha256:...",
    "firmware_hash_rp2350": "sha256:...",
    "changelog_ja": "...",
    "changelog_en": "...",
    "force_update": false,
    "min_protocol_version": 2
  }
  ```
- [ ] Force update: if `force_update: true`, show notification (TASK-026 GUI)
- [ ] Protocol compatibility: if `min_protocol_version` > current, update software first
- [ ] No telemetry, no analytics — only the version check HTTP request
- [ ] Graceful offline: if no internet, silently skip, retry next day

## Notes
- GitHub API rate limit: 60/hour unauthenticated (1 req/day is fine)
- Use `requests` library (already in ecosystem)
- For software self-update, consider using Windows Restart Manager API as alternative
- The rename-on-restart pattern is simple and proven
- Settings app also updated by same mechanism (same .exe or bundled together)
