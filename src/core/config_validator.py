"""
Configuration Validation Module

Validates all required environment variables and configuration values at startup.
Ensures the service fails fast with clear error messages if configuration is invalid.

Usage:
    from core.config_validator import validate_configuration
    
    # At application startup (before any other initialization)
    validate_configuration()
"""

import os
import sys
import re
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from enum import Enum
from urllib.parse import urlparse


class ConfigValidationError(Exception):
    """Raised when configuration validation fails."""
    pass


class ValidationType(Enum):
    """Types of validation checks."""
    REQUIRED = "required"
    FORMAT = "format"
    RANGE = "range"
    ENUM = "enum"
    URL = "url"
    PORT = "port"
    DEPENDENCY = "dependency"


@dataclass
class ValidationRule:
    """Defines a validation rule for a configuration variable."""
    name: str
    required: bool = False
    validation_type: Optional[ValidationType] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    allowed_values: Optional[List[str]] = None
    pattern: Optional[str] = None
    default: Optional[str] = None
    description: str = ""
    example: str = ""
    depends_on: Optional[List[str]] = None


class ConfigValidator:
    """
    Validates application configuration at startup.
    
    Performs comprehensive validation of environment variables and configuration values.
    Fails fast with clear, actionable error messages.
    """
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
        self.validated_config: Dict[str, Any] = {}
        
    def define_rules(self) -> List[ValidationRule]:
        """
        Define all configuration validation rules.
        
        Returns:
            List of ValidationRule objects
        """
        return [
            # Application Configuration
            ValidationRule(
                name="ENVIRONMENT",
                required=False,
                validation_type=ValidationType.ENUM,
                allowed_values=["development", "staging", "production", "test"],
                default="development",
                description="Application environment",
                example="production"
            ),
            ValidationRule(
                name="DEBUG",
                required=False,
                validation_type=ValidationType.ENUM,
                allowed_values=["true", "false", "True", "False", "1", "0"],
                default="false",
                description="Debug mode flag",
                example="false"
            ),
            
            # Redis Configuration
            ValidationRule(
                name="REDIS_HOST",
                required=False,
                default="localhost",
                description="Redis server hostname",
                example="localhost"
            ),
            ValidationRule(
                name="REDIS_PORT",
                required=False,
                validation_type=ValidationType.PORT,
                min_value=1,
                max_value=65535,
                default="6379",
                description="Redis server port",
                example="6379"
            ),
            ValidationRule(
                name="REDIS_URL",
                required=False,
                validation_type=ValidationType.URL,
                default="redis://localhost:6379",
                description="Redis connection URL",
                example="redis://localhost:6379"
            ),
            
            # API Configuration
            ValidationRule(
                name="API_HOST",
                required=False,
                default="0.0.0.0",  # nosec B104
                description="API server bind address",
                example="0.0.0.0"  # nosec B104
            ),
            ValidationRule(
                name="API_PORT",
                required=False,
                validation_type=ValidationType.PORT,
                min_value=1,
                max_value=65535,
                default="8002",
                description="API server port",
                example="8002"
            ),
            
            # Logging Configuration
            ValidationRule(
                name="LOG_LEVEL",
                required=False,
                validation_type=ValidationType.ENUM,
                allowed_values=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", 
                               "debug", "info", "warning", "error", "critical"],
                default="INFO",
                description="Logging verbosity level",
                example="INFO"
            ),
            
            # Security Configuration (Metrics Endpoint)
            ValidationRule(
                name="METRICS_USER",
                required=False,
                description="Username for metrics endpoint authentication",
                example="metrics_monitor"
            ),
            ValidationRule(
                name="METRICS_PASSWORD",
                required=False,
                description="Password for metrics endpoint authentication",
                example="<use-strong-random-password>"
            ),
            
            # CORS Configuration
            ValidationRule(
                name="ALLOWED_ORIGINS",
                required=False,
                default="http://localhost:3000,http://localhost:8000",
                description="Comma-separated list of allowed CORS origins",
                example="http://localhost:3000,https://app.example.com"
            ),
            
            # Optional: JWT Configuration
            ValidationRule(
                name="JWT_SECRET_KEY",
                required=False,
                description="Secret key for JWT token signing (min 32 characters)",
                example="<use-secrets.token_urlsafe(32)>"
            ),
            
            # Optional: Timeout Configuration
            ValidationRule(
                name="TIMEOUT_MODEL_LOAD",
                required=False,
                validation_type=ValidationType.RANGE,
                min_value=1,
                max_value=3600,
                default="300",
                description="Model loading timeout in seconds",
                example="300"
            ),
            ValidationRule(
                name="TIMEOUT_INFERENCE",
                required=False,
                validation_type=ValidationType.RANGE,
                min_value=1,
                max_value=600,
                default="60",
                description="Inference timeout in seconds",
                example="60"
            ),
            ValidationRule(
                name="TIMEOUT_REDIS",
                required=False,
                validation_type=ValidationType.RANGE,
                min_value=1,
                max_value=60,
                default="5",
                description="Redis operation timeout in seconds",
                example="5"
            ),
            ValidationRule(
                name="TIMEOUT_FILE_IO",
                required=False,
                validation_type=ValidationType.RANGE,
                min_value=1,
                max_value=300,
                default="30",
                description="File I/O timeout in seconds",
                example="30"
            ),
        ]
    
    def validate_required(self, rule: ValidationRule) -> bool:
        """
        Validate that a required variable exists and is not empty.
        
        Args:
            rule: Validation rule
            
        Returns:
            True if valid, False otherwise
        """
        value = os.environ.get(rule.name)
        
        if rule.required:
            if value is None:
                self.errors.append(
                    f"❌ MISSING REQUIRED: '{rule.name}' is required but not set.\n"
                    f"   Description: {rule.description}\n"
                    f"   Example: {rule.example}\n"
                    f"   Fix: Set environment variable: export {rule.name}={rule.example}"
                )
                return False
            
            if not value.strip():
                self.errors.append(
                    f"❌ EMPTY VALUE: '{rule.name}' is set but empty.\n"
                    f"   Description: {rule.description}\n"
                    f"   Example: {rule.example}"
                )
                return False
        
        # Use default if not set
        if value is None and rule.default is not None:
            self.validated_config[rule.name] = rule.default
            return True
        
        if value is not None:
            self.validated_config[rule.name] = value
        
        return True
    
    def validate_enum(self, rule: ValidationRule) -> bool:
        """
        Validate that a value matches one of the allowed values.
        
        Args:
            rule: Validation rule
            
        Returns:
            True if valid, False otherwise
        """
        value = self.validated_config.get(rule.name)
        
        if value is None:
            return True  # Already handled by validate_required
        
        if rule.allowed_values and value not in rule.allowed_values:
            self.errors.append(
                f"❌ INVALID VALUE: '{rule.name}' has invalid value '{value}'.\n"
                f"   Allowed values: {', '.join(rule.allowed_values)}\n"
                f"   Example: {rule.example}"
            )
            return False
        
        return True
    
    def validate_range(self, rule: ValidationRule) -> bool:
        """
        Validate that a numeric value is within the allowed range.
        
        Args:
            rule: Validation rule
            
        Returns:
            True if valid, False otherwise
        """
        value = self.validated_config.get(rule.name)
        
        if value is None:
            return True  # Already handled by validate_required
        
        try:
            numeric_value = float(value)
            
            if rule.min_value is not None and numeric_value < rule.min_value:
                self.errors.append(
                    f"❌ OUT OF RANGE: '{rule.name}' value {numeric_value} is below minimum {rule.min_value}.\n"
                    f"   Valid range: {rule.min_value} to {rule.max_value}\n"
                    f"   Example: {rule.example}"
                )
                return False
            
            if rule.max_value is not None and numeric_value > rule.max_value:
                self.errors.append(
                    f"❌ OUT OF RANGE: '{rule.name}' value {numeric_value} exceeds maximum {rule.max_value}.\n"
                    f"   Valid range: {rule.min_value} to {rule.max_value}\n"
                    f"   Example: {rule.example}"
                )
                return False
            
        except ValueError:
            self.errors.append(
                f"❌ INVALID FORMAT: '{rule.name}' value '{value}' is not a valid number.\n"
                f"   Expected: numeric value\n"
                f"   Example: {rule.example}"
            )
            return False
        
        return True
    
    def validate_port(self, rule: ValidationRule) -> bool:
        """
        Validate that a port number is valid.
        
        Args:
            rule: Validation rule
            
        Returns:
            True if valid, False otherwise
        """
        value = self.validated_config.get(rule.name)
        
        if value is None:
            return True  # Already handled by validate_required
        
        try:
            port = int(value)
            
            if port < 1 or port > 65535:
                self.errors.append(
                    f"❌ INVALID PORT: '{rule.name}' value {port} is not a valid port number.\n"
                    f"   Valid range: 1 to 65535\n"
                    f"   Example: {rule.example}"
                )
                return False
            
        except ValueError:
            self.errors.append(
                f"❌ INVALID FORMAT: '{rule.name}' value '{value}' is not a valid port number.\n"
                f"   Expected: integer between 1 and 65535\n"
                f"   Example: {rule.example}"
            )
            return False
        
        return True
    
    def validate_url(self, rule: ValidationRule) -> bool:
        """
        Validate that a URL is properly formatted.
        
        Args:
            rule: Validation rule
            
        Returns:
            True if valid, False otherwise
        """
        value = self.validated_config.get(rule.name)
        
        if value is None:
            return True  # Already handled by validate_required
        
        try:
            result = urlparse(value)
            
            if not all([result.scheme, result.netloc]):
                self.errors.append(
                    f"❌ INVALID URL: '{rule.name}' value '{value}' is not a valid URL.\n"
                    f"   Expected format: scheme://host:port\n"
                    f"   Example: {rule.example}"
                )
                return False
            
        except Exception as e:
            self.errors.append(
                f"❌ INVALID URL: '{rule.name}' value '{value}' cannot be parsed.\n"
                f"   Error: {str(e)}\n"
                f"   Example: {rule.example}"
            )
            return False
        
        return True
    
    def validate_pattern(self, rule: ValidationRule) -> bool:
        """
        Validate that a value matches a regex pattern.
        
        Args:
            rule: Validation rule
            
        Returns:
            True if valid, False otherwise
        """
        value = self.validated_config.get(rule.name)
        
        if value is None or rule.pattern is None:
            return True
        
        if not re.match(rule.pattern, value):
            self.errors.append(
                f"❌ INVALID FORMAT: '{rule.name}' value '{value}' does not match required pattern.\n"
                f"   Pattern: {rule.pattern}\n"
                f"   Example: {rule.example}"
            )
            return False
        
        return True
    
    def validate_dependencies(self, rule: ValidationRule) -> bool:
        """
        Validate that dependent configuration is consistent.
        
        Args:
            rule: Validation rule
            
        Returns:
            True if valid, False otherwise
        """
        if rule.depends_on is None:
            return True
        
        value = self.validated_config.get(rule.name)
        
        if value is not None:
            for dependency in rule.depends_on:
                if dependency not in self.validated_config:
                    self.errors.append(
                        f"❌ MISSING DEPENDENCY: '{rule.name}' requires '{dependency}' to be set.\n"
                        f"   Fix: Set {dependency} environment variable"
                    )
                    return False
        
        return True
    
    def validate_security_credentials(self) -> bool:
        """
        Validate security-related credentials.
        
        Returns:
            True if valid, False otherwise
        """
        metrics_user = self.validated_config.get("METRICS_USER")
        metrics_password = self.validated_config.get("METRICS_PASSWORD")
        
        # If one is set, both must be set
        if (metrics_user and not metrics_password) or (metrics_password and not metrics_user):
            self.errors.append(
                "❌ INCOMPLETE CREDENTIALS: Both METRICS_USER and METRICS_PASSWORD must be set together.\n"
                "   Fix: Set both environment variables or neither"
            )
            return False
        
        # Warn about weak passwords
        if metrics_password:
            if len(metrics_password) < 12:
                self.warnings.append(
                    f"⚠️  WEAK PASSWORD: METRICS_PASSWORD is only {len(metrics_password)} characters.\n"
                    "   Recommendation: Use at least 16 characters for production"
                )
            
            # Check for common weak passwords
            weak_passwords = ["admin", "password", "12345", "123456", "test"]
            if metrics_password.lower() in weak_passwords:
                self.warnings.append(
                    "⚠️  INSECURE PASSWORD: METRICS_PASSWORD uses a common weak password.\n"
                    "   Recommendation: Use a strong, randomly-generated password\n"
                    "   Generate: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
                )
        
        # Validate JWT secret if present
        jwt_secret = self.validated_config.get("JWT_SECRET_KEY")
        if jwt_secret and len(jwt_secret) < 32:
            self.errors.append(
                f"❌ WEAK JWT SECRET: JWT_SECRET_KEY must be at least 32 characters (current: {len(jwt_secret)}).\n"
                "   Fix: Generate a strong secret: python -c \"import secrets; print(secrets.token_urlsafe(32))\""
            )
            return False
        
        return True
    
    def validate_all(self) -> bool:
        """
        Run all validation checks.
        
        Returns:
            True if all validations pass, False otherwise
        """
        rules = self.define_rules()
        
        # Phase 1: Check required variables and apply defaults
        for rule in rules:
            self.validate_required(rule)
        
        # Phase 2: Validate formats and values
        for rule in rules:
            if rule.name not in self.validated_config:
                continue
            
            if rule.validation_type == ValidationType.ENUM:
                self.validate_enum(rule)
            elif rule.validation_type == ValidationType.RANGE:
                self.validate_range(rule)
            elif rule.validation_type == ValidationType.PORT:
                self.validate_port(rule)
            elif rule.validation_type == ValidationType.URL:
                self.validate_url(rule)
            
            if rule.pattern:
                self.validate_pattern(rule)
        
        # Phase 3: Validate dependencies
        for rule in rules:
            self.validate_dependencies(rule)
        
        # Phase 4: Validate security credentials
        self.validate_security_credentials()
        
        return len(self.errors) == 0
    
    def print_report(self):
        """Print validation report with errors and warnings."""
        print("\n" + "=" * 80)
        print("🔍 CONFIGURATION VALIDATION REPORT")
        print("=" * 80)
        
        if self.errors:
            print(f"\n❌ VALIDATION FAILED: {len(self.errors)} error(s) found\n")
            for error in self.errors:
                print(error)
                print()
        
        if self.warnings:
            print(f"\n⚠️  WARNINGS: {len(self.warnings)} warning(s)\n")
            for warning in self.warnings:
                print(warning)
                print()
        
        if not self.errors and not self.warnings:
            print("\n✅ ALL VALIDATIONS PASSED")
            print(f"   Validated {len(self.validated_config)} configuration variables")
        
        print("=" * 80 + "\n")


def validate_configuration() -> Dict[str, Any]:
    """
    Validate all configuration at startup.
    
    This function should be called at the very beginning of application startup,
    before any other initialization occurs.
    
    Returns:
        Dictionary of validated configuration values
        
    Raises:
        SystemExit: If validation fails (exits with code 1)
    """
    validator = ConfigValidator()
    
    print("\n🚀 Starting configuration validation...")
    
    if not validator.validate_all():
        validator.print_report()
        print("❌ Configuration validation failed. Service cannot start.")
        print("   Fix the errors above and try again.\n")
        sys.exit(1)
    
    validator.print_report()
    
    return validator.validated_config


if __name__ == "__main__":
    # Allow running this module directly for testing
    try:
        config = validate_configuration()
        print("✅ Configuration validation successful!")
        print(f"   Validated {len(config)} variables")
    except SystemExit as e:
        print(f"\n❌ Validation failed with exit code {e.code}")
        sys.exit(e.code)
