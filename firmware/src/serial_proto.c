/*
 * serial_proto.c — Serial command protocol handler
 *
 * Text protocol over USB CDC serial:
 *   Request:  "COMMAND\n" or "COMMAND:payload\n"
 *   Response: "OK:response\n" or "ERR:message\n"
 *
 * When FLASH command is active, switches to binary receive mode.
 */

#include "serial_proto.h"
#include "hid.h"
#include "storage.h"
#include "bootloader.h"
#include "wifi.h"
#include "log.h"

#include "pico/stdlib.h"
#include "tusb.h"

#include <stdio.h>
#include <string.h>
#include <stdlib.h>

/* ── Internal state ───────────────────────────────────────────────── */

static char    _line_buf[SERIAL_LINE_MAX];
static size_t  _line_pos = 0;
static bool    _flash_mode = false;

/* ── Helpers ──────────────────────────────────────────────────────── */

static void cdc_write(const char *data, size_t len) {
    if (!tud_cdc_connected()) return;

    while (len > 0) {
        uint32_t avail = tud_cdc_write_available();
        if (avail == 0) {
            tud_cdc_write_flush();
            tud_task();
            continue;
        }
        uint32_t chunk = (len < avail) ? (uint32_t)len : avail;
        tud_cdc_write(data, chunk);
        data += chunk;
        len -= chunk;
    }
    tud_cdc_write_flush();
}

void serial_respond(const char *prefix, const char *message) {
    char buf[SERIAL_BUF_SIZE];
    int n;

    if (message && message[0] != '\0') {
        n = snprintf(buf, sizeof(buf), "%s:%s\n", prefix, message);
    } else {
        n = snprintf(buf, sizeof(buf), "%s\n", prefix);
    }

    if (n > 0) {
        cdc_write(buf, (size_t)n);
    }
}

void serial_send_raw(const char *data, size_t len) {
    cdc_write(data, len);
}

bool serial_in_flash_mode(void) {
    return _flash_mode;
}

/* ── Command parsing ──────────────────────────────────────────────── */

static command_id_t parse_command(const char *cmd) {
    if (strcmp(cmd, "PING")       == 0) return CMD_PING;
    if (strcmp(cmd, "GET_CONFIG") == 0) return CMD_GET_CONFIG;
    if (strcmp(cmd, "SET_CONFIG") == 0) return CMD_SET_CONFIG;
    if (strcmp(cmd, "SETUP_PIN")  == 0) return CMD_SETUP_PIN;
    if (strcmp(cmd, "CLEAR")      == 0) return CMD_CLEAR;
    if (strcmp(cmd, "UNLOCK")     == 0) return CMD_UNLOCK;
    if (strcmp(cmd, "HELLO")      == 0) return CMD_HELLO;
    if (strcmp(cmd, "TYPE")       == 0) return CMD_TYPE;
    if (strcmp(cmd, "PRESS")      == 0) return CMD_PRESS;
    if (strcmp(cmd, "GET_LOG")    == 0) return CMD_GET_LOG;
    if (strcmp(cmd, "FLASH")      == 0) return CMD_FLASH;
    if (strcmp(cmd, "STATUS")     == 0) return CMD_STATUS;
    if (strcmp(cmd, "BOOT_OK")    == 0) return CMD_BOOT_OK;
    return CMD_UNKNOWN;
}

static void split_command(char *line, char **cmd_out, char **payload_out) {
    *cmd_out = line;
    *payload_out = NULL;

    char *colon = strchr(line, ':');
    if (colon) {
        *colon = '\0';
        *payload_out = colon + 1;
    }
}

/* ── Command handlers ─────────────────────────────────────────────── */

static void handle_ping(void) {
    char resp[128];
    const char *dev_name;
    switch (g_state.device) {
    case DEVICE_PICO:     dev_name = "pico"; break;
    case DEVICE_PICO_W:   dev_name = "pico_w"; break;
    case DEVICE_PICO_2:   dev_name = "pico_2"; break;
    case DEVICE_PICO_2_W: dev_name = "pico_2_w"; break;
    default:              dev_name = "unknown"; break;
    }
    snprintf(resp, sizeof(resp), "%s,%s", dev_name, FW_VERSION_STRING);
    serial_respond("OK", resp);
}

static void handle_get_config(void) {
    char buf[SERIAL_BUF_SIZE];
    int n = storage_get_config_json(buf, sizeof(buf));
    if (n > 0) {
        serial_respond("OK", buf);
    } else {
        serial_respond("ERR", "config_read_failed");
    }
}

static void handle_set_config(const char *payload) {
    if (!payload || payload[0] == '\0') {
        serial_respond("ERR", "missing_payload");
        return;
    }

    if (storage_set_config_json(payload)) {
        serial_respond("OK", NULL);
    } else {
        serial_respond("ERR", "config_write_failed");
    }
}

static void handle_setup_pin(const char *payload) {
    if (!payload || payload[0] == '\0') {
        serial_respond("ERR", "missing_pin");
        return;
    }

    /* Validate: PIN should be digits only, 4-16 chars */
    size_t len = strlen(payload);
    if (len < 4 || len > PIN_MAX_LEN) {
        serial_respond("ERR", "invalid_pin_length");
        return;
    }
    for (size_t i = 0; i < len; i++) {
        if (payload[i] < '0' || payload[i] > '9') {
            serial_respond("ERR", "pin_must_be_digits");
            return;
        }
    }

    if (storage_save_pin(payload)) {
        serial_respond("OK", NULL);
    } else {
        serial_respond("ERR", "pin_store_failed");
    }
}

static void handle_clear(void) {
    if (storage_clear_all()) {
        log_clear();
        serial_respond("OK", NULL);
    } else {
        serial_respond("ERR", "clear_failed");
    }
}

static void handle_unlock(void) {
    /* UNLOCK = type stored PIN + Enter */
    char pin[PIN_MAX_LEN + 1];
    if (!storage_load_pin(pin, sizeof(pin))) {
        serial_respond("ERR", "no_pin_stored");
        return;
    }

    uint32_t start = to_ms_since_boot(get_absolute_time());

    if (!hid_type_string(pin)) {
        memset(pin, 0, sizeof(pin));
        serial_respond("ERR", "hid_not_ready");
        return;
    }

    /* Small delay before Enter */
    sleep_ms(g_state.config.dialog_wait_sec * 1000);

    hid_press_key(KEY_ENTER);
    memset(pin, 0, sizeof(pin));

    uint32_t dur = to_ms_since_boot(get_absolute_time()) - start;
    log_event(EVENT_HELLO, RESULT_SUCCESS, (uint16_t)dur, SOURCE_DAEMON);

    serial_respond("OK", NULL);
}

static void handle_hello(void) {
    /* HELLO = type stored PIN only, no Enter */
    char pin[PIN_MAX_LEN + 1];
    if (!storage_load_pin(pin, sizeof(pin))) {
        serial_respond("ERR", "no_pin_stored");
        return;
    }

    uint32_t start = to_ms_since_boot(get_absolute_time());

    if (!hid_type_string(pin)) {
        memset(pin, 0, sizeof(pin));
        serial_respond("ERR", "hid_not_ready");
        return;
    }

    memset(pin, 0, sizeof(pin));

    uint32_t dur = to_ms_since_boot(get_absolute_time()) - start;
    log_event(EVENT_HELLO, RESULT_SUCCESS, (uint16_t)dur, SOURCE_DAEMON);

    serial_respond("OK", NULL);
}

static void handle_type(const char *payload) {
    /* v1 compat: TYPE:text — type arbitrary text */
    if (!payload || payload[0] == '\0') {
        serial_respond("ERR", "missing_text");
        return;
    }

    if (hid_type_string(payload)) {
        serial_respond("OK", NULL);
    } else {
        serial_respond("ERR", "hid_not_ready");
    }
}

static void handle_press(const char *payload) {
    /* v1 compat: PRESS:keyname — press a special key */
    if (!payload || payload[0] == '\0') {
        serial_respond("ERR", "missing_key");
        return;
    }

    uint8_t keycode = 0;
    if (strcmp(payload, "ENTER")  == 0) keycode = KEY_ENTER;
    else if (strcmp(payload, "ESCAPE") == 0) keycode = KEY_ESCAPE;
    else if (strcmp(payload, "ESC")    == 0) keycode = KEY_ESCAPE;
    else if (strcmp(payload, "TAB")    == 0) keycode = KEY_TAB;
    else if (strcmp(payload, "SHIFT")  == 0) keycode = KEY_SHIFT_L;
    else {
        /* Try parsing as decimal keycode */
        int kc = atoi(payload);
        if (kc > 0 && kc <= 255) {
            keycode = (uint8_t)kc;
        }
    }

    if (keycode == 0) {
        serial_respond("ERR", "unknown_key");
        return;
    }

    if (hid_press_key(keycode)) {
        serial_respond("OK", NULL);
    } else {
        serial_respond("ERR", "hid_not_ready");
    }
}

static void handle_get_log(void) {
    char buf[SERIAL_BUF_SIZE];
    int n = storage_get_log_base64(buf, sizeof(buf));
    if (n >= 0) {
        serial_respond("OK", buf);
    } else {
        serial_respond("ERR", "log_read_failed");
    }
}

static void handle_flash(const char *payload) {
    if (!payload || payload[0] == '\0') {
        serial_respond("ERR", "missing_size");
        return;
    }

    uint32_t size = (uint32_t)strtoul(payload, NULL, 10);
    if (size == 0 || size > FLASH_PART_B_SIZE) {
        serial_respond("ERR", "invalid_size");
        return;
    }

    if (bootloader_start_flash(size)) {
        _flash_mode = true;
        serial_respond("READY", NULL);
    } else {
        serial_respond("ERR", "flash_init_failed");
    }
}

static void handle_status(void) {
    char buf[512];
    char wifi_status[64];
    wifi_status_string(wifi_status, sizeof(wifi_status));

    const boot_flags_t *flags = bootloader_get_flags();

    snprintf(buf, sizeof(buf),
        "{"
        "\"firmware\":\"%s\","
        "\"device\":\"%s\","
        "\"uptime\":%lu,"
        "\"pin_stored\":%s,"
        "\"wifi\":\"%s\","
        "\"ntp_epoch\":%lu,"
        "\"boot_unlock_done\":%s,"
        "\"active_partition\":%d,"
        "\"pending_verify\":%s,"
        "\"log_count\":%d"
        "}",
        FW_VERSION_STRING,
        g_state.config.device_str,
        (unsigned long)g_state.uptime_sec,
        g_state.pin_stored ? "true" : "false",
        wifi_status,
        (unsigned long)g_state.ntp_epoch,
        g_state.boot_unlock_done ? "true" : "false",
        flags ? flags->active_part : 0,
        (flags && flags->pending_verify) ? "true" : "false",
        log_count());

    serial_respond("OK", buf);
}

static void handle_boot_ok(void) {
    bootloader_confirm();
    serial_respond("OK", NULL);
}

/* ── Command dispatch ─────────────────────────────────────────────── */

static void dispatch_command(char *line) {
    char *cmd_str = NULL;
    char *payload = NULL;
    split_command(line, &cmd_str, &payload);

    command_id_t cmd = parse_command(cmd_str);

    /*
     * Any command from the daemon proves it's alive.
     * Cancel boot unlock if it hasn't fired yet.
     */
    if (cmd != CMD_UNKNOWN) {
        serial_cancel_boot_unlock();
    }

    switch (cmd) {
    case CMD_PING:       handle_ping(); break;
    case CMD_GET_CONFIG: handle_get_config(); break;
    case CMD_SET_CONFIG: handle_set_config(payload); break;
    case CMD_SETUP_PIN:  handle_setup_pin(payload); break;
    case CMD_CLEAR:      handle_clear(); break;
    case CMD_UNLOCK:     handle_unlock(); break;
    case CMD_HELLO:      handle_hello(); break;
    case CMD_TYPE:       handle_type(payload); break;
    case CMD_PRESS:      handle_press(payload); break;
    case CMD_GET_LOG:    handle_get_log(); break;
    case CMD_FLASH:      handle_flash(payload); break;
    case CMD_STATUS:     handle_status(); break;
    case CMD_BOOT_OK:    handle_boot_ok(); break;
    default:
        serial_respond("ERR", "unknown_command");
        break;
    }
}

/* ── Flash mode binary receive ────────────────────────────────────── */

static void process_flash_data(void) {
    uint8_t buf[512];
    uint32_t avail = tud_cdc_available();
    if (avail == 0) return;

    uint32_t to_read = MIN(avail, sizeof(buf));
    uint32_t n = tud_cdc_read(buf, to_read);

    if (n > 0) {
        if (!bootloader_feed_data(buf, n)) {
            /* Flash error: abort */
            _flash_mode = false;
            serial_respond("ERR", "flash_write_failed");
            return;
        }

        /* Report progress */
        static uint8_t last_progress = 0;
        uint8_t progress = bootloader_progress();
        if (progress / 10 > last_progress / 10) {
            char msg[16];
            snprintf(msg, sizeof(msg), "%d", progress);
            char line[32];
            snprintf(line, sizeof(line), "PROGRESS:%s\n", msg);
            cdc_write(line, strlen(line));
            last_progress = progress;
        }

        if (bootloader_is_complete()) {
            _flash_mode = false;
            last_progress = 0;

            if (bootloader_finalize()) {
                /* finalize() reboots on success, so we only get here on failure */
                serial_respond("ERR", "flash_verify_failed");
            }
        }
    }
}

/* ── Public API ───────────────────────────────────────────────────── */

void serial_init(void) {
    _line_pos = 0;
    _flash_mode = false;
    memset(_line_buf, 0, sizeof(_line_buf));
}

void serial_cancel_boot_unlock(void) {
    g_state.boot_unlock_cancelled = true;
}

void serial_task(void) {
    if (!tud_cdc_connected() || !tud_cdc_available()) {
        return;
    }

    /* In flash mode, receive raw binary */
    if (_flash_mode) {
        process_flash_data();
        return;
    }

    /* Normal text mode: read bytes into line buffer */
    while (tud_cdc_available()) {
        char c;
        if (tud_cdc_read(&c, 1) != 1) break;

        if (c == '\n' || c == '\r') {
            if (_line_pos > 0) {
                _line_buf[_line_pos] = '\0';
                dispatch_command(_line_buf);
                _line_pos = 0;
            }
        } else if (_line_pos < SERIAL_LINE_MAX - 1) {
            _line_buf[_line_pos++] = c;
        } else {
            /* Line too long: discard and report error */
            _line_pos = 0;
            serial_respond("ERR", "line_too_long");
        }
    }
}
