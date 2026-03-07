# TASK-004: YAML Config Loader

**Status**: todo
**Priority**: medium

## Description
The CLI serve command loads config via raw yaml.safe_load. Add a proper config loader function in a dedicated location that validates the YAML and returns a MonitorConfig. PyYAML should be an optional dependency (only needed for CLI/config loading).

## Acceptance Criteria
- [ ] `load_config(path) -> MonitorConfig` function
- [ ] Validates required fields (apps must have exe + pin)
- [ ] Clear error messages for invalid config
- [ ] PyYAML as optional dep (`pywinhello[cli]`)
- [ ] Tests for valid/invalid config files
