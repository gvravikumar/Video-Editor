"""
Secure secret storage.

Stores sensitive values (e.g. the user's YouTube OAuth token) so they are NOT
readable as plaintext from the repository — and so the agent operating this repo
cannot casually read them either.

Backend priority:
  1. OS keychain via `keyring` (macOS Keychain / Windows Credential Locker /
     Secret Service). Secrets live in the OS-managed encrypted store, not a file.
  2. Fernet-encrypted file fallback (`state/secrets/<name>.enc`). The Fernet key
     is stored in the OS keychain when possible; otherwise in a local key file
     with 0600 permissions (least preferred; a warning is logged once).

Nothing here ever logs secret values.
"""

import os
import base64
import logging

logger = logging.getLogger(__name__)

SERVICE_NAME = "videostudio-ai"
_BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_SECRETS_DIR = os.path.join(_BASE, "state", "secrets")
_KEYFILE = os.path.join(_SECRETS_DIR, ".fernet.key")


def _keyring():
    try:
        import keyring
        # Some environments have a broken/None backend; probe it.
        kr = keyring.get_keyring()
        if kr is None:
            return None
        return keyring
    except Exception:
        return None


# --------------------------------------------------------------- keychain path
def _kr_set(name, value):
    kr = _keyring()
    if not kr:
        return False
    try:
        kr.set_password(SERVICE_NAME, name, value)
        return True
    except Exception as e:
        logger.warning("keyring set failed (%s); using encrypted-file fallback", e)
        return False


def _kr_get(name):
    kr = _keyring()
    if not kr:
        return None
    try:
        return kr.get_password(SERVICE_NAME, name)
    except Exception:
        return None


def _kr_del(name):
    kr = _keyring()
    if not kr:
        return
    try:
        kr.delete_password(SERVICE_NAME, name)
    except Exception:
        pass


# ----------------------------------------------------------- encrypted-file path
def _get_fernet():
    """Return a Fernet instance using a key stored in the keychain or a 0600 file."""
    from cryptography.fernet import Fernet

    key = _kr_get("__fernet_key__")
    if not key:
        # Try local key file
        if os.path.exists(_KEYFILE):
            with open(_KEYFILE, "rb") as f:
                key = f.read().decode()
        else:
            key = Fernet.generate_key().decode()
            # Prefer stashing the key in the keychain; else a 0600 file.
            if not _kr_set("__fernet_key__", key):
                os.makedirs(_SECRETS_DIR, exist_ok=True)
                with open(_KEYFILE, "wb") as f:
                    f.write(key.encode())
                os.chmod(_KEYFILE, 0o600)
                logger.warning(
                    "Stored encryption key in a local 0600 file (%s); OS keychain "
                    "was unavailable. Protect this file.", _KEYFILE
                )
    return Fernet(key.encode() if isinstance(key, str) else key)


def _file_path(name):
    return os.path.join(_SECRETS_DIR, f"{name}.enc")


def _file_set(name, value):
    f = _get_fernet()
    token = f.encrypt(value.encode())
    os.makedirs(_SECRETS_DIR, exist_ok=True)
    path = _file_path(name)
    with open(path, "wb") as fh:
        fh.write(token)
    os.chmod(path, 0o600)


def _file_get(name):
    path = _file_path(name)
    if not os.path.exists(path):
        return None
    try:
        f = _get_fernet()
        with open(path, "rb") as fh:
            return f.decrypt(fh.read()).decode()
    except Exception as e:
        logger.warning("Could not decrypt secret '%s': %s", name, e)
        return None


def _file_del(name):
    path = _file_path(name)
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass


# ---------------------------------------------------------------- public API
def set_secret(name: str, value: str) -> None:
    """Store a secret securely (keychain preferred, encrypted file fallback)."""
    if not _kr_set(name, value):
        _file_set(name, value)


def get_secret(name: str):
    """Retrieve a secret, or None if absent."""
    v = _kr_get(name)
    if v is not None:
        return v
    return _file_get(name)


def delete_secret(name: str) -> None:
    """Remove a secret from all backends."""
    _kr_del(name)
    _file_del(name)


def backend_name() -> str:
    """Human-readable description of the active backend (for status/UI)."""
    if _keyring():
        return "OS keychain"
    return "encrypted file"
