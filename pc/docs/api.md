# API Reference

## Serial Protocol

The serial package handles all PC ↔ Pico communication.

**Why callback-based?** The monitor service owns the serial connection. Subsystems (lock detector, hello detector) receive callbacks rather than direct serial access, preventing thread contention and making testing straightforward.

::: pywinhello.serial.protocol.SerialProtocol

::: pywinhello.serial.protocol.Command

::: pywinhello.serial.protocol.Response

::: pywinhello.serial.protocol.PingInfo

::: pywinhello.serial.device.PicoDevice

::: pywinhello.serial.device.ConnectionState

::: pywinhello.serial.device.find_pico_port

::: pywinhello.serial.flasher.flash_firmware

::: pywinhello.serial.flasher.FlashResult

## Monitor

The monitor package runs as an invisible background process.

**Why separate subsystems?** Each detector has independent lifecycle, failure modes, and threading requirements. The service orchestrator creates and destroys them on USB plug/unplug.

::: pywinhello.monitor.service.MonitorService

::: pywinhello.monitor.usb_watcher.USBWatcher

::: pywinhello.monitor.lock_detector.LockDetector

::: pywinhello.monitor.lock_detector.LockConfig

::: pywinhello.monitor.hello_detector.HelloDetector

::: pywinhello.monitor.hello_detector.AppWhitelist

::: pywinhello.monitor.scheduler_sync.sync_schedule

::: pywinhello.monitor.updater.AutoUpdater

::: pywinhello.monitor.updater.check_for_updates

## Setup

First-run firmware flashing for Pico in BOOTSEL mode.

::: pywinhello.setup.find_bootsel_drive

::: pywinhello.setup.flash_uf2

::: pywinhello.setup.list_bundled_firmware

## Models

::: pywinhello.models.AuthEvent

## Dialog Detection

::: pywinhello.dialog.is_visible

::: pywinhello.dialog.focus

::: pywinhello.dialog.wait_for_dialog

::: pywinhello.dialog.wait_for_dismiss

::: pywinhello.dialog.get_owner_exe
