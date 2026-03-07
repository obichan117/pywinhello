"""CLI entry point for pywinhello."""

from __future__ import annotations

import argparse
import logging
import sys


def _cmd_serve(args: argparse.Namespace) -> None:
    """Run the monitor daemon."""
    from pywinhello import HelloMonitor
    from pywinhello.config import load_config

    config = load_config(args.config)
    monitor = HelloMonitor(config)
    try:
        monitor.serve(on_event=lambda e: print(e))
    except KeyboardInterrupt:
        monitor.stop()


def _cmd_ping(args: argparse.Namespace) -> None:
    """Ping the Pico HID bridge."""
    from pywinhello import HIDKeyboard

    port = args.port if args.port != "auto" else None
    try:
        with HIDKeyboard(port=port) as kb:
            if kb.ping():
                print(f"PONG from {kb._port_name}")
            else:
                print("No response", file=sys.stderr)
                sys.exit(1)
    except ConnectionError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def _cmd_setup_pico(args: argparse.Namespace) -> None:
    """Guide user through Pico firmware setup."""
    import shutil
    from pathlib import Path

    firmware_dir = Path(__file__).parent.parent.parent / "firmware" / "pico_hid"

    # Detect CIRCUITPY drive
    circuitpy = None
    for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
        candidate = Path(f"{letter}:\\")
        if (candidate / "boot_out.txt").exists():
            circuitpy = candidate
            break

    if circuitpy is None:
        print("CIRCUITPY drive not found.")
        print("1. Flash CircuitPython UF2 to your Pico first")
        print("2. Ensure the Pico is connected and CIRCUITPY is mounted")
        sys.exit(1)

    print(f"Found CIRCUITPY at {circuitpy}")

    # Check for adafruit_hid
    hid_lib = circuitpy / "lib" / "adafruit_hid"
    if not hid_lib.exists():
        print(f"\nadafruit_hid not found at {hid_lib}")
        print("Download from: https://circuitpython.org/libraries")
        print("Copy the adafruit_hid/ folder to CIRCUITPY/lib/")
        sys.exit(1)

    # Copy firmware files
    for name in ("boot.py", "code.py"):
        src = firmware_dir / name
        dst = circuitpy / name
        if not src.exists():
            print(f"Firmware file not found: {src}", file=sys.stderr)
            sys.exit(1)
        shutil.copy2(src, dst)
        print(f"Copied {name} -> {dst}")

    print("\nFirmware installed. Reset the Pico, then run: pywinhello ping")


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="pywinhello",
        description="Windows Hello PIN automation via USB HID",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")

    sub = parser.add_subparsers(dest="command")

    serve_p = sub.add_parser("serve", help="Run monitor daemon")
    serve_p.add_argument("-c", "--config", default="config.yaml", help="Config file path")

    ping_p = sub.add_parser("ping", help="Ping Pico HID bridge")
    ping_p.add_argument("-p", "--port", default="auto", help="COM port (default: auto-detect)")

    sub.add_parser("setup-pico", help="Install firmware on connected Pico")

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(name)s %(levelname)s %(message)s")
    else:
        logging.basicConfig(level=logging.INFO, format="%(message)s")

    if args.command == "serve":
        _cmd_serve(args)
    elif args.command == "ping":
        _cmd_ping(args)
    elif args.command == "setup-pico":
        _cmd_setup_pico(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
