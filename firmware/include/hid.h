/*
 * hid.h — USB HID keyboard interface
 *
 * Provides functions to type characters and press special keys
 * over USB HID. Uses TinyUSB device stack.
 */

#ifndef HID_H
#define HID_H

#include "pywinhello.h"

/* ── Special key codes ────────────────────────────────────────────── */

typedef enum {
    KEY_NONE    = 0x00,
    KEY_ENTER   = 0x28,
    KEY_ESCAPE  = 0x29,
    KEY_TAB     = 0x2B,
    KEY_SHIFT_L = 0xE1,
    KEY_CTRL_L  = 0xE0,
    KEY_ALT_L   = 0xE2,
} special_key_t;

/* ── Public API ───────────────────────────────────────────────────── */

/**
 * Initialize HID subsystem. Call once after USB init.
 */
void hid_init(void);

/**
 * Type a string of characters via HID keyboard reports.
 * Supports digits 0-9, lowercase a-z, and common punctuation.
 * Inter-key delay is taken from g_state.config.keystroke_ms.
 *
 * @param text  Null-terminated string to type
 * @return true on success, false if USB not ready
 */
bool hid_type_string(const char *text);

/**
 * Type a single character.
 */
bool hid_type_char(char c);

/**
 * Press and release a special key (Enter, Escape, Tab, Shift, etc.).
 *
 * @param keycode  HID usage code (see special_key_t or raw USB HID codes)
 * @return true on success
 */
bool hid_press_key(uint8_t keycode);

/**
 * Press Shift key (useful for waking lock screen).
 */
bool hid_press_shift(void);

/**
 * Send USB remote wakeup signal (wake PC from S3 sleep).
 * Requires remote wakeup enabled in descriptor and host permission.
 */
bool hid_remote_wakeup(void);

/**
 * Check if HID device is mounted and ready to send reports.
 */
bool hid_is_ready(void);

/**
 * Called from main loop to process HID tasks.
 */
void hid_task(void);

#endif /* HID_H */
