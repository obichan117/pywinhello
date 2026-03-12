/*
 * hid.c — USB HID keyboard implementation
 *
 * Uses TinyUSB device stack to send keyboard reports.
 * Supports typing digits, letters, and special keys.
 */

#include "hid.h"

#include "pico/stdlib.h"
#include "tusb.h"

#include <string.h>

/* ── Internal state ───────────────────────────────────────────────── */

static bool _report_pending = false;

/* ── Keycode lookup tables ────────────────────────────────────────── */

/*
 * Map ASCII characters to HID keycodes.
 * Returns {keycode, modifier} pair.
 * Modifier: 0 = none, KEYBOARD_MODIFIER_LEFTSHIFT = shift held.
 */
typedef struct {
    uint8_t keycode;
    uint8_t modifier;
} keymap_entry_t;

static keymap_entry_t ascii_to_hid(char c) {
    keymap_entry_t entry = {0, 0};

    if (c >= 'a' && c <= 'z') {
        entry.keycode = HID_KEY_A + (c - 'a');
    } else if (c >= 'A' && c <= 'Z') {
        entry.keycode = HID_KEY_A + (c - 'A');
        entry.modifier = KEYBOARD_MODIFIER_LEFTSHIFT;
    } else if (c >= '1' && c <= '9') {
        entry.keycode = HID_KEY_1 + (c - '1');
    } else if (c == '0') {
        entry.keycode = HID_KEY_0;
    } else {
        /* Common punctuation */
        switch (c) {
        case ' ':  entry.keycode = HID_KEY_SPACE; break;
        case '\n': entry.keycode = HID_KEY_ENTER; break;
        case '\t': entry.keycode = HID_KEY_TAB; break;
        case '-':  entry.keycode = HID_KEY_MINUS; break;
        case '=':  entry.keycode = HID_KEY_EQUAL; break;
        case '[':  entry.keycode = HID_KEY_BRACKET_LEFT; break;
        case ']':  entry.keycode = HID_KEY_BRACKET_RIGHT; break;
        case '\\': entry.keycode = HID_KEY_BACKSLASH; break;
        case ';':  entry.keycode = HID_KEY_SEMICOLON; break;
        case '\'': entry.keycode = HID_KEY_APOSTROPHE; break;
        case ',':  entry.keycode = HID_KEY_COMMA; break;
        case '.':  entry.keycode = HID_KEY_PERIOD; break;
        case '/':  entry.keycode = HID_KEY_SLASH; break;
        case '!':  entry.keycode = HID_KEY_1; entry.modifier = KEYBOARD_MODIFIER_LEFTSHIFT; break;
        case '@':  entry.keycode = HID_KEY_2; entry.modifier = KEYBOARD_MODIFIER_LEFTSHIFT; break;
        case '#':  entry.keycode = HID_KEY_3; entry.modifier = KEYBOARD_MODIFIER_LEFTSHIFT; break;
        case '$':  entry.keycode = HID_KEY_4; entry.modifier = KEYBOARD_MODIFIER_LEFTSHIFT; break;
        case '%':  entry.keycode = HID_KEY_5; entry.modifier = KEYBOARD_MODIFIER_LEFTSHIFT; break;
        case '^':  entry.keycode = HID_KEY_6; entry.modifier = KEYBOARD_MODIFIER_LEFTSHIFT; break;
        case '&':  entry.keycode = HID_KEY_7; entry.modifier = KEYBOARD_MODIFIER_LEFTSHIFT; break;
        case '*':  entry.keycode = HID_KEY_8; entry.modifier = KEYBOARD_MODIFIER_LEFTSHIFT; break;
        case '(':  entry.keycode = HID_KEY_9; entry.modifier = KEYBOARD_MODIFIER_LEFTSHIFT; break;
        case ')':  entry.keycode = HID_KEY_0; entry.modifier = KEYBOARD_MODIFIER_LEFTSHIFT; break;
        default:   break; /* Unsupported character, skip */
        }
    }

    return entry;
}

/* ── Send a single HID report and wait for completion ─────────────── */

static bool send_key_report(uint8_t modifier, uint8_t keycode) {
    if (!tud_hid_ready()) {
        return false;
    }

    uint8_t keycodes[6] = {keycode, 0, 0, 0, 0, 0};
    _report_pending = true;
    tud_hid_keyboard_report(1, modifier, keycodes);

    /* Wait for report to be sent (with timeout) */
    uint32_t start = to_ms_since_boot(get_absolute_time());
    while (_report_pending) {
        tud_task();
        if (to_ms_since_boot(get_absolute_time()) - start > 50) {
            _report_pending = false;
            break;
        }
    }

    return true;
}

static bool send_release_report(void) {
    if (!tud_hid_ready()) {
        return false;
    }

    _report_pending = true;
    tud_hid_keyboard_report(1, 0, NULL);

    uint32_t start = to_ms_since_boot(get_absolute_time());
    while (_report_pending) {
        tud_task();
        if (to_ms_since_boot(get_absolute_time()) - start > 50) {
            _report_pending = false;
            break;
        }
    }

    return true;
}

/* ── TinyUSB HID callbacks ────────────────────────────────────────── */

void tud_hid_report_complete_cb(uint8_t instance, uint8_t const *report,
                                 uint16_t len) {
    (void)instance;
    (void)report;
    (void)len;
    _report_pending = false;
}

/* Called when host sends SET_REPORT (e.g., LED status) */
void tud_hid_set_report_cb(uint8_t instance, uint8_t report_id,
                            hid_report_type_t report_type,
                            uint8_t const *buffer, uint16_t bufsize) {
    (void)instance;
    (void)report_id;
    (void)report_type;
    (void)buffer;
    (void)bufsize;
    /* We don't use LED indicators, ignore. */
}

/* Called when host sends GET_REPORT */
uint16_t tud_hid_get_report_cb(uint8_t instance, uint8_t report_id,
                                hid_report_type_t report_type,
                                uint8_t *buffer, uint16_t reqlen) {
    (void)instance;
    (void)report_id;
    (void)report_type;
    (void)buffer;
    (void)reqlen;
    return 0;
}

/* ── Public API ───────────────────────────────────────────────────── */

void hid_init(void) {
    _report_pending = false;
}

bool hid_is_ready(void) {
    return tud_mounted() && tud_hid_ready();
}

bool hid_type_char(char c) {
    if (!hid_is_ready()) {
        return false;
    }

    keymap_entry_t key = ascii_to_hid(c);
    if (key.keycode == 0) {
        return false;  /* Unsupported character */
    }

    /* Press key */
    if (!send_key_report(key.modifier, key.keycode)) {
        return false;
    }

    /* Release key */
    send_release_report();

    return true;
}

bool hid_type_string(const char *text) {
    if (!text || !hid_is_ready()) {
        return false;
    }

    uint32_t delay_ms = g_state.config.keystroke_ms;
    if (delay_ms == 0) delay_ms = 50;  /* Default 50ms between keys */

    for (const char *p = text; *p != '\0'; p++) {
        if (!hid_type_char(*p)) {
            return false;
        }
        sleep_ms(delay_ms);
    }

    return true;
}

bool hid_press_key(uint8_t keycode) {
    if (!hid_is_ready()) {
        return false;
    }

    uint8_t modifier = 0;

    /* If it's a modifier key, send as modifier instead of keycode */
    if (keycode >= 0xE0 && keycode <= 0xE7) {
        modifier = 1 << (keycode - 0xE0);
        keycode = 0;
    }

    if (!send_key_report(modifier, keycode)) {
        return false;
    }

    send_release_report();
    return true;
}

bool hid_press_shift(void) {
    return hid_press_key(KEY_SHIFT_L);
}

bool hid_remote_wakeup(void) {
    if (!tud_mounted()) {
        return false;
    }

    if (tud_suspended()) {
        return tud_remote_wakeup();
    }

    return false;  /* Not suspended, no wakeup needed */
}

void hid_task(void) {
    /* Currently no periodic HID work needed.
     * TinyUSB handles polling via tud_task() in main loop. */
}
