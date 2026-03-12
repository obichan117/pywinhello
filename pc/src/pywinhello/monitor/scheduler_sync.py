"""Windows Task Scheduler sync — create/delete scheduled tasks from Pico config.

Creates wake-timer tasks that wake the PC from sleep at the configured schedule
times. Tasks are created on Pico plug, deleted on Pico unplug.

Uses ``schtasks.exe`` for task management (same approach as pyrakuten-ms2).
"""

from __future__ import annotations

import logging
import subprocess
import sys
from dataclasses import dataclass

logger = logging.getLogger(__name__)

_TASK_PREFIX = "pywinhello-"
_WAKE_TASK_NAME = "pywinhello-wake"

# Day-of-week mapping: config days (1=Mon..7=Sun) -> schtasks days
_DAY_MAP = {
    1: "MON",
    2: "TUE",
    3: "WED",
    4: "THU",
    5: "FRI",
    6: "SAT",
    7: "SUN",
}

# Day name to number mapping for convenience
_DAY_NAME_MAP = {
    "mon": 1,
    "tue": 2,
    "wed": 3,
    "thu": 4,
    "fri": 5,
    "sat": 6,
    "sun": 7,
    "monday": 1,
    "tuesday": 2,
    "wednesday": 3,
    "thursday": 4,
    "friday": 5,
    "saturday": 6,
    "sunday": 7,
}


@dataclass(frozen=True)
class ScheduleConfig:
    """Schedule configuration read from Pico."""

    time: str
    """Wake time in HH:MM format (e.g. '07:45')."""

    days: list[int]
    """Days of week as integers (1=Mon..7=Sun)."""

    enabled: bool = True
    """Whether the schedule is active."""

    @classmethod
    def from_pico_config(cls, config: dict) -> ScheduleConfig | None:
        """Parse schedule from Pico GET_CONFIG response.

        Args:
            config: Full config dict from Pico.

        Returns:
            ScheduleConfig or None if no schedule configured.
        """
        schedule = config.get("schedule")
        if not schedule:
            return None

        time_str = schedule.get("time", "")
        if not time_str:
            return None

        raw_days = schedule.get("days", [])
        days: list[int] = []
        for d in raw_days:
            if isinstance(d, int):
                days.append(d)
            elif isinstance(d, str):
                num = _DAY_NAME_MAP.get(d.lower())
                if num is not None:
                    days.append(num)

        if not days:
            return None

        return cls(
            time=time_str,
            days=days,
            enabled=schedule.get("enabled", True),
        )


def _run_schtasks(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    """Run schtasks.exe with the given arguments."""
    cmd = ["schtasks.exe", *args]
    logger.debug("Running: %s", " ".join(cmd))
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        check=check,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
    )


def _get_pywinhello_exe() -> str:
    """Get the path to the pywinhello-monitor executable.

    Returns the path to the currently running Python or the installed exe.
    """
    # When running as PyInstaller exe, sys.executable is the exe itself
    if getattr(sys, "frozen", False):
        return sys.executable

    # When running from source, use the Python interpreter + module
    return f'"{sys.executable}" -m pywinhello'


def task_exists(task_name: str) -> bool:
    """Check if a scheduled task exists.

    Args:
        task_name: Full task name (e.g. 'pywinhello-wake').

    Returns:
        True if the task exists.
    """
    result = _run_schtasks("/query", "/tn", task_name, check=False)
    return result.returncode == 0


def create_wake_task(schedule: ScheduleConfig) -> bool:
    """Create or update the pywinhello-wake scheduled task.

    The task:
    - Runs daily at the configured time on the configured days
    - Has "Wake the computer to run this task" enabled
    - Runs as the current user (logged-on only)
    - Executes ``pywinhello-monitor.exe wake``

    Args:
        schedule: Schedule configuration from Pico.

    Returns:
        True if the task was created/updated successfully.
    """
    if not schedule.enabled:
        logger.info("Schedule disabled, deleting task if exists")
        delete_wake_task()
        return True

    # Build days string for schtasks
    days_str = ",".join(_DAY_MAP[d] for d in sorted(schedule.days) if d in _DAY_MAP)
    if not days_str:
        logger.warning("No valid days in schedule: %s", schedule.days)
        return False

    exe_path = _get_pywinhello_exe()

    # Delete existing task first (idempotent update)
    delete_wake_task()

    try:
        # Create the scheduled task with XML for wake timer support
        # schtasks /create doesn't have a direct "wake" flag, so we use XML
        xml = _build_task_xml(schedule.time, days_str, exe_path)
        _create_task_from_xml(_WAKE_TASK_NAME, xml)
        logger.info(
            "Created task '%s': %s on %s (wake timer enabled)",
            _WAKE_TASK_NAME,
            schedule.time,
            days_str,
        )
        return True
    except subprocess.CalledProcessError as e:
        logger.error("Failed to create task: %s\n%s", e, e.stderr)
        return False
    except Exception as e:
        logger.error("Failed to create task: %s", e)
        return False


def _build_task_xml(time_str: str, days_str: str, exe_path: str) -> str:
    """Build a Task Scheduler XML definition with wake timer enabled.

    Args:
        time_str: Start time in HH:MM format.
        days_str: Comma-separated day abbreviations (MON,TUE,...).
        exe_path: Path to the executable to run.

    Returns:
        XML string for schtasks /create /xml.
    """
    # Build DaysOfWeek element
    day_elements = ""
    for day in days_str.split(","):
        day_full = {
            "MON": "Monday",
            "TUE": "Tuesday",
            "WED": "Wednesday",
            "THU": "Thursday",
            "FRI": "Friday",
            "SAT": "Saturday",
            "SUN": "Sunday",
        }.get(day.strip(), day.strip())
        day_elements += f"          <{day_full} />\n"

    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>2026-01-01T{time_str}:00</StartBoundary>
      <Enabled>true</Enabled>
      <ScheduleByWeek>
        <DaysOfWeek>
{day_elements}        </DaysOfWeek>
        <WeeksInterval>1</WeeksInterval>
      </ScheduleByWeek>
    </CalendarTrigger>
  </Triggers>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <WakeToRun>true</WakeToRun>
    <ExecutionTimeLimit>PT5M</ExecutionTimeLimit>
    <Enabled>true</Enabled>
  </Settings>
  <Actions>
    <Exec>
      <Command>{exe_path}</Command>
      <Arguments>wake</Arguments>
    </Exec>
  </Actions>
</Task>"""


def _create_task_from_xml(task_name: str, xml: str) -> None:
    """Create a task from an XML definition using a temp file."""
    import tempfile
    from pathlib import Path

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".xml",
        delete=False,
        encoding="utf-16",
    ) as f:
        f.write(xml)
        xml_path = f.name

    try:
        _run_schtasks("/create", "/tn", task_name, "/xml", xml_path, "/f")
    finally:
        Path(xml_path).unlink(missing_ok=True)


def delete_wake_task() -> bool:
    """Delete the pywinhello-wake task if it exists.

    Returns:
        True if the task was deleted or didn't exist.
    """
    if not task_exists(_WAKE_TASK_NAME):
        return True

    try:
        _run_schtasks("/delete", "/tn", _WAKE_TASK_NAME, "/f")
        logger.info("Deleted task '%s'", _WAKE_TASK_NAME)
        return True
    except subprocess.CalledProcessError as e:
        logger.error("Failed to delete task '%s': %s", _WAKE_TASK_NAME, e.stderr)
        return False


def delete_all_tasks() -> int:
    """Delete all pywinhello-* scheduled tasks.

    Returns:
        Number of tasks deleted.
    """
    deleted = 0

    # Query all tasks and filter by prefix
    result = _run_schtasks("/query", "/fo", "csv", "/nh", check=False)
    if result.returncode != 0:
        logger.warning("Failed to query tasks: %s", result.stderr)
        return 0

    for line in result.stdout.splitlines():
        line = line.strip().strip('"')
        # CSV format: "TaskName","Next Run Time","Status"
        parts = line.split('","')
        if not parts:
            continue
        task_name = parts[0].strip('"').lstrip("\\")
        if task_name.startswith(_TASK_PREFIX):
            try:
                _run_schtasks("/delete", "/tn", task_name, "/f")
                deleted += 1
                logger.info("Deleted task '%s'", task_name)
            except subprocess.CalledProcessError:
                logger.warning("Failed to delete task '%s'", task_name)

    return deleted


def enable_wake_timers() -> bool:
    """Enable wake timers in the active Windows power plan.

    Configures both AC and DC power settings so that the "Wake the computer
    to run this task" flag actually works. Requires admin elevation.

    Returns:
        True if the settings were applied successfully.
    """
    if sys.platform != "win32":
        logger.debug("Wake timers only supported on Windows")
        return False

    # Sleep subgroup GUID and wake timers setting GUID
    sleep_guid = "238C9FA8-0AAD-41ED-83F4-97BE242C8F20"
    wake_guid = "BD3B718A-0680-4D9D-8AB2-E1D2B4AC806D"

    try:
        # Get active power scheme
        result = subprocess.run(
            ["powercfg", "/getactivescheme"],
            capture_output=True,
            text=True,
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        # Output: "Power Scheme GUID: xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx  (name)"
        scheme_guid = result.stdout.strip().split()[3]

        # Enable wake timers for AC power
        subprocess.run(
            ["powercfg", "/setacvalueindex", scheme_guid, sleep_guid, wake_guid, "1"],
            capture_output=True,
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        # Enable wake timers for DC (battery) power
        subprocess.run(
            ["powercfg", "/setdcvalueindex", scheme_guid, sleep_guid, wake_guid, "1"],
            capture_output=True,
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        # Apply changes
        subprocess.run(
            ["powercfg", "/setactive", scheme_guid],
            capture_output=True,
            check=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        logger.info("Wake timers enabled for power scheme %s", scheme_guid)
        return True

    except subprocess.CalledProcessError as e:
        logger.error("Failed to enable wake timers: %s\n%s", e, e.stderr)
        return False
    except Exception as e:
        logger.error("Failed to enable wake timers: %s", e)
        return False


def sync_schedule(config: dict) -> bool:
    """Sync Task Scheduler tasks with Pico config.

    Creates or updates the wake task if a schedule is configured,
    or deletes it if no schedule is present.

    This is idempotent — calling with the same config produces the same result.

    Args:
        config: Full config dict from Pico GET_CONFIG.

    Returns:
        True if sync was successful.
    """
    schedule = ScheduleConfig.from_pico_config(config)

    if schedule is None or not schedule.enabled:
        logger.info("No active schedule — deleting all tasks")
        delete_all_tasks()
        return True

    return create_wake_task(schedule)
