"""Entry point for ``python -m pywinhello`` (monitor service).

Used by PyInstaller to create the background process executable.
"""

import logging


def main() -> None:
    """Start the monitor service."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    from pywinhello.monitor import MonitorService

    service = MonitorService()
    try:
        service.start()
    except KeyboardInterrupt:
        pass
    finally:
        service.stop()


if __name__ == "__main__":
    main()
