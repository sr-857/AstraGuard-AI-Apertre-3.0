"""
Evidence Collector for Digital Forensics

Collects and preserves digital evidence for security incidents
with chain of custody and integrity verification.
"""

import hashlib
import json
import os
import shutil
from typing import Dict, List, Any, Optional, BinaryIO
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import logging
from pathlib import Path
import uuid

from core.error_handling import safe_execute, AstraGuardException

logger = logging.getLogger(__name__)


class EvidenceType(Enum):
    """Types of digital evidence."""
    MEMORY_DUMP = "memory_dump"
    DISK_IMAGE = "disk_image"
    LOG_FILE = "log_file"
    NETWORK_CAPTURE = "network_capture"
    FILE_SYSTEM = "file_system"
    REGISTRY = "registry"
    PROCESS_DUMP = "process_dump"
    CONFIGURATION = "configuration"
    DATABASE_RECORD = "database_record"
    SCREENSHOT = "screenshot"


class EvidenceStatus(Enum):
    """Status of evidence collection."""
    PENDING = "pending"
    COLLECTING = "collecting"
    COLLECTED = "collected"
    VERIFIED = "verified"
    FAILED = "failed"
    CORRUPTED = "corrupted"


@dataclass
class EvidenceItem:
    """Digital evidence item."""
    evidence_id: str
    evidence_type: EvidenceType
    source_entity: str
    collection_time: datetime
    collector: str
    storage_path: str
    original_hash: str
    size_bytes: int
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: EvidenceStatus = EvidenceStatus.COLLECTED
    verification_hash: Optional[str] = None
    chain_of_custody: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "evidence_id": self.evidence_id,
            "evidence_type": self.evidence_type.value,
            "source_entity": self.source_entity,
            "collection_time": self.collection_time.isoformat(),
            "collector": self.collector,
            "storage_path": self.storage_path,
            "original_hash": self.original_hash,
            "size_bytes": self.size_bytes,
            "metadata": self.metadata,
            "status": self.status.value,
            "verification_hash": self.verification_hash,
            "chain_of_custody": self.chain_of_custody
        }
    
    def verify_integrity(self) -> bool:
        """Verify evidence integrity."""
        if not os.path.exists(self.storage_path):
            return False
        
        current_hash = self._calculate_file_hash(self.storage_path)
        return current_hash == self.original_hash
    
    @staticmethod
    def _calculate_file_hash(file_path: str) -> str:
        """Calculate SHA-256 hash of file."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def add_custody_entry(self, action: str, actor: str, timestamp: Optional[datetime] = None):
        """Add chain of custody entry."""
        entry = {
            "action": action,
            "actor": actor,
            "timestamp": (timestamp or datetime.now()).isoformat()
        }
        self.chain_of_custody.append(entry)


class EvidenceCollector:
    """
    Digital evidence collection system.
    
    Collects, preserves, and manages digital evidence with
    chain of custody and integrity verification.
    """
    
    def __init__(self, storage_dir: str = "evidence"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        
        # Evidence inventory
        self.evidence: Dict[str, EvidenceItem] = {}
        
        # Collection statistics
        self.collection_count = 0
        self.success_count = 0
        self.failed_count = 0
        
        # Create subdirectories for each evidence type
        for ev_type in EvidenceType:
            (self.storage_dir / ev_type.value).mkdir(exist_ok=True)
    
    def _generate_evidence_id(self, evidence_type: EvidenceType) -> str:
        """Generate unique evidence ID."""
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        unique_id = str(uuid.uuid4())[:8]
        return f"EVID-{evidence_type.value.upper()}-{timestamp}-{unique_id}"
    
    def _calculate_hash(self, data: bytes) -> str:
        """Calculate SHA-256 hash of data."""
        return hashlib.sha256(data).hexdigest()
    
    async def collect_file(self,
                        source_path: str,
                        evidence_type: EvidenceType,
                        source_entity: str,
                        metadata: Optional[Dict[str, Any]] = None) -> EvidenceItem:
        """
        Collect a file as evidence.
        
        Args:
            source_path: Path to source file
            evidence_type: Type of evidence
            source_entity: Entity being investigated
            metadata: Optional metadata
            
        Returns:
            EvidenceItem
        """
        evidence_id = self._generate_evidence_id(evidence_type)
        
        try:
            # Verify source exists
            if not os.path.exists(source_path):
                raise AstraGuardException(
                    f"Source file not found: {source_path}",
                    component="evidence_collector"
                )
            
            # Calculate original hash
            original_hash = EvidenceItem._calculate_file_hash(source_path)
            
            # Determine storage path
            file_name = os.path.basename(source_path)
            storage_path = self.storage_dir / evidence_type.value / f"{evidence_id}_{file_name}"
            
            # Copy file
            shutil.copy2(source_path, storage_path)
            
            # Get file size
            size_bytes = os.path.getsize(storage_path)
            
            # Create evidence item
            item = EvidenceItem(
                evidence_id=evidence_id,
                evidence_type=evidence_type,
                source_entity=source_entity,
                collection_time=datetime.now(),
                collector="evidence_collector",
                storage_path=str(storage_path),
                original_hash=original_hash,
                size_bytes=size_bytes,
                metadata=metadata or {},
                status=EvidenceStatus.COLLECTED
            )
            
            # Add custody entry
            item.add_custody_entry("collected", "evidence_collector")
            
            # Store
            self.evidence[evidence_id] = item
            self.collection_count += 1
            self.success_count += 1
            
            logger.info(f"Collected evidence: {evidence_id} from {source_path}")
            
            return item
            
        except Exception as e:
            self.failed_count += 1
            logger.error(f"Failed to collect evidence from {source_path}: {e}")
            raise
    
    async def collect_memory_dump(self,
                                 target_system: str,
                                 output_format: str = "raw") -> EvidenceItem:
        """
        Collect memory dump from target system.
        
        Args:
            target_system: Target system identifier
            output_format: Memory dump format
            
        Returns:
            EvidenceItem
        """
        evidence_id = self._generate_evidence_id(EvidenceType.MEMORY_DUMP)
        
        logger.info(f"Collecting memory dump from {target_system}")
        
        # In production: Implement actual memory dump collection
        # - Use OS-specific tools (dd, winpmem, etc.)
        # - Handle memory acquisition carefully
        
        # Placeholder implementation
        storage_path = self.storage_dir / EvidenceType.MEMORY_DUMP.value / f"{evidence_id}.mem"
        
        # Create placeholder file
        with open(storage_path, "wb") as f:
            f.write(b"MEMORY_DUMP_PLACEHOLDER")
        
        item = EvidenceItem(
            evidence_id=evidence_id,
            evidence_type=EvidenceType.MEMORY_DUMP,
            source_entity=target_system,
            collection_time=datetime.now(),
            collector="memory_collector",
            storage_path=str(storage_path),
            original_hash=self._calculate_hash(b"MEMORY_DUMP_PLACEHOLDER"),
            size_bytes=os.path.getsize(storage_path),
            metadata={"format": output_format, "target": target_system},
            status=EvidenceStatus.COLLECTED
        )
        
        item.add_custody_entry("collected", "memory_collector")
        
        self.evidence[evidence_id] = item
        self.collection_count += 1
        self.success_count += 1
        
        return item
    
    async def collect_logs(self,
                        log_paths: List[str],
                        source_entity: str,
                        time_range: Optional[tuple] = None) -> List[EvidenceItem]:
        """
        Collect log files as evidence.
        
        Args:
            log_paths: List of log file paths
            source_entity: Source entity identifier
            time_range: Optional (start, end) time range
            
        Returns:
            List of EvidenceItem objects
        """
        items = []
        
        for log_path in log_paths:
            try:
                item = await self.collect_file(
                    log_path,
                    EvidenceType.LOG_FILE,
                    source_entity,
                    metadata={"time_range": time_range}
                )
                items.append(item)
            except Exception as e:
                logger.warning(f"Failed to collect log {log_path}: {e}")
        
        return items
    
    async def collect_network_capture(self,
                                     interface: str,
                                     duration_seconds: int,
                                     filter_expr: Optional[str] = None,
                                     source_entity: str = "network") -> EvidenceItem:
        """
        Collect network packet capture.
        
        Args:
            interface: Network interface to capture
            duration_seconds: Capture duration
            filter_expr: Optional capture filter
            source_entity: Source entity identifier
            
        Returns:
            EvidenceItem
        """
        evidence_id = self._generate_evidence_id(EvidenceType.NETWORK_CAPTURE)
        
        logger.info(f"Starting network capture on {interface} for {duration_seconds}s")
        
        # In production: Implement actual packet capture
        # - Use libpcap/tshark/tcpdump
        # - Apply filters
        # - Handle large captures
        
        storage_path = self.storage_dir / EvidenceType.NETWORK_CAPTURE.value / f"{evidence_id}.pcap"
        
        # Placeholder
        with open(storage_path, "wb") as f:
            f.write(b"PCAP_PLACEHOLDER")
        
        item = EvidenceItem(
            evidence_id=evidence_id,
            evidence_type=EvidenceType.NETWORK_CAPTURE,
            source_entity=source_entity,
            collection_time=datetime.now(),
            collector="network_collector",
            storage_path=str(storage_path),
            original_hash=self._calculate_hash(b"PCAP_PLACEHOLDER"),
            size_bytes=os.path.getsize(storage_path),
            metadata={
                "interface": interface,
                "duration": duration_seconds,
                "filter": filter_expr
            },
            status=EvidenceStatus.COLLECTED
        )
        
        item.add_custody_entry("collected", "network_collector")
        
        self.evidence[evidence_id] = item
        self.collection_count += 1
        self.success_count += 1
        
        return item
    
    async def collect_process_dump(self,
                                  pid: int,
                                  source_entity: str) -> EvidenceItem:
        """
        Collect process memory dump.
        
        Args:
            pid: Process ID
            source_entity: Source entity identifier
            
        Returns:
            EvidenceItem
        """
        evidence_id = self._generate_evidence_id(EvidenceType.PROCESS_DUMP)
        
        logger.info(f"Collecting process dump for PID {pid}")
        
        # In production: Implement actual process dump
        # - Use gcore, procdump, etc.
        # - Handle process state carefully
        
        storage_path = self.storage_dir / EvidenceType.PROCESS_DUMP.value / f"{evidence_id}.dmp"
        
        # Placeholder
        with open(storage_path, "wb") as f:
            f.write(f"PROCESS_DUMP_PID_{pid}".encode())
        
        item = EvidenceItem(
            evidence_id=evidence_id,
            evidence_type=EvidenceType.PROCESS_DUMP,
            source_entity=source_entity,
            collection_time=datetime.now(),
            collector="process_collector",
            storage_path=str(storage_path),
            original_hash=self._calculate_hash(f"PROCESS_DUMP_PID_{pid}".encode()),
            size_bytes=os.path.getsize(storage_path),
            metadata={"pid": pid},
            status=EvidenceStatus.COLLECTED
        )
        
        item.add_custody_entry("collected", "process_collector")
        
        self.evidence[evidence_id] = item
        self.collection_count += 1
        self.success_count += 1
        
        return item
    
    def verify_evidence(self, evidence_id: str) -> bool:
        """
        Verify evidence integrity.
        
        Args:
            evidence_id: Evidence identifier
            
        Returns:
            True if integrity verified
        """
        item = self.evidence.get(evidence_id)
        if not item:
            return False
        
        is_valid = item.verify_integrity()
        
        if is_valid:
            item.status = EvidenceStatus.VERIFIED
            item.verification_hash = item.original_hash
            logger.info(f"Evidence integrity verified: {evidence_id}")
        else:
            item.status = EvidenceStatus.CORRUPTED
            logger.error(f"Evidence integrity failed: {evidence_id}")
        
        return is_valid
    
    def get_evidence(self, evidence_id: str) -> Optional[EvidenceItem]:
        """Get evidence item by ID."""
        return self.evidence.get(evidence_id)
    
    def get_evidence_by_type(self, evidence_type: EvidenceType) -> List[EvidenceItem]:
        """Get all evidence of a specific type."""
        return [
            item for item in self.evidence.values()
            if item.evidence_type == evidence_type
        ]
    
    def get_evidence_by_entity(self, source_entity: str) -> List[EvidenceItem]:
        """Get all evidence for a specific entity."""
        return [
            item for item in self.evidence.values()
            if item.source_entity == source_entity
        ]
    
    def transfer_custody(self, 
                        evidence_id: str, 
                        from_actor: str, 
                        to_actor: str,
                        reason: str) -> bool:
        """
        Transfer chain of custody.
        
        Args:
            evidence_id: Evidence identifier
            from_actor: Current custodian
            to_actor: New custodian
            reason: Transfer reason
            
        Returns:
            True if successful
        """
        item = self.evidence.get(evidence_id)
        if not item:
            return False
        
        item.add_custody_entry(f"transferred: {reason}", to_actor)
        logger.info(f"Custody transferred for {evidence_id}: {from_actor} -> {to_actor}")
        
        return True
    
    def export_evidence_report(self, evidence_ids: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Generate evidence report.
        
        Args:
            evidence_ids: Optional list of evidence IDs (all if None)
            
        Returns:
            Evidence report dictionary
        """
        if evidence_ids:
            items = [self.evidence.get(eid) for eid in evidence_ids if eid in self.evidence]
        else:
            items = list(self.evidence.values())
        
        # Filter out None values
        items = [item for item in items if item]
        
        by_type = {}
        total_size = 0
        integrity_status = {"verified": 0, "failed": 0, "unknown": 0}
        
        for item in items:
            etype = item.evidence_type.value
            by_type[etype] = by_type.get(etype, 0) + 1
            total_size += item.size_bytes
            
            if item.status == EvidenceStatus.VERIFIED:
                integrity_status["verified"] += 1
            elif item.status == EvidenceStatus.CORRUPTED:
                integrity_status["failed"] += 1
            else:
                integrity_status["unknown"] += 1
        
        return {
            "report_generated": datetime.now().isoformat(),
            "total_evidence_items": len(items),
            "by_type": by_type,
            "total_size_bytes": total_size,
            "integrity_status": integrity_status,
            "evidence_items": [item.to_dict() for item in items]
        }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get collector statistics."""
        by_type = {}
        by_status = {}
        
        for item in self.evidence.values():
            etype = item.evidence_type.value
            status = item.status.value
            
            by_type[etype] = by_type.get(etype, 0) + 1
            by_status[status] = by_status.get(status, 0) + 1
        
        return {
            "total_collected": self.collection_count,
            "successful": self.success_count,
            "failed": self.failed_count,
            "by_type": by_type,
            "by_status": by_status,
            "storage_directory": str(self.storage_dir)
        }


# Global instance
_evidence_collector: Optional[EvidenceCollector] = None


def get_evidence_collector() -> EvidenceCollector:
    """Get global evidence collector instance."""
    global _evidence_collector
    if _evidence_collector is None:
        _evidence_collector = EvidenceCollector()
    return _evidence_collector
