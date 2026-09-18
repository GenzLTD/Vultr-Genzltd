"""
Looma Trust Protocol — Ed25519 digital signature utilities.

Design: trust.v1.json §signature
- Sign attestation bodies with Ed25519
- Any third party with looma's public key can verify offline
- Key pair generated once, stored as env vars or PEM files
"""
from __future__ import annotations

import base64
import hashlib
import json
import logging
import os
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ed25519

logger = logging.getLogger("looma.crypto")

_KEY_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
_PRIVATE_KEY_PATH = os.path.join(_KEY_DIR, "looma_ed25519_private.pem")
_PUBLIC_KEY_PATH = os.path.join(_KEY_DIR, "looma_ed25519_public.pem")

_private_key: ed25519.Ed25519PrivateKey | None = None
_public_key: ed25519.Ed25519PublicKey | None = None


def _load_or_generate_keys() -> tuple[ed25519.Ed25519PrivateKey, ed25519.Ed25519PublicKey]:
    """Load existing key pair or generate and persist a new one."""
    global _private_key, _public_key
    if _private_key is not None:
        return _private_key, _public_key

    os.makedirs(_KEY_DIR, exist_ok=True)

    if os.path.exists(_PRIVATE_KEY_PATH) and os.path.exists(_PUBLIC_KEY_PATH):
        with open(_PRIVATE_KEY_PATH, "rb") as f:
            _private_key = serialization.load_pem_private_key(f.read(), password=None)
        with open(_PUBLIC_KEY_PATH, "rb") as f:
            _public_key = serialization.load_pem_public_key(f.read())
        logger.info("Loaded existing Ed25519 key pair from %s", _KEY_DIR)
    else:
        _private_key = ed25519.Ed25519PrivateKey.generate()
        _public_key = _private_key.public_key()
        with open(_PRIVATE_KEY_PATH, "wb") as f:
            f.write(
                _private_key.private_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PrivateFormat.PKCS8,
                    encryption_algorithm=serialization.NoEncryption(),
                )
            )
        with open(_PUBLIC_KEY_PATH, "wb") as f:
            f.write(
                _public_key.public_bytes(
                    encoding=serialization.Encoding.PEM,
                    format=serialization.PublicFormat.SubjectPublicKeyInfo,
                )
            )
        logger.info("Generated new Ed25519 key pair → %s", _KEY_DIR)

    return _private_key, _public_key


def get_private_key() -> ed25519.Ed25519PrivateKey:
    priv, _ = _load_or_generate_keys()
    return priv


def get_public_key() -> ed25519.Ed25519PublicKey:
    _, pub = _load_or_generate_keys()
    return pub


def get_public_key_pem() -> str:
    """Return the PEM-encoded public key as a string (for .well-known endpoint)."""
    _, pub = _load_or_generate_keys()
    return pub.public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("ascii")


def sign_attestation(attestation_body: dict) -> str:
    """
    Sign an attestation body and return the looma_sig_v1 signature string.

    Signs: SHA-256 of canonical JSON (sorted keys, no whitespace) of
    the body dict WITHOUT the 'signature' field.
    """
    priv, _ = _load_or_generate_keys()
    # Remove signature field if present (shouldn't be, but be safe)
    body_for_signing = {k: v for k, v in attestation_body.items() if k != "signature"}
    canonical = _canonical_json(body_for_signing)
    digest = hashlib.sha256(canonical.encode("utf-8")).digest()
    raw_sig = priv.sign(digest)
    encoded = base64.urlsafe_b64encode(raw_sig).rstrip(b"=").decode("ascii")
    return f"looma_sig_v1:{encoded}"


def verify_attestation(attestation: dict) -> bool:
    """
    Verify the looma_sig_v1 signature on an attestation dict.

    Returns True if valid, False otherwise.
    """
    _, pub = _load_or_generate_keys()
    signature_str = attestation.get("signature", "")
    if not signature_str.startswith("looma_sig_v1:"):
        return False
    encoded_sig = signature_str[len("looma_sig_v1:"):]
    # Add padding if needed
    padding = 4 - len(encoded_sig) % 4
    if padding != 4:
        encoded_sig += "=" * padding
    try:
        raw_sig = base64.urlsafe_b64decode(encoded_sig)
    except Exception:
        return False

    body_for_verification = {k: v for k, v in attestation.items() if k != "signature"}
    canonical = _canonical_json(body_for_verification)
    digest = hashlib.sha256(canonical.encode("utf-8")).digest()
    try:
        pub.verify(raw_sig, digest)
        return True
    except Exception:
        return False


def _canonical_json(obj) -> str:
    """Produce a canonical JSON string: sorted keys, no whitespace, ensure_ascii."""
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"))