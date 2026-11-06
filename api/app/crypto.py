"""Envelope encryption for camera URLs and credentials (rule 4).

Each value gets its own random 256-bit data key (DEK). The value is sealed with AES-256-GCM under the
DEK, and the DEK is sealed under the key-encryption key (KEK) from the environment. The tenant and
camera IDs are bound in as associated data, so a ciphertext copied to another row will not decrypt.
Rotating the KEK means re-wrapping DEKs only. In production the KEK moves to a KMS / secret manager.

Blob layout: version(1) | wrap_nonce(12) | wrapped_dek(48) | data_nonce(12) | ciphertext+tag
"""

import base64
import os
from functools import lru_cache
from uuid import UUID

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import get_settings

VERSION = b"\x01"


@lru_cache
def _kek() -> AESGCM:
    key = base64.b64decode(get_settings().camera_kek_b64.get_secret_value())
    if len(key) != 32:
        raise ValueError("CAMERA_KEK_B64 must be 32 bytes, base64-encoded")
    return AESGCM(key)


def _aad(tenant_id: UUID, camera_id: UUID, field: str) -> bytes:
    return f"enclave:{tenant_id}:{camera_id}:{field}".encode()


def seal(plaintext: str, *, tenant_id: UUID, camera_id: UUID, field: str) -> bytes:
    aad = _aad(tenant_id, camera_id, field)
    dek = AESGCM.generate_key(bit_length=256)
    wrap_nonce, data_nonce = os.urandom(12), os.urandom(12)
    wrapped = _kek().encrypt(wrap_nonce, dek, aad)
    sealed = AESGCM(dek).encrypt(data_nonce, plaintext.encode(), aad)
    return VERSION + wrap_nonce + wrapped + data_nonce + sealed


def unseal(blob: bytes, *, tenant_id: UUID, camera_id: UUID, field: str) -> str:
    if blob[:1] != VERSION:
        raise ValueError("unknown ciphertext version")
    aad = _aad(tenant_id, camera_id, field)
    wrap_nonce, wrapped = blob[1:13], blob[13:61]
    data_nonce, sealed = blob[61:73], blob[73:]
    dek = _kek().decrypt(wrap_nonce, wrapped, aad)
    return AESGCM(dek).decrypt(data_nonce, sealed, aad).decode()
