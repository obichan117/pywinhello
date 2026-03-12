# API Reference

## v2 Modules

### Serial Protocol

The serial package handles all PC ↔ Pico communication.

**Why callback-based?** The monitor service owns the serial connection. Subsystems (lock detector, hello detector) receive callbacks rather than direct serial access, preventing thread contention and making testing straightforward.

::: pywinhello.serial.protocol.SerialProtocol

::: pywinhello.serial.protocol.Command

::: pywinhello.serial.protocol.Response

::: pywinhello.serial.protocol.PingInfo

::: pywinhello.serial.device.PicoDevice

::: pywinhello.serial.device.ConnectionState

::: pywinhello.serial.flasher.flash_firmware

::: pywinhello.serial.flasher.FlashResult

### Monitor

The monitor package runs as an invisible background process.

**Why separate subsystems?** Each detector has independent lifecycle, failure modes, and threading requirements. The service orchestrator creates and destroys them on USB plug/unplug.

::: pywinhello.monitor.service.MonitorService

::: pywinhello.monitor.usb_watcher.USBWatcher

::: pywinhello.monitor.lock_detector.LockDetector

::: pywinhello.monitor.lock_detector.LockConfig

::: pywinhello.monitor.hello_detector.HelloDetector

::: pywinhello.monitor.hello_detector.AppWhitelist

::: pywinhello.monitor.scheduler_sync.sync_schedule

::: pywinhello.monitor.scheduler_sync.enable_wake_timers

::: pywinhello.monitor.updater.AutoUpdater

::: pywinhello.monitor.updater.check_for_updates

## v1 Modules (still available)

### Top-level functions

::: pywinhello.pin.enter_pin

::: pywinhello.config.load_config

### Models

::: pywinhello.models.AuthEvent

::: pywinhello.models.AppConfig

::: pywinhello.models.MonitorConfig

### Monitor (v1)

::: pywinhello.monitor.HelloMonitor

### HID Keyboard

::: pywinhello.hid.HIDKeyboard

::: pywinhello.hid.find_pico_port

### Dialog Detection

::: pywinhello.dialog.is_visible

::: pywinhello.dialog.focus

::: pywinhello.dialog.wait_for_dialog

::: pywinhello.dialog.wait_for_dismiss

::: pywinhello.dialog.get_owner_exe

### Pico Setup (v1)

::: pywinhello.setup.run_setup

::: pywinhello.setup.verify_pico
