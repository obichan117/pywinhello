/*
 * lfs_config.h — LittleFS configuration for Pico flash
 *
 * Required by littlefs when LFS_NO_MALLOC is not defined.
 * Maps LittleFS logging to standard library.
 */

#ifndef LFS_CONFIG_H
#define LFS_CONFIG_H

#include <stdint.h>
#include <stdbool.h>
#include <string.h>

/* Use default malloc/free from stdlib */
#include <stdlib.h>

#endif /* LFS_CONFIG_H */
