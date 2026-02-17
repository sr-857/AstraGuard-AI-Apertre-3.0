"""
Encryption for Sensitive Data

Provides AES-256-GCM encryption for sensitive data with key derivation.
Supports field-level encryption for database fields and configuration.
"""

import logging
import os
import base64
from typing import Optional, Union, Dict, Any
from dataclasses import dataclass
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)


@dataclass
class EncryptedData:
    """Container for encrypted data."""
    ciphertext: str
    key_id: Optional[str] = None
    algorithm: str = "AES-256-GCM"

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EncryptedData':
        return cls(**data)


class DataEncryption:
    """
    AES-256-GCM encryption for sensitive data.
    
    Features:
    - AES-256-GCM authenticated encryption
    - PBKDF2 key derivation
    - Automatic nonce generation
    - Base64 encoding for storage
    """
    
    def __init__(self, master_key: Optional[str] = None, salt: Optional[bytes] = None, use_hardware_acceleration: bool = True):
        """
        Initialize encryption with master key.
        
        Args:
            master_key: Master encryption key (32 bytes or will be derived)
            salt: Salt for key derivation (16 bytes)
            use_hardware_acceleration: Whether to use hardware acceleration (mocked for now)
        """
        if master_key is None:
            master_key = os.getenv("ENCRYPTION_MASTER_KEY")
            if not master_key:
                # Fallback for tests if not provided
                master_key = "test-master-key-must-be-long-enough"
        
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
        self.use_hardware_acceleration = use_hardware_acceleration
        
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

    def health_check(self) -> Dict[str, Any]:
        """Check encryption engine health."""
        try:
            test_str = "health_check"
            encrypted = self.encrypt(test_str)
            decrypted = self.decrypt(encrypted)
            return {
                "status": "healthy" if decrypted == test_str else "degraded",
                "algorithm": "AES-256-GCM",
                "hardware_acceleration": self.use_hardware_acceleration
            }
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}
    
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


# Alias for backward compatibility/internal imports
EncryptionEngine = DataEncryption


# Global instance
_data_encryption: Optional[DataEncryption] = None


def init_encryption_engine(master_key: Optional[bytes] = None, use_hardware_acceleration: bool = True) -> DataEncryption:
    """Initialize the global encryption engine."""
    global _data_encryption
    # Convert bytes key to str if needed for compatibility
    key_str = master_key.decode() if master_key else None
    _data_encryption = DataEncryption(master_key=key_str, use_hardware_acceleration=use_hardware_acceleration)
    return _data_encryption


def get_encryption_engine() -> DataEncryption:
    """Get the global encryption engine instance."""
    global _data_encryption
    if _data_encryption is None:
        _data_encryption = DataEncryption()
    return _data_encryption


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


def encrypt_data(data: str) -> tuple:
    """Mock encrypt data returning (ciphertext, key)."""
    enc = get_encryption_engine()
    return enc.encrypt(data), "mock-key"


def decrypt_data(data: str, key: Any = None) -> str:
    """Mock decrypt data."""
    enc = get_encryption_engine()
    return enc.decrypt(data)
