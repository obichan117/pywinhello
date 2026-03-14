/*
 * tusb_config.h — Absolute minimal config for CDC-only test
 *
 * Only defines class-level config. All hardware/OS settings
 * are left to the SDK's compile definitions on tinyusb_device.
 */

#ifndef TUSB_CONFIG_H
#define TUSB_CONFIG_H

/* Class enable — CDC only */
#define CFG_TUD_CDC    1
#define CFG_TUD_HID    0
#define CFG_TUD_MSC    0
#define CFG_TUD_MIDI   0
#define CFG_TUD_VENDOR 0

/* CDC FIFO sizes */
#define CFG_TUD_CDC_RX_BUFSIZE  256
#define CFG_TUD_CDC_TX_BUFSIZE  256

#endif
