"""Windows Security dialog detection and interaction via ctypes.

The Credential Dialog Xaml Host is protected by UIPI, so pywinauto/UIA
cannot interact with it. We detect presence via FindWindowW and identify
the owning process via GetWindow/GetWindowThreadProcessId.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import logging
import time

logger = logging.getLogger(__name__)

_CREDENTIAL_DIALOG_CLASS = "Credential Dialog Xaml Host"

# Win32 constants
_GW_OWNER = 4


def find_dialog_hwnd() -> int:
    """Return the HWND of the Windows Security dialog, or 0 if not found."""
    return ctypes.windll.user32.FindWindowW(_CREDENTIAL_DIALOG_CLASS, None)


def is_visible() -> bool:
    """Check if the Windows Security dialog is currently visible."""
    return find_dialog_hwnd() != 0


def focus() -> bool:
    """Bring the Windows Security dialog to the foreground.

    HID keystrokes go to the focused window, so the credential dialog
    must have focus before sending PIN input.

    Uses AttachThreadInput to bypass Windows' foreground lock restriction.
    Without this, SetForegroundWindow silently fails when the calling
    process doesn't own the current foreground window.

    Returns:
        True if the dialog was found and focused.
    """
    hwnd = find_dialog_hwnd()
    if not hwnd:
        return False

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    fg_hwnd = user32.GetForegroundWindow()
    fg_tid = user32.GetWindowThreadProcessId(fg_hwnd, None)
    my_tid = kernel32.GetCurrentThreadId()

    attached = False
    if fg_tid != my_tid:
        attached = bool(user32.AttachThreadInput(my_tid, fg_tid, True))

    user32.BringWindowToTop(hwnd)
    user32.ShowWindow(hwnd, 5)  # SW_SHOW
    result = user32.SetForegroundWindow(hwnd)

    if attached:
        user32.AttachThreadInput(my_tid, fg_tid, False)

    if result:
        logger.info("Focused Windows Security dialog (hwnd=%d)", hwnd)
    else:
        logger.warning("SetForegroundWindow failed for hwnd=%d", hwnd)
    return bool(result)


def get_owner_exe(hwnd: int | None = None) -> str | None:
    """Identify which process triggered the Windows Security dialog.

    Uses GetWindow(GW_OWNER) to find the owner window, then
    GetWindowThreadProcessId to get the PID, then OpenProcess +
    QueryFullProcessImageNameW to get the exe name.

    Args:
        hwnd: Dialog HWND. If None, finds it automatically.

    Returns:
        Executable name (e.g. 'MarketSpeed2.exe') or None.
    """
    if hwnd is None:
        hwnd = find_dialog_hwnd()
    if not hwnd:
        return None

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    owner_hwnd = user32.GetWindow(hwnd, _GW_OWNER)
    if not owner_hwnd:
        return None

    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(owner_hwnd, ctypes.byref(pid))
    if not pid.value:
        return None

    # Open process to query its image name
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid.value)
    if not handle:
        return None

    try:
        buf = ctypes.create_unicode_buffer(260)
        size = wintypes.DWORD(260)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            full_path = buf.value
            return full_path.rsplit("\\", 1)[-1] if "\\" in full_path else full_path
    finally:
        kernel32.CloseHandle(handle)

    return None


def is_foreground() -> bool:
    """Check if the Windows Security dialog is the current foreground window.

    Returns:
        True if the credential dialog has focus (is the foreground window).
    """
    hwnd = find_dialog_hwnd()
    if not hwnd:
        return False
    fg_hwnd = ctypes.windll.user32.GetForegroundWindow()
    return hwnd == fg_hwnd


def wait_for_dialog(timeout: float = 10.0, poll_interval: float = 0.5) -> bool:
    """Poll until the Windows Security dialog appears or timeout.

    Returns:
        True if the dialog appeared within the timeout.
    """
    start = time.time()
    while time.time() - start < timeout:
        if is_visible():
            logger.info("Windows Security dialog detected after %.1fs", time.time() - start)
            return True
        time.sleep(poll_interval)
    logger.warning("Windows Security dialog not found within %.1fs", timeout)
    return False


def wait_for_dismiss(timeout: float = 30.0, poll_interval: float = 0.5) -> bool:
    """Poll until the Windows Security dialog disappears or timeout.

    Returns:
        True if the dialog disappeared within the timeout.
    """
    start = time.time()
    while time.time() - start < timeout:
        if not is_visible():
            logger.info("Windows Security dialog dismissed after %.1fs", time.time() - start)
            return True
        time.sleep(poll_interval)
    logger.warning("Windows Security dialog still present after %.1fs", timeout)
    return False
