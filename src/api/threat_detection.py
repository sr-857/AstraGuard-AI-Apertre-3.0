"""
Threat Detection API Endpoints

REST API endpoints for threat detection operations including
detection submission, results retrieval, and management.
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Depends
from pydantic import BaseModel, Field
import logging

from threat_detection.detection_engine import (
    get_detection_engine, DetectionContext, DetectionMode
)
from threat_detection.advanced_anomaly_detector import (
    ThreatSeverity, ThreatCategory
)
from threat_detection.threat_hunter import (
    get_threat_hunter, HuntType, HuntStatus
)
from threat_detection.ioc_hunter import get_ioc_hunter
from threat_detection.ioc_manager import IoCType, IoCSeverity
from threat_detection.forensics_logger import get_forensics_logger
from threat_detection.timeline_reconstructor import get_timeline_reconstructor
from core.auth import require_auth, require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/threat-detection", tags=["threat-detection"])


# Pydantic Models
class DetectionRequest(BaseModel):
    """Request model for threat detection."""
    data: Dict[str, Any] = Field(..., description="Data to analyze")
    source: str = Field("api", description="Source of the data")
    entity_id: Optional[str] = Field(None, description="Entity identifier")
    entity_type: Optional[str] = Field(None, description="Entity type")
    priority: int = Field(5, ge=1, le=10, description="Priority (1-10, lower is higher)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class DetectionResponse(BaseModel):
    """Response model for detection submission."""
    submission_id: str
    status: str
    message: str


class DetectionResultResponse(BaseModel):
    """Response model for detection results."""
    detection_id: str
    timestamp: str
    detections: List[Dict[str, Any]]
    behavioral_analysis: Optional[Dict[str, Any]]
    ioc_matches: List[Dict[str, Any]]
    response_triggered: bool
    response_actions: List[str]
    forensics_event_id: Optional[str]
    processing_time_ms: float


class HuntRequest(BaseModel):
    """Request model for threat hunt."""
    name: str = Field(..., description="Hunt name")
    description: str = Field(..., description="Hunt description")
    hunt_type: str = Field(..., description="Type of hunt")
    query_params: Dict[str, Any] = Field(default_factory=dict, description="Query parameters")
    scope: Optional[Dict[str, Any]] = Field(None, description="Hunt scope")


class HuntResponse(BaseModel):
    """Response model for hunt creation."""
    hunt_id: str
    status: str
    message: str


class IoCSubmitRequest(BaseModel):
    """Request model for IoC submission."""
    ioc_type: str = Field(..., description="Type of IoC")
    value: str = Field(..., description="IoC value")
    severity: str = Field("medium", description="Severity level")
    description: Optional[str] = Field(None, description="Description")
    source: Optional[str] = Field(None, description="Source of IoC")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class TimelineCreateRequest(BaseModel):
    """Request model for timeline creation."""
    incident_id: str = Field(..., description="Incident identifier")
    title: str = Field(..., description="Timeline title")
    description: str = Field(..., description="Timeline description")
    entity_id: Optional[str] = Field(None, description="Entity to trace")
    time_range_hours: int = Field(24, description="Time range in hours")


@router.post("/detect", response_model=DetectionResponse)
async def submit_detection(
    request: DetectionRequest,
    background_tasks: BackgroundTasks,
    user: Dict[str, Any] = Depends(require_auth)
):
    """
    Submit data for threat detection.
    
    Analyzes submitted data for threats using all available
    detection methods including anomaly detection, behavioral
    analysis, and IoC matching.
    """
    try:
        engine = await get_detection_engine()
        
        # Create detection context
        context = DetectionContext(
            source=request.source,
            timestamp=datetime.now(),
            entity_id=request.entity_id,
            entity_type=request.entity_type,
            priority=request.priority,
            metadata=request.metadata or {}
        )
        
        # Submit for detection
        submission_id = await engine.submit_for_detection(
            data=request.data,
            context=context
        )
        
        return DetectionResponse(
            submission_id=submission_id,
            status="submitted",
            message="Data submitted for threat detection"
        )
        
    except Exception as e:
        logger.error(f"Detection submission failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/detections/{detection_id}", response_model=DetectionResultResponse)
async def get_detection_result(
    detection_id: str,
    user: Dict[str, Any] = Depends(require_auth)
):
    """
    Get detection result by ID.
    
    Retrieves the complete results of a detection operation
    including all findings and triggered responses.
    """
    try:
        engine = await get_detection_engine()
        result = engine.get_detection(detection_id)
        
        if not result:
            raise HTTPException(status_code=404, detail="Detection not found")
        
        return DetectionResultResponse(
            detection_id=result.detection_id,
            timestamp=result.timestamp.isoformat(),
            detections=[d.to_dict() for d in result.detections],
            behavioral_analysis=result.behavioral_analysis.to_dict() if result.behavioral_analysis else None,
            ioc_matches=result.ioc_matches,
            response_triggered=result.response_triggered,
            response_actions=result.response_actions,
            forensics_event_id=result.forensics_event_id,
            processing_time_ms=result.processing_time_ms
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get detection result: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/detections")
async def list_detections(
    severity: Optional[str] = None,
    category: Optional[str] = None,
    limit: int = Query(100, ge=1, le=1000),
    user: Dict[str, Any] = Depends(require_auth)
):
    """
    List recent detections.
    
    Returns recent threat detections with optional filtering
    by severity and category.
    """
    try:
        engine = await get_detection_engine()
        
        # Convert string parameters to enums
        severity_enum = None
        if severity:
            severity_enum = ThreatSeverity(severity)
        
        category_enum = None
        if category:
            category_enum = ThreatCategory(category)
        
        results = engine.get_recent_detections(
            severity=severity_enum,
            category=category_enum,
            limit=limit
        )
        
        return {
            "count": len(results),
            "detections": [r.to_dict() for r in results]
        }
        
    except Exception as e:
        logger.error(f"Failed to list detections: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hunts", response_model=HuntResponse)
async def create_hunt(
    request: HuntRequest,
    user: Dict[str, Any] = Depends(require_auth)
):
    """
    Create a new threat hunt.
    
    Initiates a proactive threat hunt based on the specified
    parameters and hunt type.
    """
    try:
        hunter = get_threat_hunter()
        
        # Convert hunt type string to enum
        hunt_type = HuntType(request.hunt_type)
        
        # Create hunt
        hunt = await hunter.create_hunt(
            name=request.name,
            description=request.description,
            hunt_type=hunt_type,
            query_params=request.query_params,
            scope=request.scope or {},
            created_by=user.get("username", "unknown")
        )
        
        return HuntResponse(
            hunt_id=hunt.hunt_id,
            status="created",
            message=f"Hunt '{request.name}' created successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to create hunt: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hunts/{hunt_id}/execute")
async def execute_hunt(
    hunt_id: str,
    user: Dict[str, Any] = Depends(require_auth)
):
    """
    Execute a threat hunt.
    
    Runs the specified hunt and returns the results.
    """
    try:
        hunter = get_threat_hunter()
        hunt = await hunter.execute_hunt(hunt_id)
        
        return {
            "hunt_id": hunt.hunt_id,
            "status": hunt.status.value,
            "result_count": len(hunt.results),
            "results": [r.to_dict() for r in hunt.results]
        }
        
    except Exception as e:
        logger.error(f"Failed to execute hunt: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hunts")
async def list_hunts(
    status: Optional[str] = None,
    hunt_type: Optional[str] = None,
    user: Dict[str, Any] = Depends(require_auth)
):
    """
    List threat hunts.
    
    Returns all threat hunts with optional filtering by status
    and hunt type.
    """
    try:
        hunter = get_threat_hunter()
        
        # Convert filters
        status_enum = None
        if status:
            status_enum = HuntStatus(status)
        
        type_enum = None
        if hunt_type:
            type_enum = HuntType(hunt_type)
        
        hunts = hunter.list_hunts(status=status_enum, hunt_type=type_enum)
        
        return {
            "count": len(hunts),
            "hunts": [h.to_dict() for h in hunts]
        }
        
    except Exception as e:
        logger.error(f"Failed to list hunts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/hunt-templates")
async def get_hunt_templates(
    user: Dict[str, Any] = Depends(require_auth)
):
    """
    Get available hunt templates.
    
    Returns pre-built hunt templates for common threat
    hunting scenarios.
    """
    try:
        hunter = get_threat_hunter()
        templates = hunter.get_hunt_templates()
        
        return {
            "templates": templates
        }
        
    except Exception as e:
        logger.error(f"Failed to get hunt templates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/iocs")
async def submit_ioc(
    request: IoCSubmitRequest,
    user: Dict[str, Any] = Depends(require_permission("ioc:manage"))
):
    """
    Submit a new IoC.
    
    Adds a new Indicator of Compromise to the system for
    detection and hunting.
    """
    try:
        ioc_manager = get_ioc_manager()
        
        # Convert enums
        ioc_type = IoCType(request.ioc_type)
        severity = IoCSeverity(request.severity)
        
        # Add IoC
        ioc = ioc_manager.add_ioc(
            ioc_type=ioc_type,
            value=request.value,
            severity=severity,
            description=request.description,
            source=request.source or user.get("username", "api"),
            metadata=request.metadata or {}
        )
        
        return {
            "ioc_id": ioc.ioc_id,
            "status": "added",
            "message": f"IoC {request.value} added successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to submit IoC: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/iocs")
async def list_iocs(
    ioc_type: Optional[str] = None,
    active_only: bool = True,
    user: Dict[str, Any] = Depends(require_auth)
):
    """
    List IoCs.
    
    Returns all IoCs with optional filtering by type and
    active status.
    """
    try:
        ioc_manager = get_ioc_manager()
        
        if active_only:
            iocs = ioc_manager.get_all_active_iocs()
        else:
            iocs = list(ioc_manager.iocs.values())
        
        if ioc_type:
            type_enum = IoCType(ioc_type)
            iocs = [ioc for ioc in iocs if ioc.ioc_type == type_enum]
        
        return {
            "count": len(iocs),
            "iocs": [ioc.to_dict() for ioc in iocs]
        }
        
    except Exception as e:
        logger.error(f"Failed to list IoCs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/iocs/{ioc_id}/hunt")
async def hunt_ioc(
    ioc_id: str,
    user: Dict[str, Any] = Depends(require_auth)
):
    """
    Hunt for a specific IoC.
    
    Searches across all data sources for occurrences of
    the specified IoC.
    """
    try:
        ioc_hunter = get_ioc_hunter()
        result = await ioc_hunter.hunt_ioc(ioc_id)
        
        return result.to_dict()
        
    except Exception as e:
        logger.error(f"Failed to hunt IoC: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/timelines")
async def create_timeline(
    request: TimelineCreateRequest,
    user: Dict[str, Any] = Depends(require_auth)
):
    """
    Create an incident timeline.
    
    Reconstructs a chronological timeline of events for
    the specified incident or entity.
    """
    try:
        reconstructor = get_timeline_reconstructor()
        
        # Calculate time range
        from datetime import timedelta
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=request.time_range_hours)
        
        if request.entity_id:
            # Entity-based reconstruction
            timeline = await reconstructor.reconstruct_from_entity(
                incident_id=request.incident_id,
                entity_id=request.entity_id,
                time_range=(start_time, end_time)
            )
        else:
            # Create empty timeline
            timeline = reconstructor.create_timeline(
                incident_id=request.incident_id,
                title=request.title,
                description=request.description
            )
        
        return {
            "incident_id": timeline.incident_id,
            "entry_count": len(timeline.entries),
            "duration_seconds": timeline.get_duration(),
            "timeline": timeline.to_dict()
        }
        
    except Exception as e:
        logger.error(f"Failed to create timeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/timelines/{incident_id}")
async def get_timeline(
    incident_id: str,
    format: str = "json",
    user: Dict[str, Any] = Depends(require_auth)
):
    """
    Get incident timeline.
    
    Retrieves the complete timeline for an incident in
    the requested format (json, html, markdown).
    """
    try:
        reconstructor = get_timeline_reconstructor()
        
        if format == "narrative":
            # Return narrative text
            narrative = reconstructor.generate_narrative(incident_id)
            return {
                "incident_id": incident_id,
                "format": "narrative",
                "content": narrative
            }
        else:
            # Return structured data
            timeline = reconstructor.export_timeline(incident_id, format=format)
            return {
                "incident_id": incident_id,
                "format": format,
                "content": timeline
            }
        
    except Exception as e:
        logger.error(f"Failed to get timeline: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/statistics")
async def get_statistics(
    user: Dict[str, Any] = Depends(require_auth)
):
    """
    Get threat detection statistics.
    
    Returns comprehensive statistics about detection
    operations, hunts, and IoCs.
    """
    try:
        engine = await get_detection_engine()
        hunter = get_threat_hunter()
        ioc_manager = get_ioc_manager()
        forensics = get_forensics_logger()
        
        return {
            "detection_engine": engine.get_statistics(),
            "threat_hunter": hunter.get_statistics(),
            "ioc_manager": ioc_manager.get_statistics(),
            "forensics": forensics.get_statistics()
        }
        
    except Exception as e:
        logger.error(f"Failed to get statistics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Returns the health status of the threat detection system.
    """
    try:
        engine = await get_detection_engine()
        stats = engine.get_statistics()
        
        return {
            "status": "healthy" if stats["status"] == "running" else "degraded",
            "mode": stats["mode"],
            "queue_size": stats["queue_size"],
            "active_workers": stats["active_workers"]
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }
