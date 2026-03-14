/*
 * tusb_config.h — TinyUSB configuration for pywinhello
 *
 * Composite device: CDC (serial) + HID (keyboard)
 * Required by TinyUSB — must be on the include path.
 *
 * NOTE: Do NOT define CFG_TUSB_MCU, CFG_TUSB_OS, CFG_TUD_ENABLED,
 * or CFG_TUD_MAX_SPEED here. The Pico SDK sets these automatically
 * via the tinyusb_device / tinyusb_board CMake targets.
 */

#ifndef TUSB_CONFIG_H
#define TUSB_CONFIG_H

#ifdef __cplusplus
extern "C" {
#endif

/* ── Endpoint 0 max packet size ──────────────────────────────────── */

#ifndef CFG_TUD_ENDPOINT0_SIZE
#define CFG_TUD_ENDPOINT0_SIZE  64
#endif

/* ── Class enable ────────────────────────────────────────────────── */

#define CFG_TUD_CDC    1
#define CFG_TUD_HID    1
#define CFG_TUD_MSC    0
#define CFG_TUD_MIDI   0
#define CFG_TUD_VENDOR 0

/* ── CDC FIFO sizes ──────────────────────────────────────────────── */

#define CFG_TUD_CDC_RX_BUFSIZE  256
#define CFG_TUD_CDC_TX_BUFSIZE  256

/* ── HID buffer size ─────────────────────────────────────────────── */

#define CFG_TUD_HID_EP_BUFSIZE  16

#ifdef __cplusplus
}
#endif

#endif /* TUSB_CONFIG_H */
