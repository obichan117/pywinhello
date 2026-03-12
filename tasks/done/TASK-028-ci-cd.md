# TASK-028: CI/CD — GitHub Actions

**Status**: todo
**Priority**: medium
**Phase**: 5 — Installer & Distribution

## Description
GitHub Actions pipeline that builds, tests, and releases the full installer + firmware on git tag push.

## Acceptance Criteria

### CI (on every push / PR)
- [ ] `test-pc` job (windows-latest):
  - `uv sync`
  - `uv run pytest pc/tests/ -m "not hardware"`
  - `uv run ruff check pc/`
  - `uv run mypy pc/src/`
- [ ] `build-firmware` job (ubuntu-latest):
  - Install Pico SDK + ARM GCC toolchain
  - `cmake --build firmware/` (both RP2040 and RP2350 targets)
  - Upload .uf2 artifacts

### Release (on tag push v*)
- [ ] `build-installer` job (windows-latest):
  - Depends on test-pc + build-firmware
  - PyInstaller: build monitor.exe + settings.exe
  - Download firmware .uf2 artifacts
  - Inno Setup: compile installer
  - Upload installer artifact
- [ ] `release` job:
  - Create GitHub Release from tag
  - Upload assets:
    - `pywinhello_setup.exe`
    - `manifest.json` (auto-generated from tag + hashes)
    - `firmware_rp2040.uf2`
    - `firmware_rp2350.uf2`
  - Generate changelog from commits since last tag
- [ ] `manifest.json` auto-generation:
  - Version from git tag
  - SHA-256 hashes computed from built .uf2 files
  - Changelog from git log

### Workflow files
- [ ] `.github/workflows/ci.yml` — test + build on push/PR
- [ ] `.github/workflows/release.yml` — build + publish on tag

## Notes
- Pico SDK setup: use `pico-sdk` GitHub Action or manual install
- ARM toolchain: `arm-none-eabi-gcc` from ARM website or apt
- Inno Setup: install via `choco install innosetup` or direct download
- PyInstaller on GitHub Actions: works out of the box on windows-latest
- Consider caching Pico SDK and ARM toolchain for faster builds
