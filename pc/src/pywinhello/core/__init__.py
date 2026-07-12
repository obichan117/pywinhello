"""GUI-independent shared services for config, PIN, schedule, status, and diagnostics.

Called by both the settings GUI and the future CLI. No customtkinter import,
no threading — synchronous calls against a caller-provided SerialProtocol.
"""

from pywinhello.core.config_service import (
    build_patch,
    get_field,
    parse_assignment,
    read_config,
    write_config,
)
from pywinhello.core.diagnostics import (
    LockUnlockResult,
    LockUnlockTest,
    TypeTestResult,
    run_notepad_type_test,
)
from pywinhello.core.pin_service import register_pin, validate_pin
from pywinhello.core.schedule_service import (
    DAY_KEYS,
    DEFAULT_DAYS,
    format_time,
    parse_days,
    parse_time,
    save_schedule,
)
from pywinhello.core.status_service import StatusReport, gather_status
from pywinhello.core.update_service import (
    UpdateCheckResult,
    apply_firmware_update,
    check_for_update,
)

__all__ = [
    "DAY_KEYS",
    "DEFAULT_DAYS",
    "LockUnlockResult",
    "LockUnlockTest",
    "StatusReport",
    "TypeTestResult",
    "UpdateCheckResult",
    "apply_firmware_update",
    "build_patch",
    "check_for_update",
    "format_time",
    "gather_status",
    "get_field",
    "parse_assignment",
    "parse_days",
    "parse_time",
    "read_config",
    "register_pin",
    "run_notepad_type_test",
    "save_schedule",
    "validate_pin",
    "write_config",
]
