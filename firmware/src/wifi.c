/*
 * wifi.c — CYW43 WiFi auto-detection and NTP sync
 *
 * On Pico W: detects WiFi chip, connects, syncs NTP.
 * On non-W Pico: all functions gracefully return false/no-op.
 *
 * WiFi support is conditionally compiled. When PYWINHELLO_HAS_CYW43
 * is defined, real CYW43 driver calls are used. Otherwise, stubs.
 */

#include "wifi.h"

#include "pico/stdlib.h"

#include <string.h>
#include <stdio.h>

#ifdef PYWINHELLO_HAS_CYW43

#include "pico/cyw43_arch.h"
#include "lwip/dns.h"
#include "lwip/pbuf.h"
#include "lwip/udp.h"

/* ── NTP client ───────────────────────────────────────────────────── */

#define NTP_SERVER       "pool.ntp.org"
#define NTP_PORT         123
#define NTP_MSG_LEN      48
#define NTP_DELTA        2208988800ULL  /* Seconds between 1900 and 1970 */
#define NTP_RESYNC_MS    (6 * 60 * 60 * 1000)  /* 6 hours */

static bool      _wifi_present   = false;
static bool      _wifi_connected = false;
static uint32_t  _ntp_last_sync  = 0;
static uint32_t  _ntp_epoch_at_sync = 0;
static uint32_t  _ntp_local_ms_at_sync = 0;

/* NTP response state */
static volatile bool     _ntp_done = false;
static volatile uint32_t _ntp_result = 0;

static void ntp_recv_cb(void *arg, struct udp_pcb *pcb, struct pbuf *p,
                        const ip_addr_t *addr, u16_t port) {
    (void)arg; (void)pcb; (void)addr; (void)port;

    if (p && p->tot_len >= NTP_MSG_LEN) {
        uint8_t *buf = (uint8_t *)p->payload;
        /* Transmit timestamp is at offset 40, big-endian */
        uint32_t secs = ((uint32_t)buf[40] << 24) |
                        ((uint32_t)buf[41] << 16) |
                        ((uint32_t)buf[42] << 8)  |
                        (uint32_t)buf[43];
        _ntp_result = secs - (uint32_t)NTP_DELTA;
        _ntp_done = true;
    }

    if (p) pbuf_free(p);
}

/* ── Public API (WiFi-enabled build) ──────────────────────────────── */

bool wifi_detect(void) {
    /*
     * CYW43 may already be initialized by board_init().
     * cyw43_arch_init() returns 0 on success, or a negative error
     * if the hardware isn't present. On double-init it may return
     * 0 or PICO_ERROR_GENERIC — either way, check if the driver
     * is actually functional by testing cyw43_is_initialized().
     */
    if (!_wifi_present) {
        int err = cyw43_arch_init();
        if (err == 0) {
            _wifi_present = true;
        }
    }

    if (_wifi_present) {
        #if defined(PICO_RP2350)
        g_state.device = DEVICE_PICO_2_W;
        #else
        g_state.device = DEVICE_PICO_W;
        #endif
        return true;
    }

    /* CYW43 init failed: not a W board */
    #if defined(PICO_RP2350)
    g_state.device = DEVICE_PICO_2;
    #else
    g_state.device = DEVICE_PICO;
    #endif

    return false;
}

bool wifi_connect(void) {
    if (!_wifi_present) return false;

    const char *ssid = g_state.config.wifi_ssid;
    const char *pass = g_state.config.wifi_password;

    if (ssid[0] == '\0') return false;

    cyw43_arch_enable_sta_mode();

    int err = cyw43_arch_wifi_connect_timeout_ms(
        ssid, pass, CYW43_AUTH_WPA2_AES_PSK, 10000);

    _wifi_connected = (err == 0);
    g_state.wifi_connected = _wifi_connected;

    return _wifi_connected;
}

void wifi_disconnect(void) {
    if (!_wifi_present) return;

    cyw43_arch_disable_sta_mode();
    _wifi_connected = false;
    g_state.wifi_connected = false;
}

bool wifi_is_connected(void) {
    if (!_wifi_present) return false;

    /* Check actual link status */
    int status = cyw43_wifi_link_status(&cyw43_state, CYW43_ITF_STA);
    _wifi_connected = (status == CYW43_LINK_JOIN);
    g_state.wifi_connected = _wifi_connected;

    return _wifi_connected;
}

bool wifi_ntp_sync(void) {
    if (!_wifi_connected) return false;

    /* Resolve NTP server */
    ip_addr_t ntp_addr;
    _ntp_done = false;
    _ntp_result = 0;

    /* Use DNS to resolve the server */
    err_t err = dns_gethostbyname(NTP_SERVER, &ntp_addr, NULL, NULL);
    if (err == ERR_INPROGRESS) {
        /* Wait for DNS resolution (with timeout) */
        uint32_t start = to_ms_since_boot(get_absolute_time());
        while (err == ERR_INPROGRESS) {
            cyw43_arch_poll();
            sleep_ms(10);
            err = dns_gethostbyname(NTP_SERVER, &ntp_addr, NULL, NULL);
            if (to_ms_since_boot(get_absolute_time()) - start > 5000) {
                return false;
            }
        }
    }
    if (err != ERR_OK) return false;

    /* Create UDP socket and send NTP request */
    struct udp_pcb *pcb = udp_new();
    if (!pcb) return false;

    udp_recv(pcb, ntp_recv_cb, NULL);

    struct pbuf *p = pbuf_alloc(PBUF_TRANSPORT, NTP_MSG_LEN, PBUF_RAM);
    if (!p) {
        udp_remove(pcb);
        return false;
    }

    uint8_t *req = (uint8_t *)p->payload;
    memset(req, 0, NTP_MSG_LEN);
    req[0] = 0x1B;  /* LI=0, VN=3, Mode=3 (client) */

    err = udp_sendto(pcb, p, &ntp_addr, NTP_PORT);
    pbuf_free(p);

    if (err != ERR_OK) {
        udp_remove(pcb);
        return false;
    }

    /* Wait for response */
    uint32_t start = to_ms_since_boot(get_absolute_time());
    while (!_ntp_done) {
        cyw43_arch_poll();
        sleep_ms(10);
        if (to_ms_since_boot(get_absolute_time()) - start > 5000) {
            udp_remove(pcb);
            return false;
        }
    }

    udp_remove(pcb);

    if (_ntp_result > 0) {
        _ntp_epoch_at_sync = _ntp_result;
        _ntp_local_ms_at_sync = to_ms_since_boot(get_absolute_time());
        _ntp_last_sync = _ntp_local_ms_at_sync;
        g_state.ntp_epoch = _ntp_result;
        return true;
    }

    return false;
}

uint32_t wifi_get_epoch(void) {
    if (_ntp_epoch_at_sync == 0) return 0;

    uint32_t elapsed_ms = to_ms_since_boot(get_absolute_time()) - _ntp_local_ms_at_sync;
    return _ntp_epoch_at_sync + (elapsed_ms / 1000);
}

void wifi_task(void) {
    if (!_wifi_present) return;

    cyw43_arch_poll();

    /* Check connection status and reconnect if needed */
    if (!wifi_is_connected() && g_state.config.wifi_ssid[0] != '\0') {
        static uint32_t last_reconnect = 0;
        uint32_t now = to_ms_since_boot(get_absolute_time());
        if (now - last_reconnect > 30000) {  /* Retry every 30s */
            last_reconnect = now;
            wifi_connect();
        }
    }

    /* Periodic NTP re-sync */
    if (_wifi_connected && _ntp_last_sync > 0) {
        uint32_t now = to_ms_since_boot(get_absolute_time());
        if (now - _ntp_last_sync > NTP_RESYNC_MS) {
            wifi_ntp_sync();
        }
    }
}

void wifi_status_string(char *buf, size_t buflen) {
    if (!_wifi_present) {
        snprintf(buf, buflen, "disabled");
    } else if (_wifi_connected) {
        snprintf(buf, buflen, "connected");
    } else {
        snprintf(buf, buflen, "disconnected");
    }
}

#else /* !PYWINHELLO_HAS_CYW43 — Stub implementations for non-W builds */

bool wifi_detect(void) {
    /*
     * Without CYW43 library, we cannot detect WiFi.
     * Detect RP2040 vs RP2350 only.
     */
    #if defined(PICO_RP2350)
    g_state.device = DEVICE_PICO_2;
    #else
    g_state.device = DEVICE_PICO;
    #endif
    return false;
}

bool wifi_connect(void)       { return false; }
void wifi_disconnect(void)    {}
bool wifi_is_connected(void)  { return false; }
bool wifi_ntp_sync(void)      { return false; }
uint32_t wifi_get_epoch(void) { return 0; }
void wifi_task(void)          {}

void wifi_status_string(char *buf, size_t buflen) {
    snprintf(buf, buflen, "disabled");
}

#endif /* PYWINHELLO_HAS_CYW43 */
