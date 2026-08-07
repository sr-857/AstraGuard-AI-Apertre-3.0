"""
Encryption for Sensitive Data

Provides AES-256-GCM encryption for sensitive data with key derivation.
Supports field-level encryption for database fields and configuration.
"""

import logging
import os
import base64
from typing import Optional, Union
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


class DataEncryption:
    """
    AES-256-GCM encryption for sensitive data.
    
    Features:
    - AES-256-GCM authenticated encryption
    - PBKDF2 key derivation
    - Automatic nonce generation
    - Base64 encoding for storage
    """
    
    def __init__(self, master_key: Optional[str] = None, salt: Optional[bytes] = None):
        """
        Initialize encryption with master key.
        
        Args:
            master_key: Master encryption key (32 bytes or will be derived)
            salt: Salt for key derivation (16 bytes)
        """
        if master_key is None:
            master_key = os.getenv("ENCRYPTION_MASTER_KEY")
            if not master_key:
                raise ValueError("Master key required for encryption")
        
        # Derive encryption key from master key
        if salt is None:
            salt = os.getenv("ENCRYPTION_SALT", "astraguard-salt-2026").encode()[:16]
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256 bits
            salt=salt,
            iterations=100000,
        )
        self.key = kdf.derive(master_key.encode())
        self.aesgcm = AESGCM(self.key)
        
        logger.info("Data encryption initialized with AES-256-GCM")
    
    def encrypt(self, plaintext: Union[str, bytes]) -> str:
        """
        Encrypt data.
        
        Args:
            plaintext: Data to encrypt (string or bytes)
            
        Returns:
            Base64-encoded ciphertext with nonce
        """
        if isinstance(plaintext, str):
            plaintext = plaintext.encode('utf-8')
        
        # Generate random nonce (96 bits for GCM)
        nonce = os.urandom(12)
        
        # Encrypt
        ciphertext = self.aesgcm.encrypt(nonce, plaintext, None)
        
        # Combine nonce + ciphertext and encode
        combined = nonce + ciphertext
        encoded = base64.b64encode(combined).decode('utf-8')
        
        logger.debug(f"Encrypted {len(plaintext)} bytes")
        return encoded
    
    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt data.
        
        Args:
            ciphertext: Base64-encoded ciphertext with nonce
            
        Returns:
            Decrypted plaintext as string
        """
        try:
            # Decode from base64
            combined = base64.b64decode(ciphertext.encode('utf-8'))
            
            # Split nonce and ciphertext
            nonce = combined[:12]
            actual_ciphertext = combined[12:]
            
            # Decrypt
            plaintext = self.aesgcm.decrypt(nonce, actual_ciphertext, None)
            
            logger.debug(f"Decrypted {len(plaintext)} bytes")
            return plaintext.decode('utf-8')
            
        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise ValueError("Decryption failed - invalid ciphertext or key")
    
    def encrypt_dict(self, data: dict, fields_to_encrypt: list) -> dict:
        """
        Encrypt specific fields in a dictionary.
        
        Args:
            data: Dictionary with data
            fields_to_encrypt: List of field names to encrypt
            
        Returns:
            Dictionary with encrypted fields
        """
        result = data.copy()
        
        for field in fields_to_encrypt:
            if field in result and result[field] is not None:
                result[field] = self.encrypt(str(result[field]))
                logger.debug(f"Encrypted field: {field}")
        
        return result
    
    def decrypt_dict(self, data: dict, fields_to_decrypt: list) -> dict:
        """
        Decrypt specific fields in a dictionary.
        
        Args:
            data: Dictionary with encrypted data
            fields_to_decrypt: List of field names to decrypt
            
        Returns:
            Dictionary with decrypted fields
        """
        result = data.copy()
        
        for field in fields_to_decrypt:
            if field in result and result[field] is not None:
                try:
                    result[field] = self.decrypt(result[field])
                    logger.debug(f"Decrypted field: {field}")
                except Exception as e:
                    logger.error(f"Failed to decrypt field {field}: {e}")
                    result[field] = None
        
        return result


# Global instance
_data_encryption: Optional[DataEncryption] = None


def get_data_encryption(master_key: Optional[str] = None) -> DataEncryption:
    """Get or create data encryption instance."""
    global _data_encryption
    
    if _data_encryption is None:
        _data_encryption = DataEncryption(master_key)
    
    return _data_encryption


# Convenience functions
def encrypt_field(value: str) -> str:
    """Encrypt a single field value."""
    enc = get_data_encryption()
    return enc.encrypt(value)


def decrypt_field(value: str) -> str:
    """Decrypt a single field value."""
    enc = get_data_encryption()
    return enc.decrypt(value)


# ---------------------------------------------------------------------------
# Backward-compatible aliases expected by src/security/__init__.py
# ---------------------------------------------------------------------------

# EncryptionEngine is the canonical public name; DataEncryption is the impl.
EncryptionEngine = DataEncryption


class EncryptedData:
    """Lightweight container for encrypted payload + metadata."""
    __slots__ = ("ciphertext", "algorithm", "key_id")

    def __init__(self, ciphertext: str, algorithm: str = "AES-256-GCM", key_id: str = ""):
        self.ciphertext = ciphertext
        self.algorithm = algorithm
        self.key_id = key_id

    def __repr__(self) -> str:  # pragma: no cover
        return f"EncryptedData(algorithm={self.algorithm!r}, key_id={self.key_id!r})"


class DataEncryptionKey:
    """Represents a Data Encryption Key (DEK)."""
    __slots__ = ("key_id", "key_material", "algorithm")

    def __init__(self, key_id: str = "", key_material: bytes = b"", algorithm: str = "AES-256-GCM"):
        self.key_id = key_id
        self.key_material = key_material
        self.algorithm = algorithm


class KeyEncryptionKey:
    """Represents a Key Encryption Key (KEK) used to wrap DEKs."""
    __slots__ = ("key_id", "provider")

    def __init__(self, key_id: str = "", provider: str = "local"):
        self.key_id = key_id
        self.provider = provider


class EncryptionAlgorithm:
    """Supported encryption algorithm identifiers."""
    AES_256_GCM = "AES-256-GCM"
    AES_256_CBC = "AES-256-CBC"
    CHACHA20_POLY1305 = "ChaCha20-Poly1305"


# Module-level encryption engine singleton (mirrors get_data_encryption API)
_encryption_engine: Optional[DataEncryption] = None


def init_encryption_engine(master_key: Optional[str] = None, **kwargs) -> DataEncryption:
    """Initialize and return the singleton EncryptionEngine."""
    global _encryption_engine
    _encryption_engine = DataEncryption(master_key)
    return _encryption_engine


def get_encryption_engine() -> Optional[DataEncryption]:
    """Return the current singleton EncryptionEngine (or None if not initialised)."""
    return _encryption_engine


def encrypt_data(plaintext: Union[str, bytes], master_key: Optional[str] = None) -> tuple:
    """Encrypt *plaintext* and return *(EncryptedData, DataEncryptionKey)*."""
    engine = get_data_encryption(master_key)
    ciphertext = engine.encrypt(plaintext)
    dek = DataEncryptionKey(key_material=engine.key)
    return EncryptedData(ciphertext), dek


def decrypt_data(encrypted: "EncryptedData", dek: "DataEncryptionKey", master_key: Optional[str] = None) -> str:
    """Decrypt an *EncryptedData* object and return the plaintext string."""
    engine = get_data_encryption(master_key)
    return engine.decrypt(encrypted.ciphertext)
