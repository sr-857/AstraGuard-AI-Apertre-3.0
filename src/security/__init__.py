"""
AstraGuard Security Module - Advanced Encryption and Key Management

Provides comprehensive encryption capabilities:
- Envelope encryption with AES-256-GCM
- HSM integration (PKCS#11, AWS CloudHSM, Azure, GCP)
- Automatic key rotation
- Shamir's Secret Sharing for key recovery
- FIPS 140-2 compliance
- Field-level encryption
- Zero-knowledge architecture
- FastAPI middleware integration

Example Usage:
    from security import (
        init_encryption_system,
        encrypt_data,
        decrypt_data,
        get_key_hierarchy,
    )

    # Initialize the encryption system
    await init_encryption_system(
        master_key=os.getenv("MASTER_KEY"),
        enable_hsm=True,
        hsm_provider=HSMProvider.AWS_CLOUDHSM,
    )

    # Encrypt data
    encrypted, dek = encrypt_data("sensitive data")

    # Decrypt data
    plaintext = decrypt_data(encrypted, dek)
"""

__version__ = "1.0.0"

# Core encryption
from .encryption import (
    EncryptionEngine,
    EncryptedData,
    DataEncryptionKey,
    KeyEncryptionKey,
    EncryptionAlgorithm,
    encrypt_data,
    decrypt_data,
    init_encryption_engine,
    get_encryption_engine,
)

# Key management
from .key_management import (
    KeyHierarchy,
    KeyMetadata,
    KeyType,
    KeyStatus,
    ManagedKey,
    init_key_hierarchy,
    get_key_hierarchy,
)

# HSM client
from .hsm_client import (
    HSMClient,
    HSMProvider,
    HSMKeyType,
    HSMKeyMetadata,
    MockHSMClient,
    PKCS11HSMClient,
    AWSCloudHSMClient,
    init_hsm_client,
    get_hsm_client,
)

# Key rotation
from .key_rotation import (
    KeyRotationManager,
    RotationPolicy,
    RotationEvent,
    RotationTrigger,
    init_key_rotation_manager,
    get_key_rotation_manager,
    start_automatic_rotation,
    stop_automatic_rotation,
    emergency_rotate_all,
)

# Key recovery
from .key_recovery import (
    KeyRecoveryManager,
    KeyShare,
    RecoveryCeremony,
    RecoveryStatus,
    ShamirSecretSharing,
    init_key_recovery_manager,
    get_key_recovery_manager,
    split_key_for_recovery,
    initiate_key_recovery,
    submit_recovery_share,
)

# Compliance
from .compliance import (
    ComplianceManager,
    ComplianceStandard,
    AuditEvent,
    AuditEventType,
    AuditLogger,
    FIPSMode,
    ComplianceReport,
    init_compliance_manager,
    get_compliance_manager,
    log_key_event,
    log_encryption_event,
)

# Field-level encryption
from .field_encryption import (
    FieldEncryptionEngine,
    FieldEncryptionMapper,
    FieldEncryptionConfig,
    FieldEncryptionMode,
    encrypted_field,
    init_field_encryption,
    get_field_encryption,
    encrypt_sensitive_fields,
    decrypt_sensitive_fields,
)

# Zero-knowledge
from .zero_knowledge import (
    ZeroKnowledgeManager,
    ClientSideEncryption,
    ServerBlindProcessor,
    ClientKeyMaterial,
    EncryptedPayload,
    ZKEncryptionMode,
    init_zero_knowledge,
    get_zero_knowledge_manager,
    generate_client_keys,
    client_encrypt,
    client_decrypt,
)

# Middleware
from .encryption_middleware import (
    EncryptionMiddleware,
    EncryptionMiddlewareConfig,
    EncryptionAtRestMiddleware,
    encrypt_response,
    setup_encryption_middleware,
)

import logging
import os
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


async def init_encryption_system(
    master_key: Optional[str] = None,
    storage_path: str = ".encryption",
    enable_hsm: bool = False,
    hsm_provider: HSMProvider = HSMProvider.MOCK,
    hsm_config: Optional[Dict[str, Any]] = None,
    fips_enabled: bool = False,
    auto_rotation: bool = True,
    compliance_standards: Optional[list] = None,
) -> Dict[str, Any]:
    """
    Initialize the complete encryption system.
    
    This is the main entry point for setting up all encryption capabilities.
    
    Args:
        master_key: Master encryption key (auto-generated if None)
        storage_path: Path for key storage
        enable_hsm: Enable HSM integration
        hsm_provider: HSM provider type
        hsm_config: HSM-specific configuration
        fips_enabled: Enable FIPS 140-2 mode
        auto_rotation: Enable automatic key rotation
        compliance_standards: List of compliance standards to enforce
    
    Returns:
        Dictionary with initialized components status
    
    Example:
        >>> status = await init_encryption_system(
        ...     master_key="my-secret-master-key",
        ...     enable_hsm=True,
        ...     hsm_provider=HSMProvider.AWS_CLOUDHSM,
        ...     fips_enabled=True,
        ... )
        >>> print(status["encryption_engine"]["status"])
        'initialized'
    """
    results = {
        "encryption_engine": {"status": "pending"},
        "key_hierarchy": {"status": "pending"},
        "hsm_client": {"status": "pending"},
        "key_rotation": {"status": "pending"},
        "key_recovery": {"status": "pending"},
        "compliance": {"status": "pending"},
        "field_encryption": {"status": "pending"},
        "zero_knowledge": {"status": "pending"},
    }
    
    try:
        # Initialize compliance first (for audit logging)
        compliance = init_compliance_manager(
            fips_enabled=fips_enabled,
            audit_retention_days=365,
            standards=set(compliance_standards or [ComplianceStandard.FIPS_140_2]),
        )
        results["compliance"] = {
            "status": "initialized",
            "fips_enabled": fips_enabled,
        }
        logger.info(f"Compliance manager initialized (FIPS={fips_enabled})")
        
        # Initialize HSM if enabled
        if enable_hsm:
            try:
                hsm_config = hsm_config or {}
                hsm = init_hsm_client(provider=hsm_provider, **hsm_config)
                hsm_health = hsm.health_check()
                results["hsm_client"] = {
                    "status": "initialized",
                    "provider": hsm_provider.value,
                    "health": hsm_health,
                }
                logger.info(f"HSM client initialized ({hsm_provider.value})")
            except Exception as e:
                logger.error(f"Failed to initialize HSM: {e}")
                results["hsm_client"] = {
                    "status": "failed",
                    "error": str(e),
                }
                # Continue without HSM
                enable_hsm = False
        
        # Initialize key hierarchy
        key_hierarchy = init_key_hierarchy(
            storage_path=f"{storage_path}/keys",
            master_key=master_key.encode() if master_key else None,
            enable_hsm=enable_hsm,
        )
        results["key_hierarchy"] = {
            "status": "initialized",
            "kek_id": key_hierarchy._current_kek.metadata.key_id if key_hierarchy._current_kek else None,
        }
        logger.info("Key hierarchy initialized")
        
        # Initialize encryption engine
        encryption_engine = init_encryption_engine(
            master_key=master_key.encode() if master_key else None,
            use_hardware_acceleration=True,
        )
        results["encryption_engine"] = {
            "status": "initialized",
            "hardware_acceleration": encryption_engine.use_hardware_acceleration,
        }
        logger.info("Encryption engine initialized")
        
        # Initialize key rotation
        rotation_manager = init_key_rotation_manager(
            key_hierarchy=key_hierarchy,
            hsm_client=get_hsm_client() if enable_hsm else None,
            storage_path=f"{storage_path}/rotations",
        )
        results["key_rotation"] = {
            "status": "initialized",
            "auto_rotation": auto_rotation,
        }
        logger.info("Key rotation manager initialized")
        
        if auto_rotation:
            start_automatic_rotation()
            logger.info("Automatic key rotation started")
        
        # Initialize key recovery
        recovery_manager = init_key_recovery_manager(
            storage_path=f"{storage_path}/recovery",
        )
        results["key_recovery"] = {
            "status": "initialized",
            "default_threshold": recovery_manager.default_threshold,
        }
        logger.info("Key recovery manager initialized")
        
        # Initialize field encryption
        field_encryption = init_field_encryption(
            encryption_engine=encryption_engine,
        )
        results["field_encryption"] = {
            "status": "initialized",
        }
        logger.info("Field encryption engine initialized")
        
        # Initialize zero-knowledge
        zk_manager = init_zero_knowledge()
        results["zero_knowledge"] = {
            "status": "initialized",
        }
        logger.info("Zero-knowledge manager initialized")
        
        # Log system initialization
        log_encryption_event(
            "init_encryption_system",
            details={
                "fips_enabled": fips_enabled,
                "hsm_enabled": enable_hsm,
                "auto_rotation": auto_rotation,
            },
        )
        
        logger.info("Encryption system fully initialized")
        
    except Exception as e:
        logger.error(f"Failed to initialize encryption system: {e}")
        results["error"] = str(e)
        raise
    
    return results


def get_encryption_status() -> Dict[str, Any]:
    """
    Get current status of the encryption system.
    
    Returns:
        Dictionary with component statuses and health information
    """
    status = {
        "initialized": True,
        "components": {},
    }
    
    try:
        status["components"]["encryption_engine"] = get_encryption_engine().health_check()
    except Exception as e:
        status["components"]["encryption_engine"] = {"error": str(e)}
    
    try:
        status["components"]["key_hierarchy"] = get_key_hierarchy().health_check()
    except Exception as e:
        status["components"]["key_hierarchy"] = {"error": str(e)}
    
    try:
        status["components"]["compliance"] = get_compliance_manager().health_check()
    except Exception as e:
        status["components"]["compliance"] = {"error": str(e)}
    
    try:
        status["components"]["key_rotation"] = get_key_rotation_manager().get_status()
    except Exception as e:
        status["components"]["key_rotation"] = {"error": str(e)}
    
    try:
        status["components"]["key_recovery"] = get_key_recovery_manager().health_check()
    except Exception as e:
        status["components"]["key_recovery"] = {"error": str(e)}
    
    return status


__all__ = [
    # Version
    "__version__",
    
    # Core encryption
    "EncryptionEngine",
    "EncryptedData",
    "DataEncryptionKey",
    "KeyEncryptionKey",
    "EncryptionAlgorithm",
    "encrypt_data",
    "decrypt_data",
    "init_encryption_engine",
    "get_encryption_engine",
    
    # Key management
    "KeyHierarchy",
    "KeyMetadata",
    "KeyType",
    "KeyStatus",
    "ManagedKey",
    "init_key_hierarchy",
    "get_key_hierarchy",
    
    # HSM
    "HSMClient",
    "HSMProvider",
    "HSMKeyType",
    "HSMKeyMetadata",
    "MockHSMClient",
    "PKCS11HSMClient",
    "AWSCloudHSMClient",
    "init_hsm_client",
    "get_hsm_client",
    
    # Key rotation
    "KeyRotationManager",
    "RotationPolicy",
    "RotationEvent",
    "RotationTrigger",
    "init_key_rotation_manager",
    "get_key_rotation_manager",
    "start_automatic_rotation",
    "stop_automatic_rotation",
    "emergency_rotate_all",
    
    # Key recovery
    "KeyRecoveryManager",
    "KeyShare",
    "RecoveryCeremony",
    "RecoveryStatus",
    "ShamirSecretSharing",
    "init_key_recovery_manager",
    "get_key_recovery_manager",
    "split_key_for_recovery",
    "initiate_key_recovery",
    "submit_recovery_share",
    
    # Compliance
    "ComplianceManager",
    "ComplianceStandard",
    "AuditEvent",
    "AuditEventType",
    "AuditLogger",
    "FIPSMode",
    "ComplianceReport",
    "init_compliance_manager",
    "get_compliance_manager",
    "log_key_event",
    "log_encryption_event",
    
    # Field encryption
    "FieldEncryptionEngine",
    "FieldEncryptionMapper",
    "FieldEncryptionConfig",
    "FieldEncryptionMode",
    "encrypted_field",
    "init_field_encryption",
    "get_field_encryption",
    "encrypt_sensitive_fields",
    "decrypt_sensitive_fields",
    
    # Zero-knowledge
    "ZeroKnowledgeManager",
    "ClientSideEncryption",
    "ServerBlindProcessor",
    "ClientKeyMaterial",
    "EncryptedPayload",
    "ZKEncryptionMode",
    "init_zero_knowledge",
    "get_zero_knowledge_manager",
    "generate_client_keys",
    "client_encrypt",
    "client_decrypt",
    
    # Middleware
    "EncryptionMiddleware",
    "EncryptionMiddlewareConfig",
    "EncryptionAtRestMiddleware",
    "encrypt_response",
    "setup_encryption_middleware",
    
    # System initialization
    "init_encryption_system",
    "get_encryption_status",
]
