/*
 * usb_descriptors.c — TinyUSB USB descriptors (HID keyboard + CDC serial)
 *
 * Composite device with two interfaces:
 *   Interface 0: CDC (serial communication)
 *   Interface 1: CDC Data
 *   Interface 2: HID (keyboard)
 *
 * Remote wakeup is enabled in the configuration descriptor
 * so the Pico can wake the host PC from S3 sleep.
 */

#include "tusb.h"
#include "pywinhello.h"
#include "pico/unique_id.h"

/* ── Device Descriptor ────────────────────────────────────────────── */

tusb_desc_device_t const desc_device = {
    .bLength            = sizeof(tusb_desc_device_t),
    .bDescriptorType    = TUSB_DESC_DEVICE,
    .bcdUSB             = 0x0200,  /* USB 2.0 */
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

/* ── HID Report Descriptor ────────────────────────────────────────── */

uint8_t const desc_hid_report[] = {
    TUD_HID_REPORT_DESC_KEYBOARD(HID_REPORT_ID(1)),
};

uint8_t const *tud_hid_descriptor_report_cb(uint8_t instance) {
    (void)instance;
    return desc_hid_report;
}

/* ── Configuration Descriptor ─────────────────────────────────────── */

/*
 * Interface numbering:
 *   0 = CDC Control
 *   1 = CDC Data
 *   2 = HID Keyboard
 *
 * Endpoints:
 *   CDC: EP 0x81 (notify), EP 0x02 (out), EP 0x82 (in)
 *   HID: EP 0x83 (in)
 */

#define ITF_NUM_CDC       0
#define ITF_NUM_CDC_DATA  1
#define ITF_NUM_HID       2
#define ITF_NUM_TOTAL     3

#define EPNUM_CDC_NOTIF   0x81
#define EPNUM_CDC_OUT     0x02
#define EPNUM_CDC_IN      0x82
#define EPNUM_HID         0x83

#define CONFIG_TOTAL_LEN  (TUD_CONFIG_DESC_LEN + TUD_CDC_DESC_LEN + TUD_HID_DESC_LEN)

uint8_t const desc_configuration[] = {
    /* Config descriptor: remote wakeup enabled */
    TUD_CONFIG_DESCRIPTOR(1, ITF_NUM_TOTAL, 0, CONFIG_TOTAL_LEN,
                          TUSB_DESC_CONFIG_ATT_REMOTE_WAKEUP, 100),

    /* CDC: Interface 0+1, EP 0x81 notify, EP 0x02 out, EP 0x82 in */
    TUD_CDC_DESCRIPTOR(ITF_NUM_CDC, 4, EPNUM_CDC_NOTIF,
                       8, EPNUM_CDC_OUT, EPNUM_CDC_IN, 64),

    /* HID: Interface 2, EP 0x83 in, report desc */
    TUD_HID_DESCRIPTOR(ITF_NUM_HID, 5, HID_ITF_PROTOCOL_KEYBOARD,
                       sizeof(desc_hid_report), EPNUM_HID, 16, 10),
};

uint8_t const *tud_descriptor_configuration_cb(uint8_t index) {
    (void)index;
    return desc_configuration;
}

/* ── String Descriptors ───────────────────────────────────────────── */

/* String index 0: supported language = English */
static const char *string_desc_arr[] = {
    (const char[]){0x09, 0x04},  /* English (US) */
    "pywinhello",                /* Manufacturer */
    "PyWinHello Pico",           /* Product */
    "",                          /* Serial (filled at runtime from board ID) */
    "PyWinHello CDC",            /* CDC interface */
    "PyWinHello HID",            /* HID interface */
};

static uint16_t _desc_str[32 + 1];

uint16_t const *tud_descriptor_string_cb(uint8_t index, uint16_t langid) {
    (void)langid;
    size_t chr_count;

    switch (index) {
    case 0:
        memcpy(&_desc_str[1], string_desc_arr[0], 2);
        chr_count = 1;
        break;

    case 3: {
        /* Serial number from board unique ID */
        char serial[17];
        pico_unique_board_id_t id;
        pico_get_unique_board_id(&id);
        for (int i = 0; i < 8; i++) {
            snprintf(&serial[i * 2], 3, "%02X", id.id[i]);
        }
        serial[16] = '\0';
        chr_count = 16;
        for (size_t i = 0; i < chr_count; i++) {
            _desc_str[1 + i] = serial[i];
        }
        break;
    }

    default:
        if (index >= sizeof(string_desc_arr) / sizeof(string_desc_arr[0])) {
            return NULL;
        }
        const char *str = string_desc_arr[index];
        chr_count = strlen(str);
        if (chr_count > 31) chr_count = 31;
        for (size_t i = 0; i < chr_count; i++) {
            _desc_str[1 + i] = str[i];
        }
        break;
    }

    /* First byte is length (including header), second byte is string type */
    _desc_str[0] = (uint16_t)((TUSB_DESC_STRING << 8) | (2 * chr_count + 2));

    return _desc_str;
}
