"""CLI entry point for pywinhello."""

from __future__ import annotations

import argparse
import logging
import sys


def _cmd_serve(args: argparse.Namespace) -> None:
    """Run the monitor daemon."""
    from pathlib import Path

    from pywinhello import HelloMonitor
    from pywinhello.models import MonitorConfig

    config_path = Path(args.config)
    if config_path.exists():
        from pywinhello.config import load_config

        config = load_config(config_path)
    else:
        # No config file — use PYWINHELLO_PIN env var (enter_pin reads it)
        config = MonitorConfig()

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
    """Set up a Pico as a USB HID keyboard bridge."""
    from pathlib import Path

    from pywinhello.setup import run_setup, verify_pico

    if args.verify_only:
        print("Verifying Pico HID bridge...")
        ok = verify_pico()
        sys.exit(0 if ok else 1)

    drive = Path(args.drive) if args.drive else None
    ok = run_setup(
        drive=drive,
        board=args.board,
        bundle_tag=args.bundle_tag,
        skip_verify=args.skip_verify,
    )
    sys.exit(0 if ok else 1)


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

    setup_p = sub.add_parser(
        "setup-pico",
        help="Install firmware on connected Pico",
        description="Set up a Raspberry Pi Pico as a USB HID keyboard bridge",
    )
    setup_p.add_argument(
        "--drive", default=None, help="CIRCUITPY drive path (auto-detected if omitted)"
    )
    setup_p.add_argument(
        "--board",
        default=None,
        choices=["pico", "pico_w", "pico2", "pico2_w"],
        help="Board variant for UF2 download (auto-detected if omitted)",
    )
    setup_p.add_argument(
        "--bundle-tag", default=None, help="CircuitPython bundle release tag (default: latest)"
    )
    setup_p.add_argument(
        "--verify-only", action="store_true", help="Only verify PING/PONG, skip firmware copy"
    )
    setup_p.add_argument(
        "--skip-verify", action="store_true", help="Skip the PING verification step after setup"
    )

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
