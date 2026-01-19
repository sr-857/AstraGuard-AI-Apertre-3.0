"""
SwarmSerializer - Data serialization for bandwidth-constrained operations.

Implements LZ4 compression + orjson fast serialization for <1KB HealthSummary
payloads on ISL links with 10KB/s bandwidth limit.

Issue #399 integration: Compression metrics and LZ4 optimization.
"""

import json
from typing import Any, Dict, Union
from datetime import datetime

try:
    import lz4.frame
    HAS_LZ4 = True
except ImportError:
    HAS_LZ4 = False

try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    HAS_ORJSON = False

import jsonschema
from astraguard.swarm.models import HealthSummary, SwarmConfig, AgentID


class SwarmSerializer:
    """
    High-performance serializer for swarm data with LZ4 compression.
    
    Features:
    - LZ4 frame compression for 80%+ ratio on typical HealthSummary
    - orjson for faster JSON encoding/decoding (optional, fallback to json)
    - JSONSchema v1.0 validation
    - <50ms roundtrip serialization
    - <1KB compressed HealthSummary payloads
    """

    # JSONSchema for validation
    SCHEMA = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "definitions": {
            "HealthSummary": {
                "type": "object",
                "properties": {
                    "anomaly_signature": {
                        "type": "array",
                        "items": {"type": "number"},
                        "minItems": 32,
                        "maxItems": 32,
                        "description": "32-dimensional PCA vector",
                    },
                    "risk_score": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 1.0,
                        "description": "Normalized risk metric",
                    },
                    "recurrence_score": {
                        "type": "number",
                        "minimum": 0,
                        "maximum": 10,
                        "description": "Weighted decay score",
                    },
                    "timestamp": {
                        "type": "string",
                        "format": "date-time",
                        "description": "ISO 8601 timestamp",
                    },
                    "compressed_size": {
                        "type": "integer",
                        "minimum": 0,
                        "maximum": 1024,
                        "description": "LZ4 compressed size in bytes",
                    },
                },
                "required": [
                    "anomaly_signature",
                    "risk_score",
                    "recurrence_score",
                    "timestamp",
                ],
                "additionalProperties": False,
            },
            "AgentID": {
                "type": "object",
                "properties": {
                    "constellation": {
                        "type": "string",
                        "description": "Constellation identifier",
                    },
                    "satellite_serial": {
                        "type": "string",
                        "description": "Satellite serial number",
                    },
                    "uuid": {
                        "type": "string",
                        "format": "uuid",
                        "description": "UUIDv5 derived identifier",
                    },
                },
                "required": ["constellation", "satellite_serial", "uuid"],
                "additionalProperties": False,
            },
            "SwarmConfig": {
                "type": "object",
                "properties": {
                    "agent_id": {"$ref": "#/definitions/AgentID"},
                    "role": {
                        "type": "string",
                        "enum": ["primary", "backup", "standby", "safe_mode"],
                        "description": "Satellite operational role",
                    },
                    "constellation_id": {
                        "type": "string",
                        "description": "Constellation identifier",
                    },
                    "peers": {
                        "type": "array",
                        "items": {"$ref": "#/definitions/AgentID"},
                        "description": "Peer agent IDs for ISL communication",
                    },
                    "bandwidth_limit_kbps": {
                        "type": "integer",
                        "minimum": 1,
                        "description": "ISL bandwidth limit in KB/s",
                    },
                },
                "required": ["agent_id", "role", "constellation_id"],
                "additionalProperties": False,
            },
        },
    }

    def __init__(self, validate: bool = True):
        """
        Initialize serializer.
        
        Args:
            validate: Enable JSONSchema validation on serialize/deserialize
        """
        self.validate = validate
        self._use_orjson = HAS_ORJSON
        self._use_lz4 = HAS_LZ4

    def serialize_health(
        self, summary: HealthSummary, compress: bool = True
    ) -> bytes:
        """
        Serialize HealthSummary to bytes with optional LZ4 compression.
        
        Args:
            summary: HealthSummary instance
            compress: Enable LZ4 compression (default True)
            
        Returns:
            Serialized bytes (compressed if enabled)
            
        Raises:
            ValueError: If validation fails or compression unavailable
        """
        data = summary.to_dict()

        if self.validate:
            self.validate_schema(data, "HealthSummary")

        # Encode to JSON
        if self._use_orjson:
            json_bytes = orjson.dumps(data, default=str)
        else:
            json_str = json.dumps(data, default=str)
            json_bytes = json_str.encode("utf-8")

        # Compress if enabled
        if compress:
            if not self._use_lz4:
                raise ValueError(
                    "LZ4 compression requested but lz4 package not installed"
                )
            compressed = lz4.frame.compress(json_bytes)
            return compressed
        else:
            return json_bytes

    def deserialize_health(self, data: bytes, compressed: bool = True) -> HealthSummary:
        """
        Deserialize bytes to HealthSummary with optional LZ4 decompression.
        
        Args:
            data: Serialized bytes
            compressed: Whether data is LZ4 compressed (default True)
            
        Returns:
            HealthSummary instance
            
        Raises:
            ValueError: If validation or decompression fails
        """
        # Decompress if needed
        if compressed:
            if not self._use_lz4:
                raise ValueError(
                    "LZ4 decompression requested but lz4 package not installed"
                )
            json_bytes = lz4.frame.decompress(data)
        else:
            json_bytes = data

        # Decode from JSON
        if self._use_orjson:
            json_data = orjson.loads(json_bytes)
        else:
            json_str = json_bytes.decode("utf-8")
            json_data = json.loads(json_str)

        if self.validate:
            self.validate_schema(json_data, "HealthSummary")

        return HealthSummary.from_dict(json_data)

    def serialize_swarm_config(self, config: SwarmConfig) -> bytes:
        """
        Serialize SwarmConfig to JSON bytes.
        
        Args:
            config: SwarmConfig instance
            
        Returns:
            Serialized JSON bytes
        """
        data = config.to_dict()

        if self.validate:
            self.validate_schema(data, "SwarmConfig")

        if self._use_orjson:
            return orjson.dumps(data, default=str)
        else:
            json_str = json.dumps(data, default=str)
            return json_str.encode("utf-8")

    def deserialize_swarm_config(self, data: bytes) -> SwarmConfig:
        """
        Deserialize JSON bytes to SwarmConfig.
        
        Args:
            data: Serialized JSON bytes
            
        Returns:
            SwarmConfig instance
        """
        if self._use_orjson:
            json_data = orjson.loads(data)
        else:
            json_str = data.decode("utf-8")
            json_data = json.loads(json_str)

        if self.validate:
            self.validate_schema(json_data, "SwarmConfig")

        return SwarmConfig.from_dict(json_data)

    def validate_schema(self, data: dict, schema_type: str) -> bool:
        """
        Validate data against JSONSchema.
        
        Args:
            data: Dictionary to validate
            schema_type: Type name from SCHEMA definitions
            
        Returns:
            True if validation passes
            
        Raises:
            jsonschema.ValidationError: If validation fails
        """
        if not self.validate:
            return True

        validator = jsonschema.Draft7Validator(self.SCHEMA)
        schema_def = self.SCHEMA["definitions"].get(schema_type)

        if not schema_def:
            raise ValueError(f"Unknown schema type: {schema_type}")

        validator.validate(data, schema_def)
        return True

    @staticmethod
    def get_compression_stats(original_size: int, compressed_size: int) -> Dict[str, Any]:
        """
        Calculate compression statistics.
        
        Args:
            original_size: Size before compression (bytes)
            compressed_size: Size after compression (bytes)
            
        Returns:
            Dictionary with compression metrics
        """
        if original_size == 0:
            return {
                "original_size": 0,
                "compressed_size": 0,
                "compression_ratio": 0.0,
                "saved_bytes": 0,
            }

        ratio = (1.0 - compressed_size / original_size) * 100
        return {
            "original_size": original_size,
            "compressed_size": compressed_size,
            "compression_ratio": f"{ratio:.1f}%",
            "saved_bytes": original_size - compressed_size,
        }
