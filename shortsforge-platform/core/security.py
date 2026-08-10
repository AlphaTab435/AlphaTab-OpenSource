import logging
import asyncio
import os
from typing import TypeVar, Callable, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)

T = TypeVar("T")

class ErrorLevel(Enum):
    RETRY = 1
    FALLBACK = 2
    SKIP = 3
    FAIL = 4

async def call_with_retry(fn: Callable[[], Any], service_name: str, max_retries: int = 3) -> Any:
    """
    Wraps any async function with retry + exponential backoff.
    Use this for ALL external API calls (Gemini, Pexels, etc.).
    Per TECHNICAL_ADDENDUM error handling contract.
    """
    wait_times = [5, 15, 45]

    for attempt in range(max_retries):
        try:
            result = await fn()
            return result

        except Exception as e:
            is_last_attempt = attempt == max_retries - 1
            
            if is_last_attempt:
                logger.error(f"{service_name}: Failed after {max_retries} attempts. Error: {e}")
                raise
            
            wait = wait_times[attempt] if attempt < len(wait_times) else wait_times[-1]
            logger.warning(f"{service_name}: Error: {e}. Waiting {wait}s (attempt {attempt+1}/{max_retries})")
            await asyncio.sleep(wait)
            
    raise Exception(f"{service_name}: Failed after {max_retries} attempts")


# ═══════════════════════════════════════
# Token Encryption (Fernet — free, no API)
# Used for: YouTube OAuth tokens (Week 4+)
# Per TECHNICAL_ADDENDUM §1: encrypt_token / decrypt_token
# ═══════════════════════════════════════

def _get_fernet():
    """
    Returns a Fernet instance using ENCRYPTION_KEY from environment.
    Returns None if key is not set (graceful skip in dev).
    """
    from core.config import ENCRYPTION_KEY
    if not ENCRYPTION_KEY:
        logger.warning("ENCRYPTION_KEY not set. Token encryption disabled.")
        return None
    
    try:
        from cryptography.fernet import Fernet
        return Fernet(ENCRYPTION_KEY.encode() if isinstance(ENCRYPTION_KEY, str) else ENCRYPTION_KEY)
    except Exception as e:
        logger.error(f"Failed to initialize Fernet: {e}")
        return None


def encrypt_token(token: str) -> Optional[str]:
    """
    Encrypts a token string using Fernet symmetric encryption.
    Returns base64-encoded encrypted string, or None if encryption unavailable.
    Free tier: uses cryptography library (no paid API).
    """
    fernet = _get_fernet()
    if not fernet:
        logger.warning("Encryption unavailable — storing token as-is (DEV ONLY).")
        return token
    
    try:
        encrypted = fernet.encrypt(token.encode())
        return encrypted.decode()
    except Exception as e:
        logger.error(f"Token encryption failed: {e}")
        return None


def decrypt_token(encrypted_token: str) -> Optional[str]:
    """
    Decrypts a Fernet-encrypted token string.
    Returns the original token, or None if decryption fails.
    """
    fernet = _get_fernet()
    if not fernet:
        logger.warning("Decryption unavailable — returning token as-is (DEV ONLY).")
        return encrypted_token
    
    try:
        decrypted = fernet.decrypt(encrypted_token.encode())
        return decrypted.decode()
    except Exception as e:
        logger.error(f"Token decryption failed: {e}. Key may have changed — re-run add_channel.py")
        return None
