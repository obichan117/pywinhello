"""CLI entry point for pywinhello."""

from __future__ import annotations

import argparse
import logging
import sys


def _cmd_serve(args: argparse.Namespace) -> None:
    """Run the monitor daemon."""
    import yaml

    from pywinhello import HelloMonitor
    from pywinhello.models import AppConfig, MonitorConfig

    with open(args.config) as f:
        raw = yaml.safe_load(f)

    apps = [AppConfig(**app) for app in raw.get("apps", [])]
    config = MonitorConfig(
        apps=apps,
        hid_port=raw.get("hid_port"),
        inter_key_delay_ms=raw.get("inter_key_delay_ms", 50),
    )

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

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG, format="%(name)s %(levelname)s %(message)s")
    else:
        logging.basicConfig(level=logging.INFO, format="%(message)s")

    if args.command == "serve":
        _cmd_serve(args)
    elif args.command == "ping":
        _cmd_ping(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
