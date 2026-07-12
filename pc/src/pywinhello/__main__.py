"""Entry point for ``python -m pywinhello`` — delegates to the Typer CLI.

The monitor service itself (formerly run here directly) is now `pywinhello
serve`. The packaged pywinhello-monitor.exe still builds from
monitor/service.py directly and does not go through this module.
"""

from pywinhello.cli import app


def main() -> None:
    app()


if __name__ == "__main__":
    main()
