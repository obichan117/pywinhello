/*
 * crypto.c — AES-256 PIN encryption using mbedtls
 *
 * Key derivation: HKDF-SHA256(board_unique_id, salt) → 256-bit AES key
 * Encryption: AES-256-CBC with PKCS7 padding
 * Storage format: [salt:16][iv:16][ciphertext:N]
 */

#include "crypto.h"

#include "pico/unique_id.h"
#include "mbedtls/aes.h"
#include "mbedtls/sha256.h"
#include "mbedtls/md.h"
#include "mbedtls/hkdf.h"
#include "mbedtls/entropy.h"
#include "mbedtls/ctr_drbg.h"

#include <string.h>

/* ── Internal state ───────────────────────────────────────────────── */

static uint8_t _board_id[8];  /* RP2040 unique board ID */
static bool    _initialized = false;

/* HKDF info string — domain separation */
static const uint8_t HKDF_INFO[] = "pywinhello-pin-v1";
#define HKDF_INFO_LEN (sizeof(HKDF_INFO) - 1)

/* ── PRNG for salt/IV generation ──────────────────────────────────── */

static mbedtls_entropy_context  _entropy;
static mbedtls_ctr_drbg_context _ctr_drbg;

static bool prng_init(void) {
    mbedtls_entropy_init(&_entropy);
    mbedtls_ctr_drbg_init(&_ctr_drbg);

    /*
     * Seed the DRBG. On Pico, mbedtls entropy source is limited,
     * so we mix in the board ID as personalization.
     */
    int ret = mbedtls_ctr_drbg_seed(&_ctr_drbg, mbedtls_entropy_func,
                                     &_entropy, _board_id, sizeof(_board_id));
    return (ret == 0);
}

static bool prng_random(uint8_t *buf, size_t len) {
    return (mbedtls_ctr_drbg_random(&_ctr_drbg, buf, len) == 0);
}

/* ── Key derivation ───────────────────────────────────────────────── */

static bool derive_key(const uint8_t *salt, size_t salt_len,
                       uint8_t *key_out) {
    const mbedtls_md_info_t *md = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);
    if (!md) return false;

    int ret = mbedtls_hkdf(md,
                           salt, salt_len,
                           _board_id, sizeof(_board_id),
                           HKDF_INFO, HKDF_INFO_LEN,
                           key_out, AES_KEY_SIZE);
    return (ret == 0);
}

/* ── PKCS7 padding ────────────────────────────────────────────────── */

static size_t pkcs7_pad(uint8_t *buf, size_t data_len, size_t block_size) {
    size_t pad_len = block_size - (data_len % block_size);
    for (size_t i = 0; i < pad_len; i++) {
        buf[data_len + i] = (uint8_t)pad_len;
    }
    return data_len + pad_len;
}

static int pkcs7_unpad(const uint8_t *buf, size_t buf_len) {
    if (buf_len == 0 || buf_len % PIN_ENC_BLOCK_SIZE != 0) {
        return -1;
    }
    uint8_t pad_val = buf[buf_len - 1];
    if (pad_val == 0 || pad_val > PIN_ENC_BLOCK_SIZE) {
        return -1;
    }
    /* Verify all padding bytes */
    for (size_t i = 0; i < pad_val; i++) {
        if (buf[buf_len - 1 - i] != pad_val) {
            return -1;
        }
    }
    return (int)(buf_len - pad_val);
}

/* ── Public API ───────────────────────────────────────────────────── */

void crypto_init(void) {
    pico_unique_board_id_t id;
    pico_get_unique_board_id(&id);
    memcpy(_board_id, id.id, sizeof(_board_id));

    prng_init();
    _initialized = true;
}

bool crypto_encrypt_pin(const char *pin, uint8_t *out, size_t out_size,
                        size_t *out_len) {
    if (!_initialized || !pin || !out || !out_len) {
        return false;
    }

    size_t pin_len = strlen(pin);
    if (pin_len == 0 || pin_len > PIN_MAX_LEN) {
        return false;
    }

    /* Padded plaintext: up to PIN_MAX_LEN + padding = 32 bytes max */
    uint8_t plaintext[32];
    memcpy(plaintext, pin, pin_len);
    size_t padded_len = pkcs7_pad(plaintext, pin_len, PIN_ENC_BLOCK_SIZE);

    /* Output needs: salt(16) + iv(16) + ciphertext(padded_len) */
    size_t total = PIN_SALT_SIZE + PIN_IV_SIZE + padded_len;
    if (out_size < total) {
        memset(plaintext, 0, sizeof(plaintext));
        return false;
    }

    /* Generate random salt and IV */
    uint8_t salt[PIN_SALT_SIZE];
    uint8_t iv[PIN_IV_SIZE];
    if (!prng_random(salt, PIN_SALT_SIZE) || !prng_random(iv, PIN_IV_SIZE)) {
        memset(plaintext, 0, sizeof(plaintext));
        return false;
    }

    /* Derive key from board ID + salt */
    uint8_t key[AES_KEY_SIZE];
    if (!derive_key(salt, PIN_SALT_SIZE, key)) {
        memset(plaintext, 0, sizeof(plaintext));
        memset(key, 0, sizeof(key));
        return false;
    }

    /* AES-256-CBC encrypt */
    mbedtls_aes_context aes;
    mbedtls_aes_init(&aes);

    int ret = mbedtls_aes_setkey_enc(&aes, key, 256);
    if (ret != 0) {
        mbedtls_aes_free(&aes);
        memset(plaintext, 0, sizeof(plaintext));
        memset(key, 0, sizeof(key));
        return false;
    }

    /* Build output: [salt][iv][ciphertext] */
    memcpy(out, salt, PIN_SALT_SIZE);
    memcpy(out + PIN_SALT_SIZE, iv, PIN_IV_SIZE);

    uint8_t iv_copy[PIN_IV_SIZE];
    memcpy(iv_copy, iv, PIN_IV_SIZE);

    ret = mbedtls_aes_crypt_cbc(&aes, MBEDTLS_AES_ENCRYPT, padded_len,
                                 iv_copy, plaintext,
                                 out + PIN_SALT_SIZE + PIN_IV_SIZE);

    mbedtls_aes_free(&aes);
    memset(plaintext, 0, sizeof(plaintext));
    memset(key, 0, sizeof(key));
    memset(iv_copy, 0, sizeof(iv_copy));

    if (ret != 0) {
        return false;
    }

    *out_len = total;
    return true;
}

bool crypto_decrypt_pin(const uint8_t *enc, size_t enc_len,
                        char *pin, size_t pin_size) {
    if (!_initialized || !enc || !pin) {
        return false;
    }

    /* Minimum: salt(16) + iv(16) + one block(16) = 48 */
    if (enc_len < PIN_SALT_SIZE + PIN_IV_SIZE + PIN_ENC_BLOCK_SIZE) {
        return false;
    }

    size_t ct_len = enc_len - PIN_SALT_SIZE - PIN_IV_SIZE;
    if (ct_len % PIN_ENC_BLOCK_SIZE != 0) {
        return false;
    }

    const uint8_t *salt = enc;
    const uint8_t *iv   = enc + PIN_SALT_SIZE;
    const uint8_t *ct   = enc + PIN_SALT_SIZE + PIN_IV_SIZE;

    /* Derive key */
    uint8_t key[AES_KEY_SIZE];
    if (!derive_key(salt, PIN_SALT_SIZE, key)) {
        return false;
    }

    /* Decrypt */
    mbedtls_aes_context aes;
    mbedtls_aes_init(&aes);

    int ret = mbedtls_aes_setkey_dec(&aes, key, 256);
    if (ret != 0) {
        mbedtls_aes_free(&aes);
        memset(key, 0, sizeof(key));
        return false;
    }

    uint8_t iv_copy[PIN_IV_SIZE];
    memcpy(iv_copy, iv, PIN_IV_SIZE);

    uint8_t plaintext[48];  /* Max: 32 bytes PIN + padding */
    if (ct_len > sizeof(plaintext)) {
        mbedtls_aes_free(&aes);
        memset(key, 0, sizeof(key));
        return false;
    }

    ret = mbedtls_aes_crypt_cbc(&aes, MBEDTLS_AES_DECRYPT, ct_len,
                                 iv_copy, ct, plaintext);

    mbedtls_aes_free(&aes);
    memset(key, 0, sizeof(key));
    memset(iv_copy, 0, sizeof(iv_copy));

    if (ret != 0) {
        memset(plaintext, 0, sizeof(plaintext));
        return false;
    }

    /* Remove PKCS7 padding */
    int plain_len = pkcs7_unpad(plaintext, ct_len);
    if (plain_len < 0 || (size_t)plain_len >= pin_size) {
        memset(plaintext, 0, sizeof(plaintext));
        return false;
    }

    memcpy(pin, plaintext, plain_len);
    pin[plain_len] = '\0';

    memset(plaintext, 0, sizeof(plaintext));
    return true;
}

bool crypto_sha256(const uint8_t *data, size_t len, uint8_t *hash) {
    if (!data || !hash) return false;

    mbedtls_sha256_context ctx;
    mbedtls_sha256_init(&ctx);

    int ret = mbedtls_sha256_starts(&ctx, 0);  /* 0 = SHA-256 (not 224) */
    if (ret == 0) ret = mbedtls_sha256_update(&ctx, data, len);
    if (ret == 0) ret = mbedtls_sha256_finish(&ctx, hash);

    mbedtls_sha256_free(&ctx);
    return (ret == 0);
}
