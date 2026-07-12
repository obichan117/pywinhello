/*
 * tusb_config.h — CDC-only TinyUSB configuration
 *
 * Follows the official pico-examples/usb/device pattern.
 * CFG_TUSB_MCU is provided by the SDK as a compiler definition.
 */

#ifndef TUSB_CONFIG_H
#define TUSB_CONFIG_H

#ifdef __cplusplus
 extern "C" {
#endif

/* ── Board ─────────────────────────────────────────────────────── */

#ifndef BOARD_TUD_RHPORT
#define BOARD_TUD_RHPORT      0
#endif

#ifndef BOARD_TUD_MAX_SPEED
#define BOARD_TUD_MAX_SPEED   OPT_MODE_DEFAULT_SPEED
#endif

/* ── Common ────────────────────────────────────────────────────── */

/* CFG_TUSB_MCU is set by the SDK's CMake targets — do not define here */

#ifndef CFG_TUSB_OS
#define CFG_TUSB_OS           OPT_OS_NONE
#endif

#ifndef CFG_TUSB_DEBUG
#define CFG_TUSB_DEBUG        0
#endif

#define CFG_TUD_ENABLED       1
#define CFG_TUD_MAX_SPEED     BOARD_TUD_MAX_SPEED

#ifndef CFG_TUSB_MEM_SECTION
#define CFG_TUSB_MEM_SECTION
#endif

#ifndef CFG_TUSB_MEM_ALIGN
#define CFG_TUSB_MEM_ALIGN    __attribute__((aligned(4)))
#endif

/* ── Device ────────────────────────────────────────────────────── */

#ifndef CFG_TUD_ENDPOINT0_SIZE
#define CFG_TUD_ENDPOINT0_SIZE  64
#endif

/* ── Classes ───────────────────────────────────────────────────── */

#define CFG_TUD_CDC    1
#define CFG_TUD_HID    0
#define CFG_TUD_MSC    0
#define CFG_TUD_MIDI   0
#define CFG_TUD_VENDOR 0

/* CDC FIFO sizes */
#define CFG_TUD_CDC_RX_BUFSIZE  256
#define CFG_TUD_CDC_TX_BUFSIZE  256

#ifdef __cplusplus
 }
#endif

#endif /* TUSB_CONFIG_H */
