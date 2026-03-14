/*
 * test_tusb_config.h — Minimal TinyUSB config for CDC-only test
 */

#ifndef TUSB_CONFIG_H
#define TUSB_CONFIG_H

#ifdef __cplusplus
extern "C" {
#endif

#ifndef CFG_TUSB_MCU
#define CFG_TUSB_MCU  OPT_MCU_RP2040
#endif

#ifndef CFG_TUSB_OS
#define CFG_TUSB_OS   OPT_OS_PICO
#endif

#ifndef CFG_TUD_ENABLED
#define CFG_TUD_ENABLED  1
#endif

#ifndef CFG_TUD_MAX_SPEED
#define CFG_TUD_MAX_SPEED  OPT_MODE_FULL_SPEED
#endif

#ifndef CFG_TUD_ENDPOINT0_SIZE
#define CFG_TUD_ENDPOINT0_SIZE  64
#endif

/* CDC only — no HID */
#define CFG_TUD_CDC    1
#define CFG_TUD_HID    0
#define CFG_TUD_MSC    0
#define CFG_TUD_MIDI   0
#define CFG_TUD_VENDOR 0

#define CFG_TUD_CDC_RX_BUFSIZE  256
#define CFG_TUD_CDC_TX_BUFSIZE  256

#ifdef __cplusplus
}
#endif

#endif
