"""Live integration test for focus-guard PIN entry.

Tests that pywinhello correctly guards against PIN leaking
into non-credential windows.

Requires:
- Pico W connected via USB
- MS2 open (will be closed and relaunched)
- PYWINHELLO_PIN env var set

Run manually:
    cd C:/Users/owner/Documents/dev/jp-trading
    uv run python C:/Users/owner/Documents/dev/pywinhello/tests/integration/test_focus_guard.py
"""

import logging
import sys
import time

sys.stdout.reconfigure(encoding="utf-8")
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s.%(msecs)03d %(name)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)


def test_full_login_cycle():
    """Close MS2, relaunch, and verify PIN entry with focus guard."""
    from pyrakuten_ms2 import MS2Client

    client = MS2Client()

    # --- Phase 1: Close MS2 ---
    print("\n=== Phase 1: Closing MS2 ===")
    if client._login_service.is_logged_in():
        print("MS2 is logged in — quitting...")
        ok = client.quit(timeout=20.0)
        print(f"Quit result: {ok}")
        if not ok:
            print("FAILED to quit MS2")
            sys.exit(1)
        time.sleep(3.0)  # Wait for full process exit
    else:
        print("MS2 not detected as logged in — checking for windows...")
        windows = client._runtime.connector.get_all_windows()
        if windows:
            print(f"Found {len(windows)} window(s) — quitting...")
            client.quit(timeout=20.0)
            time.sleep(3.0)
        else:
            print("No MS2 windows found — already closed")

    # --- Phase 2: Relaunch and login ---
    print("\n=== Phase 2: Launching MS2 + passkey login ===")
    print("pywinhello daemon should be running in background...")
    print("(The focus guard will abort if credential dialog loses focus)")

    result = client.login()
    print(f"\nLogin result: {result}")

    if result:
        print("\n>> SUCCESS — logged in with focus-guarded PIN entry")
    else:
        print("\n>> FAILED — login did not complete")
        sys.exit(1)


if __name__ == "__main__":
    test_full_login_cycle()
    print("\n=== Integration test complete ===")
