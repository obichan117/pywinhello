# TASK-029: Documentation & README

**Status**: todo
**Priority**: medium
**Phase**: 6 — Polish

## Description
User-facing documentation for the GitHub repo. Since target users are non-technical Japanese beginners, the README should be visual and simple. Separate developer docs for contributors.

## Acceptance Criteria

### README.md (user-facing, bilingual)
- [ ] Hero section: what it does in one sentence (ja + en)
- [ ] Visual: photo/diagram of Pico plugged into PC
- [ ] Download link: prominent button to latest release
- [ ] 3-step quickstart: 1. Buy Pico 2. Download 3. Run setup
- [ ] Supported Pico devices list with checkmarks
- [ ] FAQ section:
  - "PINは安全ですか？" (PIN stored on device only, never on PC/internet)
  - "どのPicoを買えばいいですか？" (any works, W recommended)
  - "シャットダウンしても動きますか？" (use Sleep instead)
- [ ] Screenshots of setup wizard

### Developer docs (docs/ or CONTRIBUTING.md)
- [ ] Architecture overview (firmware + PC + installer)
- [ ] Building from source (firmware + PC)
- [ ] Serial protocol reference
- [ ] Testing guide (unit, hardware, manual)
- [ ] Release process

### CLAUDE.md
- [ ] Updated for v2 architecture
- [ ] Quick start commands (build firmware, run PC tests, build installer)
- [ ] Key file paths
- [ ] Architecture summary

## Notes
- README is primarily Japanese (target audience), with English sections
- MkDocs from v1 can be kept or replaced — user docs are minimal (setup.exe is self-explanatory)
- Consider a simple landing page (GitHub Pages) for download link
