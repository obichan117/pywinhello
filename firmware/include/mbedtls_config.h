/*
 * mbedtls_config.h — Minimal mbedTLS configuration for pywinhello
 *
 * Only enables AES-256-CBC (PIN encryption) and SHA-256 (OTA verification).
 * Everything else is disabled to minimize binary size.
 */

#ifndef MBEDTLS_CONFIG_H
#define MBEDTLS_CONFIG_H

/* System support */
#define MBEDTLS_HAVE_ASM
#define MBEDTLS_NO_PLATFORM_ENTROPY

/* Crypto primitives we actually use */
#define MBEDTLS_AES_C
#define MBEDTLS_SHA256_C
#define MBEDTLS_MD_C
#define MBEDTLS_CIPHER_C
#define MBEDTLS_HKDF_C
#define MBEDTLS_ENTROPY_C
#define MBEDTLS_CTR_DRBG_C

/* AES-CBC mode for PIN encryption */
#define MBEDTLS_CIPHER_MODE_CBC

/* Save flash space */
#define MBEDTLS_AES_ROM_TABLES

#include "mbedtls/check_config.h"

#endif /* MBEDTLS_CONFIG_H */
