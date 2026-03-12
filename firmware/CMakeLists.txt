cmake_minimum_required(VERSION 3.13)

# Pull in Pico SDK (must be set via PICO_SDK_PATH env var)
include($ENV{PICO_SDK_PATH}/external/pico_sdk_import.cmake)

project(pywinhello_firmware C CXX ASM)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

pico_sdk_init()

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
)

target_include_directories(pywinhello_firmware PRIVATE include)

target_link_libraries(pywinhello_firmware
    pico_stdlib
    pico_unique_id
    tinyusb_device
    tinyusb_board
    hardware_flash
    hardware_sync
    pico_mbedtls
)

# Enable USB output, disable UART output
pico_enable_stdio_usb(pywinhello_firmware 1)
pico_enable_stdio_uart(pywinhello_firmware 0)

# Generate UF2 output
pico_add_extra_outputs(pywinhello_firmware)
