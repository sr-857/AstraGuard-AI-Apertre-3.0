"""Enhanced error handling for Security Engine with actionable suggestions."""

import logging
from typing import Optional, Dict, Any, List
from pathlib import Path

logger = logging.getLogger(__name__)


class ActionableErrorMixin:
    """Mixin class that provides actionable error suggestions."""

    def get_actionable_suggestions(self) -> List[str]:
        """Return a list of actionable suggestions for resolving the error.

        Returns:
            List of specific, actionable steps the user can take
        """
        return getattr(self, '_suggestions', [])

    def get_error_context(self) -> Dict[str, Any]:
        """Return contextual information about the error.

        Returns:
            Dictionary with error context information
        """
        return getattr(self, '_context', {})

    def __str__(self) -> str:
        """Enhanced string representation with suggestions."""
        base_msg = super().__str__()
        suggestions = self.get_actionable_suggestions()

        if suggestions:
            suggestion_text = "\n\nActionable Suggestions:\n" + "\n".join(
                f"• {suggestion}" for suggestion in suggestions
            )
            return base_msg + suggestion_text

        return base_msg


class SecurityEngineError(Exception, ActionableErrorMixin):
    """Base exception class for Security Engine errors with actionable suggestions."""

    def __init__(
        self,
        message: str,
        suggestions: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
        error_code: Optional[str] = None
    ):
        """Initialize SecurityEngineError with enhanced error information.

        Args:
            message: The main error message
            suggestions: List of actionable suggestions for resolution
            context: Additional context information about the error
            error_code: Optional error code for categorization
        """
        super().__init__(message)
        self._suggestions = suggestions or []
        self._context = context or {}
        self.error_code = error_code

        # Log the error with context
        logger.error(
            f"SecurityEngineError [{error_code}]: {message}",
            extra={
                "error_code": error_code,
                "suggestions": self._suggestions,
                "context": self._context
            }
        )


class FileOperationError(SecurityEngineError):
    """Error related to file operations (read/write feedback files)."""

    def __init__(
        self,
        operation: str,
        file_path: Path,
        original_error: Optional[Exception] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """Initialize FileOperationError with file-specific suggestions.

        Args:
            operation: The file operation that failed (read/write)
            file_path: Path to the file that caused the error
            original_error: The original exception that was caught
            context: Additional context information
        """
        message = f"File {operation} operation failed for {file_path.name}"

        if original_error:
            message += f": {type(original_error).__name__}: {original_error}"

        suggestions = [
            f"Check if the file path '{file_path}' exists and is accessible",
            f"Verify that the directory '{file_path.parent}' has write permissions" if operation == "write"
            else f"Verify that the file '{file_path}' exists and is readable",
            "Ensure no other processes are locking the file",
            "Check available disk space if writing files",
            "Try running the application with elevated permissions if access is denied"
        ]

        # Add specific suggestions based on error type
        if original_error:
            if isinstance(original_error, PermissionError):
                suggestions.insert(0, "File permission denied - run with appropriate permissions")
            elif isinstance(original_error, FileNotFoundError):
                suggestions.insert(0, f"File not found - ensure '{file_path}' exists")
            elif isinstance(original_error, OSError):
                suggestions.insert(0, "Operating system error - check file system integrity")

        error_context = {
            "operation": operation,
            "file_path": str(file_path),
            "file_exists": file_path.exists(),
            "parent_exists": file_path.parent.exists(),
            "original_error_type": type(original_error).__name__ if original_error else None
        }
        if context:
            error_context.update(context)

        super().__init__(
            message=message,
            suggestions=suggestions,
            context=error_context,
            error_code="FILE_OP_ERROR"
        )


class MemoryOperationError(SecurityEngineError):
    """Error related to memory/adaptive memory operations."""

    def __init__(
        self,
        operation: str,
        memory_type: str = "adaptive_memory",
        missing_method: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """Initialize MemoryOperationError with memory-specific suggestions.

        Args:
            operation: The memory operation that failed
            memory_type: Type of memory system (adaptive_memory, etc.)
            missing_method: Name of the missing method if applicable
            context: Additional context information
        """
        message = f"Memory operation '{operation}' failed"

        if missing_method:
            message += f" - method '{missing_method}' not available in {memory_type}"

        suggestions = [
            f"Ensure {memory_type} is properly initialized and configured",
            "Check that all required dependencies are installed",
            "Verify memory configuration in your settings",
            "Restart the application to reinitialize memory systems"
        ]

        if missing_method:
            suggestions.insert(0, f"Implement or import the missing method '{missing_method}' in {memory_type}")
            suggestions.insert(1, f"Check {memory_type} documentation for required interface methods")

        error_context = {
            "operation": operation,
            "memory_type": memory_type,
            "missing_method": missing_method
        }
        if context:
            error_context.update(context)

        super().__init__(
            message=message,
            suggestions=suggestions,
            context=error_context,
            error_code="MEMORY_OP_ERROR"
        )


class PolicyUpdateError(SecurityEngineError):
    """Error related to policy update operations."""

    def __init__(
        self,
        operation: str,
        reason: str,
        module_name: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """Initialize PolicyUpdateError with policy-specific suggestions.

        Args:
            operation: The policy operation that failed
            reason: The reason for the failure
            module_name: Name of the module that failed to import/load
            context: Additional context information
        """
        message = f"Policy {operation} failed: {reason}"

        suggestions = [
            "Check that all policy-related modules are properly installed",
            "Verify policy configuration files are valid and accessible",
            "Ensure feedback data is in the correct format",
            "Check application logs for detailed error information"
        ]

        if module_name:
            suggestions.insert(0, f"Verify that module '{module_name}' is installed and importable")
            suggestions.insert(1, f"Check for circular imports involving '{module_name}'")

        # Add specific suggestions based on operation
        if "import" in reason.lower():
            suggestions.insert(0, "Module import failed - check Python path and installed packages")
        elif "validation" in reason.lower():
            suggestions.insert(0, "Policy validation failed - check policy configuration syntax")

        error_context = {
            "operation": operation,
            "reason": reason,
            "module_name": module_name
        }
        if context:
            error_context.update(context)

        super().__init__(
            message=message,
            suggestions=suggestions,
            context=error_context,
            error_code="POLICY_UPDATE_ERROR"
        )


class FeedbackValidationError(SecurityEngineError):
    """Error related to feedback data validation."""

    def __init__(
        self,
        validation_type: str,
        data_description: str,
        issues: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """Initialize FeedbackValidationError with validation-specific suggestions.

        Args:
            validation_type: Type of validation that failed
            data_description: Description of the data being validated
            issues: List of specific validation issues found
            context: Additional context information
        """
        message = f"Feedback {validation_type} validation failed for {data_description}"

        if issues:
            message += f": {', '.join(issues)}"

        suggestions = [
            f"Check the format and structure of {data_description}",
            "Ensure all required fields are present in feedback data",
            "Validate feedback data against expected schema",
            "Check for data corruption or transmission errors",
            "Review feedback collection process for data integrity"
        ]

        # Add specific suggestions based on validation type
        if validation_type == "JSON":
            suggestions.insert(0, "Invalid JSON format - check for syntax errors in feedback files")
            suggestions.insert(1, "Ensure feedback files are not corrupted during storage")
        elif validation_type == "schema":
            suggestions.insert(0, "Data schema validation failed - check field types and required fields")
        elif validation_type == "content":
            suggestions.insert(0, "Feedback content validation failed - check data values and ranges")

        error_context = {
            "validation_type": validation_type,
            "data_description": data_description,
            "issues": issues or []
        }
        if context:
            error_context.update(context)

        super().__init__(
            message=message,
            suggestions=suggestions,
            context=error_context,
            error_code="FEEDBACK_VALIDATION_ERROR"
        )


class ConfigurationError(SecurityEngineError):
    """Error related to configuration issues."""

    def __init__(
        self,
        config_type: str,
        issue: str,
        config_path: Optional[Path] = None,
        context: Optional[Dict[str, Any]] = None
    ):
        """Initialize ConfigurationError with config-specific suggestions.

        Args:
            config_type: Type of configuration that has issues
            issue: Description of the configuration issue
            config_path: Path to the configuration file if applicable
            context: Additional context information
        """
        message = f"Configuration error in {config_type}: {issue}"

        suggestions = [
            f"Check your {config_type} configuration settings",
            "Verify configuration file syntax and format",
            "Ensure all required configuration parameters are set",
            "Check environment variables if using external configuration"
        ]

        if config_path:
            suggestions.insert(0, f"Verify configuration file exists at: {config_path}")
            suggestions.insert(1, f"Check read permissions for: {config_path}")

        # Add specific suggestions based on config type
        if config_type == "memory":
            suggestions.extend([
                "Ensure memory backend is properly configured",
                "Check memory connection settings and credentials"
            ])
        elif config_type == "feedback":
            suggestions.extend([
                "Verify feedback storage paths are accessible",
                "Check feedback processing configuration"
            ])

        error_context = {
            "config_type": config_type,
            "issue": issue,
            "config_path": str(config_path) if config_path else None
        }
        if context:
            error_context.update(context)

        super().__init__(
            message=message,
            suggestions=suggestions,
            context=error_context,
            error_code="CONFIG_ERROR"
        )


# Utility functions for error handling
def handle_file_operation_error(
    operation: str,
    file_path: Path,
    original_error: Exception,
    context: Optional[Dict[str, Any]] = None
) -> FileOperationError:
    """Create and return a FileOperationError with appropriate context.

    Args:
        operation: The file operation that failed
        file_path: Path to the file that caused the error
        original_error: The original exception that was caught
        context: Additional context information

    Returns:
        FileOperationError instance with actionable suggestions
    """
    return FileOperationError(operation, file_path, original_error, context)


def handle_memory_operation_error(
    operation: str,
    memory_type: str = "adaptive_memory",
    missing_method: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> MemoryOperationError:
    """Create and return a MemoryOperationError with appropriate context.

    Args:
        operation: The memory operation that failed
        memory_type: Type of memory system
        missing_method: Name of the missing method if applicable
        context: Additional context information

    Returns:
        MemoryOperationError instance with actionable suggestions
    """
    return MemoryOperationError(operation, memory_type, missing_method, context)


def handle_policy_update_error(
    operation: str,
    reason: str,
    module_name: Optional[str] = None,
    context: Optional[Dict[str, Any]] = None
) -> PolicyUpdateError:
    """Create and return a PolicyUpdateError with appropriate context.

    Args:
        operation: The policy operation that failed
        reason: The reason for the failure
        module_name: Name of the module that failed to import/load
        context: Additional context information

    Returns:
        PolicyUpdateError instance with actionable suggestions
    """
    return PolicyUpdateError(operation, reason, module_name, context)


def handle_feedback_validation_error(
    validation_type: str,
    data_description: str,
    issues: Optional[List[str]] = None,
    context: Optional[Dict[str, Any]] = None
) -> FeedbackValidationError:
    """Create and return a FeedbackValidationError with appropriate context.

    Args:
        validation_type: Type of validation that failed
        data_description: Description of the data being validated
        issues: List of specific validation issues found
        context: Additional context information

    Returns:
        FeedbackValidationError instance with actionable suggestions
    """
    return FeedbackValidationError(validation_type, data_description, issues, context)


def handle_configuration_error(
    config_type: str,
    issue: str,
    config_path: Optional[Path] = None,
    context: Optional[Dict[str, Any]] = None
) -> ConfigurationError:
    """Create and return a ConfigurationError with appropriate context.

    Args:
        config_type: Type of configuration that has issues
        issue: Description of the configuration issue
        config_path: Path to the configuration file if applicable
        context: Additional context information

    Returns:
        ConfigurationError instance with actionable suggestions
    """
    return ConfigurationError(config_type, issue, config_path, context)