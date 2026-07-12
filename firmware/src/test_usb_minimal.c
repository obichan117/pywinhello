/*
 * test_usb_minimal.c — Bare minimum USB CDC test
 *
 * Uses pico_stdio_usb (SDK built-in) to verify USB works on this board.
 * If a COM port appears and prints "pywinhello test", USB hardware is fine.
 */

#include <stdio.h>
#include "pico/stdlib.h"

int main(void) {
    stdio_init_all();

    /* Wait for USB CDC to connect */
    while (!stdio_usb_connected()) {
        sleep_ms(100);
    }

    int count = 0;
    while (true) {
        printf("pywinhello test %d\n", count++);
        sleep_ms(1000);
    }
}
