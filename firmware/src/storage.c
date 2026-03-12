/*
 * storage.c — LittleFS flash storage for config, PIN, and logs
 *
 * Uses the last 256KB of Pico flash for a LittleFS filesystem.
 * Files:
 *   /config.json  — Device configuration
 *   /pin.enc      — Encrypted PIN (AES-256-CBC)
 *   /log.bin      — Circular event log (header + entries)
 */

#include "storage.h"
#include "crypto.h"
#include "log.h"

#include "pico/stdlib.h"
#include "hardware/flash.h"
#include "hardware/sync.h"

#include "lfs.h"

#include <stdio.h>
#include <string.h>
#include <stdlib.h>

/* ── LittleFS configuration ──────────────────────────────────────── */

#define FS_BLOCK_COUNT  (FLASH_FS_SIZE / FLASH_SECTOR_SIZE)

static lfs_t        _lfs;
static bool         _mounted = false;
static uint8_t      _read_buf[FLASH_PAGE_SIZE];
static uint8_t      _prog_buf[FLASH_PAGE_SIZE];
static uint8_t      _lookahead_buf[16];

/* Flash base address for LittleFS region */
#define FS_FLASH_BASE  (XIP_BASE + FLASH_FS_OFFSET)

/* ── LittleFS block device callbacks ──────────────────────────────── */

static int lfs_read(const struct lfs_config *c, lfs_block_t block,
                    lfs_off_t off, void *buffer, lfs_size_t size) {
    (void)c;
    uint32_t addr = FLASH_FS_OFFSET + (block * FLASH_SECTOR_SIZE) + off;
    memcpy(buffer, (const void *)(XIP_BASE + addr), size);
    return 0;
}

static int lfs_prog(const struct lfs_config *c, lfs_block_t block,
                    lfs_off_t off, const void *buffer, lfs_size_t size) {
    (void)c;
    uint32_t addr = FLASH_FS_OFFSET + (block * FLASH_SECTOR_SIZE) + off;
    uint32_t ints = save_and_disable_interrupts();
    flash_range_program(addr, (const uint8_t *)buffer, size);
    restore_interrupts(ints);
    return 0;
}

static int lfs_erase(const struct lfs_config *c, lfs_block_t block) {
    (void)c;
    uint32_t addr = FLASH_FS_OFFSET + (block * FLASH_SECTOR_SIZE);
    uint32_t ints = save_and_disable_interrupts();
    flash_range_erase(addr, FLASH_SECTOR_SIZE);
    restore_interrupts(ints);
    return 0;
}

static int lfs_sync(const struct lfs_config *c) {
    (void)c;
    return 0;
}

static const struct lfs_config _lfs_cfg = {
    .read        = lfs_read,
    .prog        = lfs_prog,
    .erase       = lfs_erase,
    .sync        = lfs_sync,
    .read_size   = FLASH_PAGE_SIZE,
    .prog_size   = FLASH_PAGE_SIZE,
    .block_size  = FLASH_SECTOR_SIZE,
    .block_count = FS_BLOCK_COUNT,
    .cache_size  = FLASH_PAGE_SIZE,
    .lookahead_size = sizeof(_lookahead_buf),
    .block_cycles   = 500,
    .read_buffer       = _read_buf,
    .prog_buffer       = _prog_buf,
    .lookahead_buffer  = _lookahead_buf,
};

/* ── Raw file helpers ─────────────────────────────────────────────── */

static int fs_read_file(const char *path, void *buf, size_t maxlen) {
    if (!_mounted) return -1;

    lfs_file_t file;
    int err = lfs_file_open(&_lfs, &file, path, LFS_O_RDONLY);
    if (err < 0) return -1;

    lfs_ssize_t n = lfs_file_read(&_lfs, &file, buf, maxlen);
    lfs_file_close(&_lfs, &file);
    return (int)n;
}

static int fs_write_file(const char *path, const void *buf, size_t len) {
    if (!_mounted) return -1;

    lfs_file_t file;
    int err = lfs_file_open(&_lfs, &file, path,
                            LFS_O_WRONLY | LFS_O_CREAT | LFS_O_TRUNC);
    if (err < 0) return -1;

    lfs_ssize_t n = lfs_file_write(&_lfs, &file, buf, len);
    lfs_file_close(&_lfs, &file);
    return (n == (lfs_ssize_t)len) ? 0 : -1;
}

static int fs_delete_file(const char *path) {
    if (!_mounted) return -1;
    return lfs_remove(&_lfs, path);
}

/* ── JSON config serialization (minimal, hand-rolled) ─────────────── */

/*
 * We use a simple hand-written JSON serializer/parser to avoid
 * pulling in a full JSON library. The config schema is fixed.
 */

static void config_set_defaults(config_t *cfg) {
    memset(cfg, 0, sizeof(config_t));
    cfg->version = 2;
    snprintf(cfg->firmware, sizeof(cfg->firmware), "%s", FW_VERSION_STRING);
    snprintf(cfg->device_str, sizeof(cfg->device_str), "unknown");
    snprintf(cfg->locale, sizeof(cfg->locale), "ja");

    /* Schedule: weekdays at 07:45 */
    cfg->schedule_hour = 7;
    cfg->schedule_min  = 45;
    cfg->schedule_days = 0x3E;  /* bits 1-5 = Mon-Fri */

    /* Timing defaults */
    cfg->boot_wait_sec     = 45;
    cfg->wake_wait_sec     = 5;
    cfg->keystroke_ms      = 50;
    cfg->retry_count       = 3;
    cfg->retry_interval_sec = 10;
    cfg->dialog_wait_sec   = 1;

    /* Default apps */
    cfg->app_count = 2;
    snprintf(cfg->apps[0].name, CONFIG_APP_NAME_LEN, "lock_screen");
    cfg->apps[0].enabled = true;
    snprintf(cfg->apps[1].name, CONFIG_APP_NAME_LEN, "MarketSpeed2.exe");
    cfg->apps[1].enabled = true;
}

static int config_to_json(const config_t *cfg, char *buf, size_t buflen) {
    int n = snprintf(buf, buflen,
        "{"
        "\"version\":%d,"
        "\"firmware\":\"%s\","
        "\"device\":\"%s\","
        "\"locale\":\"%s\","
        "\"schedule\":{\"time\":\"%02d:%02d\",\"days\":[",
        cfg->version, cfg->firmware, cfg->device_str,
        cfg->locale, cfg->schedule_hour, cfg->schedule_min);

    /* Days array: day numbers where bits are set */
    bool first = true;
    for (int d = 0; d < 7; d++) {
        if (cfg->schedule_days & (1 << d)) {
            n += snprintf(buf + n, buflen - n, "%s%d", first ? "" : ",", d);
            first = false;
        }
    }

    n += snprintf(buf + n, buflen - n,
        "]},"
        "\"timing\":{"
        "\"boot_wait_sec\":%d,"
        "\"wake_wait_sec\":%d,"
        "\"keystroke_ms\":%d,"
        "\"retry_count\":%d,"
        "\"retry_interval_sec\":%d,"
        "\"dialog_wait_sec\":%d"
        "},",
        cfg->boot_wait_sec, cfg->wake_wait_sec, cfg->keystroke_ms,
        cfg->retry_count, cfg->retry_interval_sec, cfg->dialog_wait_sec);

    n += snprintf(buf + n, buflen - n, "\"apps\":{");
    for (int i = 0; i < cfg->app_count && i < CONFIG_MAX_APPS; i++) {
        n += snprintf(buf + n, buflen - n, "%s\"%s\":%s",
                      i > 0 ? "," : "",
                      cfg->apps[i].name,
                      cfg->apps[i].enabled ? "true" : "false");
    }
    n += snprintf(buf + n, buflen - n, "}");

    /* WiFi credentials (omit password from output for security) */
    if (cfg->wifi_ssid[0] != '\0') {
        n += snprintf(buf + n, buflen - n, ",\"wifi\":{\"ssid\":\"%s\"}", cfg->wifi_ssid);
    }

    n += snprintf(buf + n, buflen - n, "}");
    return n;
}

/* ── Minimal JSON parser helpers ──────────────────────────────────── */

/*
 * Simple key-value extraction from a JSON string.
 * Not a full parser; handles the flat/shallow structure of config.json.
 */

static const char *json_find_key(const char *json, const char *key) {
    char pattern[128];
    snprintf(pattern, sizeof(pattern), "\"%s\"", key);
    const char *p = strstr(json, pattern);
    if (!p) return NULL;
    p += strlen(pattern);
    while (*p == ' ' || *p == ':') p++;
    return p;
}

static int json_get_int(const char *json, const char *key, int def) {
    const char *p = json_find_key(json, key);
    if (!p) return def;
    return atoi(p);
}

static void json_get_str(const char *json, const char *key,
                         char *out, size_t outlen) {
    const char *p = json_find_key(json, key);
    if (!p || *p != '"') return;
    p++; /* skip opening quote */
    size_t i = 0;
    while (*p && *p != '"' && i < outlen - 1) {
        out[i++] = *p++;
    }
    out[i] = '\0';
}

static bool json_get_bool(const char *json, const char *key, bool def) {
    const char *p = json_find_key(json, key);
    if (!p) return def;
    if (strncmp(p, "true", 4) == 0) return true;
    if (strncmp(p, "false", 5) == 0) return false;
    return def;
}

static void json_parse_schedule_time(const char *json, config_t *cfg) {
    /* Find "time":"HH:MM" inside schedule object */
    const char *sched = strstr(json, "\"schedule\"");
    if (!sched) return;

    const char *t = strstr(sched, "\"time\"");
    if (!t) return;
    t += 6;
    while (*t == ' ' || *t == ':') t++;
    if (*t != '"') return;
    t++;

    int hour = 0, min = 0;
    if (sscanf(t, "%d:%d", &hour, &min) == 2) {
        cfg->schedule_hour = (uint8_t)hour;
        cfg->schedule_min  = (uint8_t)min;
    }
}

static void json_parse_schedule_days(const char *json, config_t *cfg) {
    const char *sched = strstr(json, "\"schedule\"");
    if (!sched) return;

    const char *days = strstr(sched, "\"days\"");
    if (!days) return;
    days = strchr(days, '[');
    if (!days) return;
    days++;

    cfg->schedule_days = 0;
    while (*days && *days != ']') {
        if (*days >= '0' && *days <= '6') {
            cfg->schedule_days |= (1 << (*days - '0'));
        }
        days++;
    }
}

static void json_parse_apps(const char *json, config_t *cfg) {
    const char *apps = strstr(json, "\"apps\"");
    if (!apps) return;
    apps = strchr(apps, '{');
    if (!apps) return;
    apps++;

    cfg->app_count = 0;
    while (*apps && *apps != '}' && cfg->app_count < CONFIG_MAX_APPS) {
        /* Skip whitespace and commas */
        while (*apps == ' ' || *apps == ',' || *apps == '\n' || *apps == '\r') apps++;
        if (*apps == '}') break;

        /* Read key */
        if (*apps != '"') break;
        apps++;
        int i = cfg->app_count;
        size_t k = 0;
        while (*apps && *apps != '"' && k < CONFIG_APP_NAME_LEN - 1) {
            cfg->apps[i].name[k++] = *apps++;
        }
        cfg->apps[i].name[k] = '\0';
        if (*apps == '"') apps++;

        /* Skip : and whitespace */
        while (*apps == ' ' || *apps == ':') apps++;

        /* Read value */
        if (strncmp(apps, "true", 4) == 0) {
            cfg->apps[i].enabled = true;
            apps += 4;
        } else if (strncmp(apps, "false", 5) == 0) {
            cfg->apps[i].enabled = false;
            apps += 5;
        }

        cfg->app_count++;
    }
}

static void json_parse_wifi(const char *json, config_t *cfg) {
    const char *wifi = strstr(json, "\"wifi\"");
    if (!wifi) return;

    /* Find ssid within wifi object */
    const char *ssid = strstr(wifi, "\"ssid\"");
    if (ssid) {
        ssid += 6;
        while (*ssid == ' ' || *ssid == ':') ssid++;
        if (*ssid == '"') {
            ssid++;
            size_t i = 0;
            while (*ssid && *ssid != '"' && i < CONFIG_SSID_LEN - 1) {
                cfg->wifi_ssid[i++] = *ssid++;
            }
            cfg->wifi_ssid[i] = '\0';
        }
    }

    const char *pass = strstr(wifi, "\"password\"");
    if (pass) {
        pass += 10;
        while (*pass == ' ' || *pass == ':') pass++;
        if (*pass == '"') {
            pass++;
            size_t i = 0;
            while (*pass && *pass != '"' && i < CONFIG_PASS_LEN - 1) {
                cfg->wifi_password[i++] = *pass++;
            }
            cfg->wifi_password[i] = '\0';
        }
    }
}

static bool config_from_json(const char *json, config_t *cfg) {
    if (!json || json[0] != '{') return false;

    /* Start with defaults, then overlay parsed values */
    config_set_defaults(cfg);

    cfg->version = (uint8_t)json_get_int(json, "version", 2);
    json_get_str(json, "firmware", cfg->firmware, sizeof(cfg->firmware));
    json_get_str(json, "device", cfg->device_str, sizeof(cfg->device_str));
    json_get_str(json, "locale", cfg->locale, sizeof(cfg->locale));

    /* Timing (nested keys — search within timing object) */
    const char *timing = strstr(json, "\"timing\"");
    if (timing) {
        cfg->boot_wait_sec      = (uint16_t)json_get_int(timing, "boot_wait_sec", 45);
        cfg->wake_wait_sec      = (uint16_t)json_get_int(timing, "wake_wait_sec", 5);
        cfg->keystroke_ms       = (uint16_t)json_get_int(timing, "keystroke_ms", 50);
        cfg->retry_count        = (uint8_t)json_get_int(timing, "retry_count", 3);
        cfg->retry_interval_sec = (uint16_t)json_get_int(timing, "retry_interval_sec", 10);
        cfg->dialog_wait_sec    = (uint16_t)json_get_int(timing, "dialog_wait_sec", 1);
    }

    json_parse_schedule_time(json, cfg);
    json_parse_schedule_days(json, cfg);
    json_parse_apps(json, cfg);
    json_parse_wifi(json, cfg);

    return true;
}

/* ── Log persistence callbacks (registered with log module) ───────── */

/* Log file format:
 *   [count:4][write_idx:4][entries: count * 16]
 */

static bool log_persist_cb(const log_entry_t *entries, int count, int write_idx) {
    uint8_t buf[8 + LOG_MAX_ENTRIES * sizeof(log_entry_t)];
    memcpy(buf, &count, 4);
    memcpy(buf + 4, &write_idx, 4);

    int entry_count = (count < LOG_MAX_ENTRIES) ? count : LOG_MAX_ENTRIES;
    memcpy(buf + 8, entries, entry_count * sizeof(log_entry_t));

    return (fs_write_file("/log.bin", buf, 8 + entry_count * sizeof(log_entry_t)) == 0);
}

static bool log_restore_cb(log_entry_t *entries, int *count, int *write_idx) {
    uint8_t buf[8 + LOG_MAX_ENTRIES * sizeof(log_entry_t)];
    int n = fs_read_file("/log.bin", buf, sizeof(buf));
    if (n < 8) return false;

    memcpy(count, buf, 4);
    memcpy(write_idx, buf + 4, 4);

    if (*count < 0 || *count > LOG_MAX_ENTRIES) {
        *count = 0;
        *write_idx = 0;
        return false;
    }

    int entry_count = (*count < LOG_MAX_ENTRIES) ? *count : LOG_MAX_ENTRIES;
    if (n < 8 + entry_count * (int)sizeof(log_entry_t)) {
        *count = 0;
        *write_idx = 0;
        return false;
    }

    memcpy(entries, buf + 8, entry_count * sizeof(log_entry_t));
    return true;
}

/* Forward declaration from log.c */
extern void log_register_persistence(
    bool (*persist)(const log_entry_t *, int, int),
    bool (*restore)(log_entry_t *, int *, int *));

/* ── Base64 encoding (for GET_LOG) ────────────────────────────────── */

static const char b64_table[] =
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

static int base64_encode(const uint8_t *in, size_t inlen, char *out, size_t outlen) {
    size_t needed = ((inlen + 2) / 3) * 4 + 1;
    if (outlen < needed) return -1;

    size_t i = 0, o = 0;
    while (i < inlen) {
        uint32_t a = i < inlen ? in[i++] : 0;
        uint32_t b = i < inlen ? in[i++] : 0;
        uint32_t c = i < inlen ? in[i++] : 0;
        uint32_t triple = (a << 16) | (b << 8) | c;

        out[o++] = b64_table[(triple >> 18) & 0x3F];
        out[o++] = b64_table[(triple >> 12) & 0x3F];
        out[o++] = (i > inlen + 1) ? '=' : b64_table[(triple >> 6) & 0x3F];
        out[o++] = (i > inlen)     ? '=' : b64_table[triple & 0x3F];
    }
    out[o] = '\0';
    return (int)o;
}

/* ── Public API ───────────────────────────────────────────────────── */

bool storage_init(void) {
    int err = lfs_mount(&_lfs, &_lfs_cfg);
    if (err < 0) {
        /* First boot or corrupted FS: format and retry */
        err = lfs_format(&_lfs, &_lfs_cfg);
        if (err < 0) return false;

        err = lfs_mount(&_lfs, &_lfs_cfg);
        if (err < 0) return false;
    }

    _mounted = true;

    /* Register log persistence callbacks */
    log_register_persistence(log_persist_cb, log_restore_cb);

    return true;
}

bool storage_load_config(void) {
    char buf[SERIAL_BUF_SIZE];
    int n = fs_read_file("/config.json", buf, sizeof(buf) - 1);

    if (n <= 0) {
        /* No config file: create defaults */
        config_set_defaults(&g_state.config);
        return storage_save_config();
    }

    buf[n] = '\0';
    return config_from_json(buf, &g_state.config);
}

bool storage_save_config(void) {
    char buf[SERIAL_BUF_SIZE];
    int n = config_to_json(&g_state.config, buf, sizeof(buf));
    if (n <= 0) return false;
    return (fs_write_file("/config.json", buf, n) == 0);
}

int storage_get_config_json(char *buf, size_t buflen) {
    return config_to_json(&g_state.config, buf, buflen);
}

bool storage_set_config_json(const char *json) {
    config_t cfg;
    if (!config_from_json(json, &cfg)) {
        return false;
    }

    g_state.config = cfg;
    return storage_save_config();
}

bool storage_save_pin(const char *pin) {
    if (!pin || strlen(pin) == 0 || strlen(pin) > PIN_MAX_LEN) {
        return false;
    }

    uint8_t enc_buf[PIN_SALT_SIZE + PIN_IV_SIZE + 32];  /* Max encrypted size */
    size_t enc_len = 0;

    if (!crypto_encrypt_pin(pin, enc_buf, sizeof(enc_buf), &enc_len)) {
        return false;
    }

    if (fs_write_file("/pin.enc", enc_buf, enc_len) != 0) {
        return false;
    }

    g_state.pin_stored = true;
    return true;
}

bool storage_load_pin(char *buf, size_t buflen) {
    uint8_t enc_buf[PIN_SALT_SIZE + PIN_IV_SIZE + 32];
    int n = fs_read_file("/pin.enc", enc_buf, sizeof(enc_buf));
    if (n <= 0) return false;

    return crypto_decrypt_pin(enc_buf, (size_t)n, buf, buflen);
}

bool storage_has_pin(void) {
    if (!_mounted) return false;

    lfs_file_t file;
    int err = lfs_file_open(&_lfs, &file, "/pin.enc", LFS_O_RDONLY);
    if (err < 0) return false;

    lfs_file_close(&_lfs, &file);
    return true;
}

bool storage_clear_all(void) {
    bool ok = true;

    /* Delete all known files (ignore errors for non-existent files) */
    fs_delete_file("/pin.enc");
    fs_delete_file("/config.json");
    fs_delete_file("/log.bin");

    g_state.pin_stored = false;

    /* Reset config to defaults */
    config_set_defaults(&g_state.config);

    return ok;
}

bool storage_append_log(const log_entry_t *entry) {
    /* Delegate to log module which manages the ring buffer */
    log_event((event_type_t)entry->event_type,
              (event_result_t)entry->result,
              entry->duration_ms,
              (event_source_t)entry->source);
    return true;
}

int storage_read_log(log_entry_t *entries, int max_entries) {
    return log_read_all(entries, max_entries);
}

int storage_get_log_base64(char *buf, size_t buflen) {
    log_entry_t entries[LOG_MAX_ENTRIES];
    int count = log_read_all(entries, LOG_MAX_ENTRIES);

    if (count == 0) {
        if (buflen > 0) buf[0] = '\0';
        return 0;
    }

    size_t raw_size = count * sizeof(log_entry_t);
    return base64_encode((const uint8_t *)entries, raw_size, buf, buflen);
}
