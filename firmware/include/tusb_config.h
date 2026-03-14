/*
 * tusb_config.h — TinyUSB configuration for pywinhello
 *
 * Composite device: CDC (serial) + HID (keyboard)
 * Required by TinyUSB — must be on the include path.
 *
 * Uses #ifndef guards for MCU/OS/speed so the Pico SDK's values
 * take precedence when provided via compile definitions.
 */

#ifndef TUSB_CONFIG_H
#define TUSB_CONFIG_H

#ifdef __cplusplus
extern "C" {
#endif

/* ── Board / MCU (fallbacks — SDK may override via compile defs) ── */

#ifndef CFG_TUSB_MCU
#define CFG_TUSB_MCU  OPT_MCU_RP2040
#endif

#ifndef CFG_TUSB_OS
#define CFG_TUSB_OS   OPT_OS_PICO
#endif

/* ── USB device configuration ────────────────────────────────────── */

#ifndef CFG_TUD_ENABLED
#define CFG_TUD_ENABLED  1
#endif

#ifndef CFG_TUD_MAX_SPEED
#define CFG_TUD_MAX_SPEED  OPT_MODE_FULL_SPEED
#endif

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
