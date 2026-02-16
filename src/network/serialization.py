"""
Serialization Layer using MsgPack
Optimized for speed and compact payload size.
"""

import msgpack
import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

def _default_serializer(obj: Any) -> Any:
    """Handle types not supported by msgpack natively."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "model_dump"): # Pydantic v2
        return obj.model_dump(mode='json')
    if hasattr(obj, "dict"): # Pydantic v1
        return obj.dict()
    return str(obj)

def serialize_payload(data: Any) -> bytes:
    """
    Serialize data to MsgPack bytes.

    Args:
        data: Python object (dict, list, primitive)

    Returns:
        MsgPack bytes
    """
    try:
        return msgpack.packb(data, default=_default_serializer, use_bin_type=True)
    except Exception as e:
        logger.error(f"Serialization failed: {e}")
        raise

def deserialize_payload(data: bytes) -> Any:
    """
    Deserialize MsgPack bytes to Python object.

    Args:
        data: MsgPack bytes

    Returns:
        Python object (dict, list, etc.)
    """
    try:
        return msgpack.unpackb(data, raw=False, strict_map_key=False)
    except Exception as e:
        logger.error(f"Deserialization failed: {e}")
        raise
