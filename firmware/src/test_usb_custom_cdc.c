/*
 * test_usb_custom_cdc.c — Custom TinyUSB CDC-only test
 *
 * Step 2 diagnostic: uses our own tusb_config.h and USB descriptors
 * but with CDC only (no HID). Tests if our TinyUSB configuration works.
 *
 * If COM port appears: CDC config is fine, issue is adding HID.
 * If no COM port: issue is in tusb_config.h or CDC descriptor setup.
 */

#include "pico/stdlib.h"
#include "pico/bootrom.h"
#include "tusb.h"

#include <stdio.h>
#include <string.h>

/* ── USB Descriptors (inline, CDC only) ─────────────────────────── */

#define USB_VID  0x2E8A
#define USB_PID  0x4001

enum {
    ITF_NUM_CDC = 0,
    ITF_NUM_CDC_DATA,
    ITF_NUM_TOTAL
};

#define EPNUM_CDC_NOTIF  0x81
#define EPNUM_CDC_OUT    0x02
#define EPNUM_CDC_IN     0x82

#define CONFIG_TOTAL_LEN (TUD_CONFIG_DESC_LEN + TUD_CDC_DESC_LEN)

/* Device descriptor */
tusb_desc_device_t const desc_device = {
    .bLength            = sizeof(tusb_desc_device_t),
    .bDescriptorType    = TUSB_DESC_DEVICE,
    .bcdUSB             = 0x0200,
    .bDeviceClass       = TUSB_CLASS_MISC,
    .bDeviceSubClass    = MISC_SUBCLASS_COMMON,
    .bDeviceProtocol    = MISC_PROTOCOL_IAD,
    .bMaxPacketSize0    = CFG_TUD_ENDPOINT0_SIZE,
    .idVendor           = USB_VID,
    .idProduct          = USB_PID,
    .bcdDevice          = 0x0100,
    .iManufacturer      = 1,
    .iProduct           = 2,
    .iSerialNumber      = 3,
    .bNumConfigurations = 1,
};

uint8_t const *tud_descriptor_device_cb(void) {
    return (uint8_t const *)&desc_device;
}

/* Configuration descriptor — CDC only */
uint8_t const desc_configuration[] = {
    TUD_CONFIG_DESCRIPTOR(1, ITF_NUM_TOTAL, 0, CONFIG_TOTAL_LEN, 0, 100),
    TUD_CDC_DESCRIPTOR(ITF_NUM_CDC, 4, EPNUM_CDC_NOTIF,
                       8, EPNUM_CDC_OUT, EPNUM_CDC_IN, 64),
};

uint8_t const *tud_descriptor_configuration_cb(uint8_t index) {
    (void)index;
    return desc_configuration;
}

/* String descriptors */
static const char *string_desc_arr[] = {
    (const char[]){0x09, 0x04},
    "pywinhello",
    "PyWinHello Test CDC",
    "000000000000",
    "PyWinHello CDC",
};

static uint16_t _desc_str[32 + 1];

uint16_t const *tud_descriptor_string_cb(uint8_t index, uint16_t langid) {
    (void)langid;
    size_t chr_count;

    if (index == 0) {
        memcpy(&_desc_str[1], string_desc_arr[0], 2);
        chr_count = 1;
    } else {
        if (index >= sizeof(string_desc_arr) / sizeof(string_desc_arr[0])) {
            return NULL;
        }
        const char *str = string_desc_arr[index];
        chr_count = strlen(str);
        if (chr_count > 31) chr_count = 31;
        for (size_t i = 0; i < chr_count; i++) {
            _desc_str[1 + i] = str[i];
        }
    }

    _desc_str[0] = (uint16_t)((TUSB_DESC_STRING << 8) | (2 * chr_count + 2));
    return _desc_str;
}

/* ── Main ───────────────────────────────────────────────────────── */

int main(void) {
    stdio_init_all();
    tusb_init();

    /* Wait for USB mount with auto-BOOTSEL fallback */
    for (int i = 0; i < 800 && !tud_mounted(); i++) {
        tud_task();
        sleep_ms(10);
    }
    if (!tud_mounted()) {
        reset_usb_boot(0, 0);
    }

    /* USB works — echo test */
    int count = 0;
    while (true) {
        tud_task();

        if (tud_cdc_connected() && tud_cdc_available()) {
            char buf[64];
            uint32_t n = tud_cdc_read(buf, sizeof(buf));
            tud_cdc_write(buf, n);
            tud_cdc_write_flush();
        }

        /* Periodic heartbeat */
        static uint32_t last = 0;
        uint32_t now = to_ms_since_boot(get_absolute_time());
        if (now - last > 2000) {
            last = now;
            if (tud_cdc_connected()) {
                char msg[64];
                int len = snprintf(msg, sizeof(msg), "test_cdc %d\r\n", count++);
                tud_cdc_write(msg, len);
                tud_cdc_write_flush();
            }
        }
    }
}
