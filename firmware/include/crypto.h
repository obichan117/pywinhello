/*
 * crypto.h — AES-256 PIN encryption using mbedtls
 *
 * Key is derived from RP2040 unique board ID via HKDF-SHA256.
 * PIN is encrypted with AES-256-CBC and stored as:
 *   [salt:16][iv:16][ciphertext:16+]
 */

#ifndef CRYPTO_H
#define CRYPTO_H

#include "pywinhello.h"

/* ── Public API ───────────────────────────────────────────────────── */

/**
 * Initialize crypto subsystem. Reads board unique ID.
 */
void crypto_init(void);

/**
 * Encrypt a PIN string.
 *
 * @param pin       Null-terminated PIN (cleartext)
 * @param out       Output buffer for [salt][iv][ciphertext]
 * @param out_size  Size of output buffer
 * @param out_len   Actual bytes written
 * @return true on success
 */
bool crypto_encrypt_pin(const char *pin, uint8_t *out, size_t out_size,
                        size_t *out_len);

/**
 * Decrypt an encrypted PIN blob.
 *
 * @param enc       Encrypted data [salt][iv][ciphertext]
 * @param enc_len   Length of encrypted data
 * @param pin       Output buffer for decrypted PIN
 * @param pin_size  Size of output buffer
 * @return true on success
 */
bool crypto_decrypt_pin(const uint8_t *enc, size_t enc_len,
                        char *pin, size_t pin_size);

/**
 * Compute SHA-256 hash of a data buffer.
 *
 * @param data     Input data
 * @param len      Length of input
 * @param hash     Output buffer (must be 32 bytes)
 * @return true on success
 */
bool crypto_sha256(const uint8_t *data, size_t len, uint8_t *hash);

#endif /* CRYPTO_H */
