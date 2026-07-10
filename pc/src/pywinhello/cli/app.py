"""Typer CLI wrapping pywinhello.core against a connected Pico over serial."""

from __future__ import annotations

import contextlib
import json
import logging
from collections.abc import Iterator
from dataclasses import asdict

import typer
from rich.console import Console
from rich.table import Table

from pywinhello.core import (
    DEFAULT_DAYS,
    LockUnlockTest,
    StatusReport,
    apply_firmware_update,
    build_patch,
    check_for_update,
    gather_status,
    get_field,
    parse_assignment,
    parse_time,
    read_config,
    register_pin,
    run_notepad_type_test,
    save_schedule,
    write_config,
)
from pywinhello.monitor.service import MonitorService
from pywinhello.monitor.updater import compare_versions
from pywinhello.serial.device import PicoDevice, find_pico_port
from pywinhello.setup import BUNDLED_FW_VERSION, DeviceState, detect, provision

console = Console()

app = typer.Typer(no_args_is_help=True, help="pywinhello device CLI.")
config_app = typer.Typer(no_args_is_help=True, help="Read/write device configuration.")
pin_app = typer.Typer(no_args_is_help=True, help="Manage the PIN stored on the Pico.")
test_app = typer.Typer(no_args_is_help=True, help="Run diagnostic tests.")
update_app = typer.Typer(no_args_is_help=True, help="Check for and apply updates.")
app.add_typer(config_app, name="config")
app.add_typer(pin_app, name="pin")
app.add_typer(test_app, name="test")
app.add_typer(update_app, name="update")


@contextlib.contextmanager
def _connected_device() -> Iterator[PicoDevice]:
    port = find_pico_port()
    if port is None:
        console.print("[red]No Pico found. Connect your Pico and try again.[/red]")
        raise typer.Exit(code=1)

    device = PicoDevice(port=port)
    try:
        device.connect()
    except (RuntimeError, TimeoutError, ConnectionError) as e:
        console.print(f"[red]Failed to connect to Pico on {port}: {e}[/red]")
        raise typer.Exit(code=1) from e

    try:
        yield device
    finally:
        device.disconnect()


def _print_status_table(report: StatusReport) -> None:
    table = Table(show_header=False)
    table.add_column("Field", style="bold")
    table.add_column("Value")
    table.add_row("Device connected", "yes" if report.device_connected else "no")
    table.add_row("Port", report.port or "-")
    table.add_row("Firmware version", report.firmware_version or "-")
    table.add_row("PIN set", "yes" if report.pin_set else "no")
    table.add_row("Schedule armed", "yes" if report.schedule_armed else "no")
    table.add_row("Monitor running", "yes" if report.monitor_running else "no")
    console.print(table)


@app.command()
def setup() -> None:
    def on_progress(message: str, fraction: float) -> None:
        console.print(f"[cyan]{message}[/cyan] ({fraction:.0%})")

    result = provision(on_progress=on_progress)
    if not result.success:
        console.print(f"[red]{result.message}[/red]")
        raise typer.Exit(code=1)
    console.print(f"[green]{result.message}[/green]")

    pin = typer.prompt("Enter a PIN for your Pico", hide_input=True, confirmation_prompt=True)
    with _connected_device() as device:
        try:
            register_pin(device.protocol, pin)
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(code=1) from e
        except (RuntimeError, TimeoutError, ConnectionError) as e:
            console.print(f"[red]Failed to register PIN: {e}[/red]")
            raise typer.Exit(code=1) from e
        console.print("[green]PIN registered.[/green]")

        time_str = typer.prompt("Wake time (HH:MM)", default="07:45")
        days_str = typer.prompt(
            "Active days (comma-separated)", default=",".join(DEFAULT_DAYS)
        )
        try:
            hour, minute = parse_time(time_str)
            days = [day.strip() for day in days_str.split(",")]
            save_schedule(device.protocol, hour, minute, days)
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(code=1) from e
        except (RuntimeError, TimeoutError, ConnectionError) as e:
            console.print(f"[red]Failed to save schedule: {e}[/red]")
            raise typer.Exit(code=1) from e
        console.print("[green]Schedule saved.[/green]")

        port = device.info.port if device.info else None

    if port and typer.confirm("Run a Notepad type test now?", default=False):
        test_result = run_notepad_type_test(
            port, on_progress=lambda message, fraction: console.print(f"{message} ({fraction:.0%})")
        )
        if test_result.passed:
            console.print("[green]Type test passed.[/green]")
        else:
            error = test_result.error or "see details above"
            console.print(f"[red]Type test failed: {error}[/red]")


@app.command()
def status(as_json: bool = typer.Option(False, "--json", help="Output status as JSON.")) -> None:
    report = gather_status()
    if as_json:
        typer.echo(json.dumps(asdict(report), indent=2))
        return
    _print_status_table(report)


@app.command()
def doctor() -> None:
    report = gather_status()
    device = detect()

    firmware_outdated = (
        device.state == DeviceState.RUNNING_PYWINHELLO
        and device.firmware_version is not None
        and compare_versions(device.firmware_version, BUNDLED_FW_VERSION) < 0
    )

    checks: list[tuple[str, bool, str]] = [
        (
            f"Firmware present ({device.state.value})",
            device.state == DeviceState.RUNNING_PYWINHELLO,
            "Run 'pywinhello setup' to flash firmware.",
        ),
        (
            f"Firmware up to date (v{device.firmware_version or '?'})",
            not firmware_outdated,
            "Run 'pywinhello setup' to update firmware.",
        ),
        ("PIN set", report.pin_set, "Run 'pywinhello pin set' to register a PIN."),
        (
            "Schedule armed",
            report.schedule_armed,
            "Run 'pywinhello setup' or 'pywinhello config set schedule.time=HH:MM' "
            "to configure a wake schedule.",
        ),
        ("Port detected", report.port is not None, "Connect your Pico via USB."),
    ]

    for label, ok, fix in checks:
        icon = "[green]OK[/green]" if ok else "[red]FAIL[/red]"
        line = f"{icon} {label}"
        if not ok:
            line += f" -> {fix}"
        console.print(line)

    is_usable = device.state == DeviceState.RUNNING_PYWINHELLO and report.pin_set
    if not is_usable:
        raise typer.Exit(code=1)


@config_app.command("get")
def config_get(
    key: str = typer.Argument(None, help="Dotted config key, e.g. schedule.time"),
) -> None:
    with _connected_device() as device:
        try:
            config = read_config(device.protocol)
        except (RuntimeError, TimeoutError, ConnectionError) as e:
            console.print(f"[red]Failed to read config: {e}[/red]")
            raise typer.Exit(code=1) from e

    if key is None:
        typer.echo(json.dumps(config, indent=2))
        return

    try:
        value = get_field(config, key)
    except KeyError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1) from e
    console.print(value)


@config_app.command("set")
def config_set(
    assignment: str = typer.Argument(..., help="key=value, e.g. schedule.time=08:00"),
) -> None:
    try:
        dotted, value = parse_assignment(assignment)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(code=1) from e

    patch = build_patch(dotted, value)
    with _connected_device() as device:
        try:
            write_config(device.protocol, patch)
        except (RuntimeError, TimeoutError, ConnectionError) as e:
            console.print(f"[red]Failed to write config: {e}[/red]")
            raise typer.Exit(code=1) from e
    console.print(f"[green]Set {dotted} = {value!r}[/green]")


@pin_app.command("set")
def pin_set() -> None:
    pin = typer.prompt("New PIN", hide_input=True, confirmation_prompt=True)
    with _connected_device() as device:
        try:
            register_pin(device.protocol, pin)
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(code=1) from e
        except (RuntimeError, TimeoutError, ConnectionError) as e:
            console.print(f"[red]Failed to register PIN: {e}[/red]")
            raise typer.Exit(code=1) from e
    console.print("[green]PIN registered.[/green]")


@pin_app.command("clear")
def pin_clear() -> None:
    if not typer.confirm(
        "This will erase the PIN and reset the Pico to factory state. Continue?", default=False
    ):
        raise typer.Exit(code=0)

    with _connected_device() as device:
        try:
            device.protocol.clear()
        except (RuntimeError, TimeoutError, ConnectionError) as e:
            console.print(f"[red]Failed to clear Pico: {e}[/red]")
            raise typer.Exit(code=1) from e
    console.print("[green]Pico cleared.[/green]")


@test_app.command("lock")
def test_lock() -> None:
    result = LockUnlockTest().run(on_status=console.print)
    if not result.passed:
        console.print(f"[red]{result.error}[/red]")
        raise typer.Exit(code=1)
    console.print(f"[green]Unlock succeeded in {result.elapsed:.1f}s.[/green]")


@test_app.command("type")
def test_type() -> None:
    port = find_pico_port()
    if port is None:
        console.print("[red]No Pico found. Connect your Pico and try again.[/red]")
        raise typer.Exit(code=1)

    result = run_notepad_type_test(
        port, on_progress=lambda message, fraction: console.print(f"{message} ({fraction:.0%})")
    )
    if not result.passed:
        console.print(f"[red]Type test failed: {result.error or 'see details above'}[/red]")
        raise typer.Exit(code=1)
    console.print("[green]Type test passed.[/green]")


@update_app.command("check")
def update_check() -> None:
    result = check_for_update()
    if result.error:
        console.print(f"[red]Update check failed: {result.error}[/red]")
        raise typer.Exit(code=1)

    console.print(f"Current version: v{result.current_version}")
    if result.latest_version:
        console.print(f"Latest version: v{result.latest_version}")
    else:
        console.print("Latest version: unknown")
    if result.has_software_update:
        console.print("[yellow]Software update available.[/yellow]")
    else:
        console.print("[green]Software up to date.[/green]")
    if result.has_firmware_update:
        console.print("[yellow]Firmware update available.[/yellow]")
    else:
        console.print("[green]No firmware update available.[/green]")


@update_app.command("apply")
def update_apply() -> None:
    with _connected_device() as device:
        try:
            success = apply_firmware_update(device.protocol)
        except (RuntimeError, TimeoutError, ConnectionError) as e:
            console.print(f"[red]Firmware update failed: {e}[/red]")
            raise typer.Exit(code=1) from e

    if not success:
        console.print("[red]Firmware update failed.[/red]")
        raise typer.Exit(code=1)
    console.print("[green]Firmware update applied.[/green]")


@app.command()
def serve() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )
    service = MonitorService()
    try:
        service.start()
    except KeyboardInterrupt:
        pass
    finally:
        service.stop()
