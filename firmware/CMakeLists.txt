cmake_minimum_required(VERSION 3.13)

# Pull in Pico SDK (must be set via PICO_SDK_PATH env var)
include($ENV{PICO_SDK_PATH}/external/pico_sdk_import.cmake)

project(pywinhello_firmware C CXX ASM)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

pico_sdk_init()

# ── Source files ──────────────────────────────────────────────────────

add_executable(pywinhello_firmware
    src/main.c
    src/hid.c
    src/serial_proto.c
    src/storage.c
    src/crypto.c
    src/wifi.c
    src/scheduler.c
    src/bootloader.c
    src/log.c
    src/usb_descriptors.c
)

target_include_directories(pywinhello_firmware PRIVATE include)

# ── Base libraries (always linked) ────────────────────────────────────

target_link_libraries(pywinhello_firmware
    pico_stdlib
    pico_unique_id
    tinyusb_device
    tinyusb_board
    hardware_flash
    hardware_sync
    pico_mbedtls
)

# ── TinyUSB configuration ────────────────────────────────────────────

# Use TinyUSB device stack (not pico stdio USB, which conflicts)
# We handle USB descriptors ourselves in usb_descriptors.c
pico_enable_stdio_usb(pywinhello_firmware 0)
pico_enable_stdio_uart(pywinhello_firmware 0)

# ── Conditional WiFi / CYW43 support ─────────────────────────────────
#
# Pico W boards need the CYW43 driver + lwIP for WiFi and NTP.
# Non-W boards get stub implementations (wifi.c has #ifdef guards).
#
# Detection: PICO_BOARD is set by the SDK. Known W boards:
#   pico_w, pico2_w
#
# Users can also force WiFi support with -DPYWINHELLO_WIFI=ON/OFF.

if(DEFINED PYWINHELLO_WIFI)
    # Explicit override
    if(PYWINHELLO_WIFI)
        set(_WIFI_ENABLED TRUE)
    else()
        set(_WIFI_ENABLED FALSE)
    endif()
elseif(PICO_BOARD STREQUAL "pico_w" OR PICO_BOARD STREQUAL "pico2_w")
    # Auto-detect from board type
    set(_WIFI_ENABLED TRUE)
else()
    set(_WIFI_ENABLED FALSE)
endif()

if(_WIFI_ENABLED)
    message(STATUS "WiFi support: ENABLED (board=${PICO_BOARD})")

    target_compile_definitions(pywinhello_firmware PRIVATE
        PYWINHELLO_HAS_CYW43=1
    )

    target_link_libraries(pywinhello_firmware
        pico_cyw43_arch_lwip_poll
    )
else()
    message(STATUS "WiFi support: DISABLED (board=${PICO_BOARD})")
endif()

# ── RP2350 detection ──────────────────────────────────────────────────

if(PICO_PLATFORM STREQUAL "rp2350" OR PICO_BOARD STREQUAL "pico2" OR PICO_BOARD STREQUAL "pico2_w")
    target_compile_definitions(pywinhello_firmware PRIVATE
        PICO_RP2350=1
    )
    message(STATUS "Target platform: RP2350")
else()
    message(STATUS "Target platform: RP2040")
endif()

# ── Compiler warnings ────────────────────────────────────────────────

target_compile_options(pywinhello_firmware PRIVATE
    -Wall
    -Wextra
    -Wno-unused-parameter
)

# ── Generate UF2 output ──────────────────────────────────────────────

pico_add_extra_outputs(pywinhello_firmware)
