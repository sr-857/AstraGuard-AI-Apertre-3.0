# -*- coding: utf-8 -*-
"""
Security Package - Secrets and Authentication Adapters

This package provides pluggable adapters for secrets management across different
environments (development, staging, production).
"""

from security.secrets_adapter import (
    SecretsAdapter,
    DevFileAdapter,
    VaultAdapter,
    AWSSecretsAdapter,
    get_adapter,
    get_secret,
    list_secrets,
)

__all__ = [
    "SecretsAdapter",
    "DevFileAdapter",
    "VaultAdapter",
    "AWSSecretsAdapter",
    "get_adapter",
    "get_secret",
    "list_secrets",
]
