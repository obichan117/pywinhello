"""USB HID keyboard bridge via Raspberry Pi Pico.

Sends keystrokes to the OS via a Pico connected over USB, appearing as
a physical keyboard. This bypasses UIPI restrictions that block software
input (SendInput / pyautogui / pywinauto) from reaching protected dialogs
like Windows Security (Windows Hello PIN).

Protocol (text, newline-delimited)::

    PING         -> PONG
    TYPE:1234    -> OK
    PRESS:ENTER  -> OK
    COMBO:CTRL+C -> OK
    DELAY:100    -> OK
    error        -> ERR:message
"""

from __future__ import annotations

import logging
import threading

import serial
from serial.tools import list_ports

logger = logging.getLogger(__name__)

# Raspberry Pi Pico CircuitPython USB identifiers (Adafruit VID)
_PICO_VID = 0x239A
_PICO_PIDS = {
    0x8058,  # Pico W
    0x8120,  # Pico W (alt)
    0x80F4,  # Pico (non-W)
    0x8150,  # Pico 2 (non-W)
    0x8160,  # Pico 2 W
}


def find_pico_port() -> str | None:
    """Auto-detect the Pico CDC data serial port by VID:PID.

    When boot.py enables two CDC channels (console + data), the data port
    has the higher USB location index. We pick the highest-numbered COM port.

    Returns:
        COM port name (e.g. "COM8") or None.
    """
    ports = list_ports.comports()
    logger.debug("Scanning %d COM ports for Pico", len(ports))

    candidates = [p for p in ports if p.vid == _PICO_VID and p.pid in _PICO_PIDS]
    if candidates:
        best = max(candidates, key=lambda p: p.device)
        logger.info("Found Pico on %s (pid=0x%04X)", best.device, best.pid)
        return best.device

    for p in ports:
        if p.vid == _PICO_VID:
            logger.info("Found Pico (VID match) on %s: %s", p.device, p.description)
            return p.device

    logger.debug("No Pico found among: %s", [(p.device, p.vid, p.pid) for p in ports])
    return None


class HIDKeyboard:
    """USB HID keyboard bridge over serial.

    Communicates with a Pico running CircuitPython firmware via text
    protocol over CDC serial.

    Usage::

        with HIDKeyboard() as kb:
            kb.type_text("1234")
            kb.press_key("ENTER")
    """

    def __init__(
        self,
        port: str | None = None,
        baud_rate: int = 115200,
        timeout: float = 2.0,
    ) -> None:
        if port is None:
            port = find_pico_port()
            if port is None:
                raise ConnectionError("Pico not found. Is it connected and running CircuitPython?")

        self._port_name = port
        self._serial = serial.Serial(
            port=port,
            baudrate=baud_rate,
            timeout=timeout,
            write_timeout=timeout,
        )
        self._lock = threading.Lock()
        logger.info("HID bridge connected on %s @ %d baud", port, baud_rate)

    def __enter__(self) -> HIDKeyboard:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _send(self, command: str) -> str:
        """Send a command and return the response line."""
        with self._lock:
            self._serial.reset_input_buffer()
            self._serial.write(f"{command}\n".encode())
            self._serial.flush()
            raw = self._serial.readline()
            if not raw:
                raise TimeoutError(f"No response from Pico for: {command}")
            resp = raw.decode().strip()
            if resp.startswith("ERR:"):
                raise RuntimeError(resp[4:])
            return resp

    def ping(self) -> bool:
        """Health check."""
        try:
            return self._send("PING") == "PONG"
        except Exception:
            return False

    def type_text(self, text: str) -> None:
        """Type a string of characters."""
        if not text:
            return
        resp = self._send(f"TYPE:{text}")
        if resp != "OK":
            raise RuntimeError(f"Unexpected TYPE response: {resp}")

    def press_key(self, key: str) -> None:
        """Press and release a named key (e.g. 'ENTER', 'TAB')."""
        resp = self._send(f"PRESS:{key}")
        if resp != "OK":
            raise RuntimeError(f"Unexpected PRESS response: {resp}")

    def key_combo(self, *keys: str) -> None:
        """Press keys simultaneously (e.g. 'CTRL', 'C')."""
        resp = self._send(f"COMBO:{'+'.join(keys)}")
        if resp != "OK":
            raise RuntimeError(f"Unexpected COMBO response: {resp}")

    def set_delay(self, delay_ms: int) -> None:
        """Set inter-key delay on the Pico (milliseconds)."""
        resp = self._send(f"DELAY:{delay_ms}")
        if resp != "OK":
            raise RuntimeError(f"Unexpected DELAY response: {resp}")

    def close(self) -> None:
        """Release the serial port."""
        if self._serial and self._serial.is_open:
            self._serial.close()
            logger.info("HID bridge disconnected from %s", self._port_name)
