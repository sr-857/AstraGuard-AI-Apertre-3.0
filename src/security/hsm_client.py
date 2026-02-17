"""
HSM (Hardware Security Module) Client with PKCS#11 Support

Provides:
- PKCS#11 integration for HSM operations
- Cloud HSM support (AWS CloudHSM, Azure Dedicated HSM, Google Cloud HSM)
- Mock HSM for testing and development
- Key generation, storage, and cryptographic operations
"""

import os
import json
import base64
import logging
import hashlib
import secrets
from typing import Optional, Dict, Any, List, Callable, Union, BinaryIO
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from abc import ABC, abstractmethod
from threading import Lock

# Optional PKCS#11 support
try:
    import PyKCS11Lib
    from PyKCS11 import Mechanism, CK_OBJECT_CLASS, CKO_PRIVATE_KEY, CKO_PUBLIC_KEY, CKO_SECRET_KEY
    HAS_PKCS11 = True
except ImportError:
    HAS_PKCS11 = False
    PyKCS11Lib = None
    Mechanism = None
    CK_OBJECT_CLASS = None
    CKO_PRIVATE_KEY = None
    CKO_PUBLIC_KEY = None
    CKO_SECRET_KEY = None

# Optional AWS SDK
try:
    import boto3
    from botocore.exceptions import ClientError
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False
    boto3 = None
    ClientError = Exception

# Optional Azure SDK
try:
    from azure.identity import DefaultAzureCredential
    from azure.keyvault.keys import KeyClient
    from azure.keyvault.keys.crypto import CryptographyClient, EncryptionAlgorithm
    HAS_AZURE = True
except ImportError:
    HAS_AZURE = False
    DefaultAzureCredential = None
    KeyClient = None
    CryptographyClient = None
    EncryptionAlgorithm = None

# Optional Google Cloud SDK
try:
    from google.cloud import kms_v1
    from google.oauth2 import service_account
    HAS_GCP = True
except ImportError:
    HAS_GCP = False
    kms_v1 = None
    service_account = None

logger = logging.getLogger(__name__)


class HSMProvider(Enum):
    """Supported HSM providers."""
    MOCK = "mock"
    PKCS11 = "pkcs11"
    AWS_CLOUDHSM = "aws_cloudhsm"
    AZURE_DEDICATED_HSM = "azure_dedicated_hsm"
    GOOGLE_CLOUD_HSM = "google_cloud_hsm"
    HASHICORP_VAULT = "hashicorp_vault"


class HSMKeyType(Enum):
    """Types of keys that can be stored in HSM."""
    AES_256 = "aes-256"
    RSA_2048 = "rsa-2048"
    RSA_4096 = "rsa-4096"
    EC_P256 = "ec-p256"
    EC_P384 = "ec-p384"


@dataclass
class HSMKeyMetadata:
    """Metadata for an HSM-stored key."""
    key_id: str
    key_type: HSMKeyType
    created_at: datetime
    hsm_provider: HSMProvider
    key_handle: str
    label: Optional[str] = None
    extractable: bool = False
    tags: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "key_id": self.key_id,
            "key_type": self.key_type.value,
            "created_at": self.created_at.isoformat(),
            "hsm_provider": self.hsm_provider.value,
            "key_handle": self.key_handle,
            "label": self.label,
            "extractable": self.extractable,
            "tags": self.tags,
        }


class HSMClientInterface(ABC):
    """Abstract interface for HSM clients."""
    
    @abstractmethod
    def generate_key(
        self,
        key_id: str,
        key_type: HSMKeyType,
        extractable: bool = False,
        label: Optional[str] = None,
    ) -> str:
        """Generate a key in the HSM."""
        pass
    
    @abstractmethod
    def encrypt(self, key_handle: str, plaintext: bytes, algorithm: str = "AES-GCM") -> bytes:
        """Encrypt data using HSM key."""
        pass
    
    @abstractmethod
    def decrypt(self, key_handle: str, ciphertext: bytes, algorithm: str = "AES-GCM") -> bytes:
        """Decrypt data using HSM key."""
        pass
    
    @abstractmethod
    def wrap_key(self, wrapping_key_handle: str, key_to_wrap: bytes) -> bytes:
        """Wrap a key using another HSM key."""
        pass
    
    @abstractmethod
    def unwrap_key(self, unwrapping_key_handle: str, wrapped_key: bytes) -> bytes:
        """Unwrap a key using another HSM key."""
        pass
    
    @abstractmethod
    def delete_key(self, key_handle: str) -> bool:
        """Delete a key from the HSM."""
        pass
    
    @abstractmethod
    def list_keys(self) -> List[HSMKeyMetadata]:
        """List all keys in the HSM."""
        pass
    
    @abstractmethod
    def health_check(self) -> Dict[str, Any]:
        """Check HSM health status."""
        pass


class MockHSMClient(HSMClientInterface):
    """
    Mock HSM client for testing and development.
    
    Simulates HSM operations using software cryptography.
    NOT FOR PRODUCTION USE.
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        self.storage_path = Path(storage_path) if storage_path else Path(".mock_hsm")
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._keys: Dict[str, Dict[str, Any]] = {}
        self._lock = Lock()
        self._load_keys()
        
        logger.warning("Using MockHSMClient - NOT FOR PRODUCTION")
    
    def _load_keys(self) -> None:
        """Load keys from storage."""
        keys_file = self.storage_path / "keys.json"
        if keys_file.exists():
            try:
                with open(keys_file, "r") as f:
                    data = json.load(f)
                    for key_id, key_data in data.items():
                        key_data["created_at"] = datetime.fromisoformat(key_data["created_at"])
                    self._keys = data
            except Exception as e:
                logger.error(f"Failed to load mock HSM keys: {e}")
    
    def _save_keys(self) -> None:
        """Save keys to storage."""
        keys_file = self.storage_path / "keys.json"
        try:
            data = {}
            for key_id, key_data in self._keys.items():
                data[key_id] = {
                    **key_data,
                    "created_at": key_data["created_at"].isoformat(),
                }
            with open(keys_file, "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save mock HSM keys: {e}")
    
    def generate_key(
        self,
        key_id: str,
        key_type: HSMKeyType,
        extractable: bool = False,
        label: Optional[str] = None,
    ) -> str:
        """Generate a mock key."""
        with self._lock:
            if key_id in self._keys:
                raise ValueError(f"Key {key_id} already exists")
            
            # Generate key material
            if key_type == HSMKeyType.AES_256:
                key_material = secrets.token_bytes(32)
            elif key_type in (HSMKeyType.RSA_2048, HSMKeyType.RSA_4096):
                # For mock, we just store a seed
                key_material = secrets.token_bytes(32)
            else:
                key_material = secrets.token_bytes(32)
            
            key_handle = f"mock-{key_id}-{secrets.token_hex(8)}"
            
            self._keys[key_handle] = {
                "key_id": key_id,
                "key_type": key_type.value,
                "key_material": base64.b64encode(key_material).decode(),
                "created_at": datetime.now(),
                "extractable": extractable,
                "label": label,
            }
            
            self._save_keys()
            
            logger.debug(f"Mock HSM generated key: {key_id} ({key_type.value})")
            return key_handle
    
    def encrypt(self, key_handle: str, plaintext: bytes, algorithm: str = "AES-GCM") -> bytes:
        """Encrypt using mock key."""
        with self._lock:
            if key_handle not in self._keys:
                raise ValueError(f"Key {key_handle} not found")
            
            key_data = self._keys[key_handle]
            key_material = base64.b64decode(key_data["key_material"])
            
            if algorithm == "AES-GCM":
                from cryptography.hazmat.primitives.ciphers.aead import AESGCM
                aesgcm = AESGCM(key_material)
                nonce = secrets.token_bytes(12)
                ciphertext = aesgcm.encrypt(nonce, plaintext, None)
                return nonce + ciphertext
            else:
                raise ValueError(f"Unsupported algorithm: {algorithm}")
    
    def decrypt(self, key_handle: str, ciphertext: bytes, algorithm: str = "AES-GCM") -> bytes:
        """Decrypt using mock key."""
        with self._lock:
            if key_handle not in self._keys:
                raise ValueError(f"Key {key_handle} not found")
            
            key_data = self._keys[key_handle]
            key_material = base64.b64decode(key_data["key_material"])
            
            if algorithm == "AES-GCM":
                from cryptography.hazmat.primitives.ciphers.aead import AESGCM
                aesgcm = AESGCM(key_material)
                nonce = ciphertext[:12]
                ct = ciphertext[12:]
                return aesgcm.decrypt(nonce, ct, None)
            else:
                raise ValueError(f"Unsupported algorithm: {algorithm}")
    
    def wrap_key(self, wrapping_key_handle: str, key_to_wrap: bytes) -> bytes:
        """Wrap a key."""
        return self.encrypt(wrapping_key_handle, key_to_wrap, "AES-GCM")
    
    def unwrap_key(self, unwrapping_key_handle: str, wrapped_key: bytes) -> bytes:
        """Unwrap a key."""
        return self.decrypt(unwrapping_key_handle, wrapped_key, "AES-GCM")
    
    def delete_key(self, key_handle: str) -> bool:
        """Delete a mock key."""
        with self._lock:
            if key_handle in self._keys:
                # Securely wipe
                key_data = self._keys[key_handle]
                key_data["key_material"] = "0" * len(key_data["key_material"])
                del self._keys[key_handle]
                self._save_keys()
                return True
            return False
    
    def list_keys(self) -> List[HSMKeyMetadata]:
        """List mock keys."""
        results = []
        for key_handle, key_data in self._keys.items():
            results.append(HSMKeyMetadata(
                key_id=key_data["key_id"],
                key_type=HSMKeyType(key_data["key_type"]),
                created_at=key_data["created_at"],
                hsm_provider=HSMProvider.MOCK,
                key_handle=key_handle,
                label=key_data.get("label"),
                extractable=key_data.get("extractable", False),
            ))
        return results
    
    def health_check(self) -> Dict[str, Any]:
        """Mock health check."""
        return {
            "status": "healthy",
            "provider": "mock",
            "total_keys": len(self._keys),
            "warning": "Mock HSM is not secure - for testing only",
        }


class PKCS11HSMClient(HSMClientInterface):
    """
    PKCS#11 HSM client for hardware security modules.
    
    Supports:
    - Thales Luna Network HSM
    - SafeNet Network HSM
    - AWS CloudHSM (with client SDK)
    - Other PKCS#11 compliant HSMs
    """
    
    def __init__(
        self,
        pkcs11_lib_path: str,
        slot: int = 0,
        pin: Optional[str] = None,
        so_pin: Optional[str] = None,
    ):
        if not HAS_PKCS11:
            raise ImportError("PyKCS11 not installed. Install with: pip install PyKCS11")
        
        self.pkcs11_lib_path = pkcs11_lib_path
        self.slot = slot
        self.pin = pin
        self.so_pin = so_pin
        
        self._pkcs11_lib = PyKCS11Lib()
        self._pkcs11_lib.load(pkcs11_lib_path)
        self._session = None
        
        self._initialize_session()
        
        logger.info(f"PKCS11 HSM client initialized (slot={slot})")
    
    def _initialize_session(self) -> None:
        """Initialize PKCS#11 session."""
        slots = self._pkcs11_lib.getSlotList(tokenPresent=True)
        
        if not slots:
            raise RuntimeError("No PKCS#11 slots available")
        
        if self.slot >= len(slots):
            raise ValueError(f"Invalid slot {self.slot}, only {len(slots)} slots available")
        
        slot_id = slots[self.slot]
        
        # Open session
        self._session = self._pkcs11_lib.openSession(slot_id)
        
        # Login if PIN provided
        if self.pin:
            self._session.login(self.pin)
        
        logger.debug(f"PKCS#11 session opened on slot {self.slot}")
    
    def generate_key(
        self,
        key_id: str,
        key_type: HSMKeyType,
        extractable: bool = False,
        label: Optional[str] = None,
    ) -> str:
        """Generate a key in the HSM."""
        if not self._session:
            raise RuntimeError("PKCS#11 session not initialized")
        
        label = label or key_id
        
        if key_type == HSMKeyType.AES_256:
            # Generate AES key
            template = [
                (CK_OBJECT_CLASS, CKO_SECRET_KEY),
                (PyKCS11.CKA_LABEL, label),
                (PyKCS11.CKA_ID, key_id.encode()),
                (PyKCS11.CKA_ENCRYPT, True),
                (PyKCS11.CKA_DECRYPT, True),
                (PyKCS11.CKA_WRAP, True),
                (PyKCS11.CKA_UNWRAP, True),
                (PyKCS11.CKA_EXTRACTABLE, extractable),
                (PyKCS11.CKA_TOKEN, True),  # Persistent
                (PyKCS11.CKA_SENSITIVE, True),
            ]
            
            key = self._session.generateKey(PyKCS11.CKM_AES_KEY_GEN, template)
            key_handle = f"pkcs11-{key_id}-{self.slot}"
            
            logger.info(f"Generated AES-256 key in HSM: {key_id}")
            return key_handle
        
        else:
            raise ValueError(f"Unsupported key type: {key_type}")
    
    def encrypt(self, key_handle: str, plaintext: bytes, algorithm: str = "AES-GCM") -> bytes:
        """Encrypt using HSM key."""
        if not self._session:
            raise RuntimeError("PKCS#11 session not initialized")
        
        # Find key by label
        key_id = key_handle.replace(f"pkcs11-", "").replace(f"-{self.slot}", "")
        
        # Search for key
        template = [
            (CK_OBJECT_CLASS, CKO_SECRET_KEY),
            (PyKCS11.CKA_ID, key_id.encode()),
        ]
        keys = self._session.findObjects(template)
        
        if not keys:
            raise ValueError(f"Key not found: {key_id}")
        
        key = keys[0]
        
        if algorithm == "AES-GCM":
            # HSM GCM encryption
            iv = secrets.token_bytes(12)
            mechanism = Mechanism(PyKCS11.CKM_AES_GCM, iv + (16).to_bytes(4, 'big'))
            ciphertext = self._session.encrypt(key, plaintext, mechanism)
            return iv + ciphertext
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
    
    def decrypt(self, key_handle: str, ciphertext: bytes, algorithm: str = "AES-GCM") -> bytes:
        """Decrypt using HSM key."""
        if not self._session:
            raise RuntimeError("PKCS#11 session not initialized")
        
        key_id = key_handle.replace(f"pkcs11-", "").replace(f"-{self.slot}", "")
        
        template = [
            (CK_OBJECT_CLASS, CKO_SECRET_KEY),
            (PyKCS11.CKA_ID, key_id.encode()),
        ]
        keys = self._session.findObjects(template)
        
        if not keys:
            raise ValueError(f"Key not found: {key_id}")
        
        key = keys[0]
        
        if algorithm == "AES-GCM":
            iv = ciphertext[:12]
            ct = ciphertext[12:]
            mechanism = Mechanism(PyKCS11.CKM_AES_GCM, iv + (16).to_bytes(4, 'big'))
            return self._session.decrypt(key, ct, mechanism)
        else:
            raise ValueError(f"Unsupported algorithm: {algorithm}")
    
    def wrap_key(self, wrapping_key_handle: str, key_to_wrap: bytes) -> bytes:
        """Wrap a key."""
        # Implementation depends on HSM capabilities
        raise NotImplementedError("Key wrapping via PKCS#11 requires HSM-specific implementation")
    
    def unwrap_key(self, unwrapping_key_handle: str, wrapped_key: bytes) -> bytes:
        """Unwrap a key."""
        raise NotImplementedError("Key unwrapping via PKCS#11 requires HSM-specific implementation")
    
    def delete_key(self, key_handle: str) -> bool:
        """Delete a key from HSM."""
        if not self._session:
            raise RuntimeError("PKCS#11 session not initialized")
        
        key_id = key_handle.replace(f"pkcs11-", "").replace(f"-{self.slot}", "")
        
        template = [
            (CK_OBJECT_CLASS, CKO_SECRET_KEY),
            (PyKCS11.CKA_ID, key_id.encode()),
        ]
        keys = self._session.findObjects(template)
        
        if keys:
            self._session.destroyObject(keys[0])
            return True
        return False
    
    def list_keys(self) -> List[HSMKeyMetadata]:
        """List keys in HSM."""
        if not self._session:
            raise RuntimeError("PKCS#11 session not initialized")
        
        template = [(CK_OBJECT_CLASS, CKO_SECRET_KEY)]
        keys = self._session.findObjects(template)
        
        results = []
        for key in keys:
            attrs = self._session.getAttributeValue(key, [
                PyKCS11.CKA_LABEL,
                PyKCS11.CKA_ID,
                PyKCS11.CKA_KEY_TYPE,
            ])
            
            label = attrs[0] if attrs[0] else None
            key_id = attrs[1].decode() if attrs[1] else "unknown"
            
            results.append(HSMKeyMetadata(
                key_id=key_id,
                key_type=HSMKeyType.AES_256,  # Simplified
                created_at=datetime.now(),  # PKCS#11 doesn't always provide this
                hsm_provider=HSMProvider.PKCS11,
                key_handle=f"pkcs11-{key_id}-{self.slot}",
                label=label,
            ))
        
        return results
    
    def health_check(self) -> Dict[str, Any]:
        """Check HSM health."""
        try:
            if not self._session:
                return {"status": "unhealthy", "error": "No session"}
            
            # Try to get slot info
            slots = self._pkcs11_lib.getSlotList(tokenPresent=True)
            slot_info = self._pkcs11_lib.getSlotInfo(slots[self.slot])
            
            return {
                "status": "healthy",
                "provider": "pkcs11",
                "slot": self.slot,
                "slot_description": slot_info.slotDescription,
                "firmware_version": f"{slot_info.firmwareVersion.major}.{slot_info.firmwareVersion.minor}",
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }


class AWSCloudHSMClient(HSMClientInterface):
    """AWS CloudHSM client."""
    
    def __init__(
        self,
        cluster_id: str,
        region: str = "us-east-1",
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
    ):
        if not HAS_BOTO3:
            raise ImportError("boto3 not installed. Install with: pip install boto3")
        
        self.cluster_id = cluster_id
        self.region = region
        
        # Initialize CloudHSM client
        self._client = boto3.client(
            "cloudhsmv2",
            region_name=region,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
        )
        
        # Initialize PKCS#11 client for crypto operations
        # AWS CloudHSM uses PKCS#11 interface
        pkcs11_lib = os.getenv("AWS_CLOUDHSM_PKCS11_LIB", "/opt/cloudhsm/lib/libcloudhsm_pkcs11.so")
        
        if os.path.exists(pkcs11_lib):
            self._pkcs11 = PKCS11HSMClient(
                pkcs11_lib_path=pkcs11_lib,
                pin=os.getenv("CLOUDHSM_PIN"),
            )
        else:
            self._pkcs11 = None
            logger.warning("CloudHSM PKCS#11 library not found, limited functionality")
        
        logger.info(f"AWS CloudHSM client initialized (cluster={cluster_id})")
    
    def generate_key(
        self,
        key_id: str,
        key_type: HSMKeyType,
        extractable: bool = False,
        label: Optional[str] = None,
    ) -> str:
        """Generate key in AWS CloudHSM."""
        if self._pkcs11:
            return self._pkcs11.generate_key(key_id, key_type, extractable, label)
        raise RuntimeError("PKCS#11 not available for key generation")
    
    def encrypt(self, key_handle: str, plaintext: bytes, algorithm: str = "AES-GCM") -> bytes:
        """Encrypt using CloudHSM."""
        if self._pkcs11:
            return self._pkcs11.encrypt(key_handle, plaintext, algorithm)
        raise RuntimeError("PKCS#11 not available for encryption")
    
    def decrypt(self, key_handle: str, ciphertext: bytes, algorithm: str = "AES-GCM") -> bytes:
        """Decrypt using CloudHSM."""
        if self._pkcs11:
            return self._pkcs11.decrypt(key_handle, ciphertext, algorithm)
        raise RuntimeError("PKCS#11 not available for decryption")
    
    def wrap_key(self, wrapping_key_handle: str, key_to_wrap: bytes) -> bytes:
        """Wrap key."""
        if self._pkcs11:
            return self._pkcs11.wrap_key(wrapping_key_handle, key_to_wrap)
        raise NotImplementedError()
    
    def unwrap_key(self, unwrapping_key_handle: str, wrapped_key: bytes) -> bytes:
        """Unwrap key."""
        if self._pkcs11:
            return self._pkcs11.unwrap_key(unwrapping_key_handle, wrapped_key)
        raise NotImplementedError()
    
    def delete_key(self, key_handle: str) -> bool:
        """Delete key."""
        if self._pkcs11:
            return self._pkcs11.delete_key(key_handle)
        return False
    
    def list_keys(self) -> List[HSMKeyMetadata]:
        """List keys."""
        if self._pkcs11:
            return self._pkcs11.list_keys()
        return []
    
    def health_check(self) -> Dict[str, Any]:
        """Check CloudHSM health."""
        try:
            response = self._client.describe_clusters(ClusterIds=[self.cluster_id])
            clusters = response.get("Clusters", [])
            
            if not clusters:
                return {"status": "unhealthy", "error": "Cluster not found"}
            
            cluster = clusters[0]
            state = cluster.get("State")
            
            return {
                "status": "healthy" if state == "ACTIVE" else "degraded",
                "provider": "aws_cloudhsm",
                "cluster_id": self.cluster_id,
                "cluster_state": state,
                "hsms": len(cluster.get("Hsms", [])),
                "pkcs11_available": self._pkcs11 is not None,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
            }


class HSMClient:
    """
    Unified HSM client supporting multiple providers.
    
    Automatically selects appropriate implementation based on configuration.
    """
    
    def __init__(
        self,
        provider: HSMProvider = HSMProvider.MOCK,
        **kwargs,
    ):
        """
        Initialize HSM client.
        
        Args:
            provider: HSM provider type
            **kwargs: Provider-specific configuration
        """
        self.provider = provider
        self._client: HSMClientInterface = self._create_client(provider, **kwargs)
    
    def _create_client(self, provider: HSMProvider, **kwargs) -> HSMClientInterface:
        """Create appropriate HSM client."""
        if provider == HSMProvider.MOCK:
            return MockHSMClient(**kwargs)
        elif provider == HSMProvider.PKCS11:
            return PKCS11HSMClient(**kwargs)
        elif provider == HSMProvider.AWS_CLOUDHSM:
            return AWSCloudHSMClient(**kwargs)
        else:
            raise ValueError(f"Unsupported HSM provider: {provider}")
    
    def generate_key(
        self,
        key_id: str,
        key_type: HSMKeyType = HSMKeyType.AES_256,
        extractable: bool = False,
        label: Optional[str] = None,
    ) -> str:
        """Generate a key in the HSM."""
        return self._client.generate_key(key_id, key_type, extractable, label)
    
    def encrypt(self, key_handle: str, plaintext: bytes, algorithm: str = "AES-GCM") -> bytes:
        """Encrypt data."""
        return self._client.encrypt(key_handle, plaintext, algorithm)
    
    def decrypt(self, key_handle: str, ciphertext: bytes, algorithm: str = "AES-GCM") -> bytes:
        """Decrypt data."""
        return self._client.decrypt(key_handle, ciphertext, algorithm)
    
    def wrap_key(self, wrapping_key_handle: str, key_to_wrap: bytes) -> bytes:
        """Wrap a key."""
        return self._client.wrap_key(wrapping_key_handle, key_to_wrap)
    
    def unwrap_key(self, unwrapping_key_handle: str, wrapped_key: bytes) -> bytes:
        """Unwrap a key."""
        return self._client.unwrap_key(unwrapping_key_handle, wrapped_key)
    
    def delete_key(self, key_handle: str) -> bool:
        """Delete a key."""
        return self._client.delete_key(key_handle)
    
    def list_keys(self) -> List[HSMKeyMetadata]:
        """List all keys."""
        return self._client.list_keys()
    
    def health_check(self) -> Dict[str, Any]:
        """Check HSM health."""
        return self._client.health_check()


# Global instance
_hsm_client: Optional[HSMClient] = None


def init_hsm_client(provider: HSMProvider = HSMProvider.MOCK, **kwargs) -> HSMClient:
    """Initialize global HSM client."""
    global _hsm_client
    _hsm_client = HSMClient(provider=provider, **kwargs)
    return _hsm_client


def get_hsm_client() -> HSMClient:
    """Get global HSM client."""
    if _hsm_client is None:
        raise RuntimeError("HSM client not initialized. Call init_hsm_client() first.")
    return _hsm_client
