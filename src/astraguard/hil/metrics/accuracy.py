"""Ground-truth accuracy metrics for agent classification validation."""

import logging
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
from enum import Enum
import numpy as np
from collections import defaultdict
import bisect
import logging


logger = logging.getLogger(__name__)

logger = logging.getLogger(__name__)


class FaultState(str, Enum):
    """Fault states for ground truth."""
    NOMINAL = "nominal"
    FAULTY = "faulty"


@dataclass
class GroundTruthEvent:
    """Ground truth event during scenario."""

    timestamp_s: float
    satellite_id: str
    expected_fault_type: Optional[str]  # None = nominal
    confidence: float = 1.0  # Ground truth confidence (always 1.0 in scenarios)


@dataclass
class AgentClassification:
    """Agent classification attempt."""

    timestamp_s: float
    satellite_id: str
    predicted_fault: Optional[str]  # None = nominal prediction
    confidence: float
    is_correct: bool


class AccuracyCollector:
    """Validates agent classification accuracy against scenario ground truth."""

    def __init__(self):
        """Initialize accuracy collector."""
        self.ground_truth_events: List[GroundTruthEvent] = []
        self.agent_classifications: List[AgentClassification] = []
        # Precomputed sorted ground truth events per satellite for efficient lookups
        self._ground_truth_by_sat: Dict[str, List[GroundTruthEvent]] = defaultdict(list)

    def record_ground_truth(
        self,
        sat_id: str,
        scenario_time_s: float,
        fault_type: Optional[str],
        confidence: float = 1.0,
    ) -> None:
        """
        Record ground truth for satellite at time.

        Args:
            sat_id: Satellite identifier
            scenario_time_s: Simulation time
            fault_type: Expected fault type (None = nominal)
            confidence: Ground truth confidence (always 1.0)
            
        Raises:
            ValueError: If parameters are invalid
            TypeError: If parameters have wrong types
        """
        # INPUT VALIDATION
        if not sat_id or not isinstance(sat_id, str):
            raise ValueError(f"Invalid sat_id: must be non-empty string, got {sat_id!r}")
        
        if not isinstance(scenario_time_s, (int, float)):
            raise TypeError(f"scenario_time_s must be numeric, got {type(scenario_time_s).__name__}")
        
        if scenario_time_s < 0:
            raise ValueError(f"scenario_time_s must be non-negative, got {scenario_time_s}")
        
        if fault_type is not None and not isinstance(fault_type, str):
            raise TypeError(f"fault_type must be string or None, got {type(fault_type).__name__}")
        
        if not isinstance(confidence, (int, float)):
            raise TypeError(f"confidence must be numeric, got {type(confidence).__name__}")
        
        if not (0.0 <= confidence <= 1.0):
            raise ValueError(f"confidence must be between 0-1, got {confidence}")
        
        event = GroundTruthEvent(
            timestamp_s=scenario_time_s,
            satellite_id=sat_id,
            expected_fault_type=fault_type,
            confidence=confidence,
        )
        self.ground_truth_events.append(event)
        
        # Use bisect.insort for O(n) insertion into sorted list
        bisect.insort(
            self._ground_truth_by_sat[sat_id], 
            event, 
            key=lambda e: e.timestamp_s
        )


    def record_agent_classification(
        self,
        sat_id: str,
        scenario_time_s: float,
        predicted_fault: Optional[str],
        confidence: float,
        is_correct: bool,
    ) -> None:
        """
        Record agent classification attempt.

        Args:
            sat_id: Satellite identifier
            scenario_time_s: Simulation time
            predicted_fault: Predicted fault type (None = nominal)
            confidence: Agent's confidence in prediction
            is_correct: Whether prediction matches ground truth
            
        Raises:
            ValueError: If parameters are invalid
            TypeError: If parameters have wrong types
        """
        # INPUT VALIDATION
        if not sat_id or not isinstance(sat_id, str):
            raise ValueError(f"Invalid sat_id: must be non-empty string, got {sat_id!r}")
        
        if not isinstance(scenario_time_s, (int, float)):
            raise TypeError(f"scenario_time_s must be numeric, got {type(scenario_time_s).__name__}")
        
        if scenario_time_s < 0:
            raise ValueError(f"scenario_time_s must be non-negative, got {scenario_time_s}")
        
        if predicted_fault is not None and not isinstance(predicted_fault, str):
            raise TypeError(f"predicted_fault must be string or None, got {type(predicted_fault).__name__}")
        
        if not isinstance(confidence, (int, float)):
            raise TypeError(f"confidence must be numeric, got {type(confidence).__name__}")
        
        if not (0.0 <= confidence <= 1.0):
            raise ValueError(f"confidence must be between 0-1, got {confidence}")
        
        if not isinstance(is_correct, bool):
            raise TypeError(f"is_correct must be boolean, got {type(is_correct).__name__}")
        
        classification = AgentClassification(
            timestamp_s=scenario_time_s,
            satellite_id=sat_id,
            predicted_fault=predicted_fault,
            confidence=confidence,
            is_correct=is_correct,
        )
        self.agent_classifications.append(classification)


    def get_accuracy_stats(self) -> Dict[str, Any]:
        """
        Calculate comprehensive classification accuracy statistics.
        """
        if not self.agent_classifications:
            return {
                "total_classifications": 0,
                "correct_classifications": 0,
                "overall_accuracy": 0.0,
                "by_fault_type": {},
                "confidence_mean": 0.0,
                "confidence_std": 0.0,
            }

        try:
            total = len(self.agent_classifications)
            correct = sum(1 for c in self.agent_classifications if c.is_correct)

            # Per-fault-type breakdown
            by_fault = self._calculate_per_fault_stats()

        # Confidence statistics with error handling
        confidences = [c.confidence for c in self.agent_classifications]

        try:
            if confidences:
                confidence_mean = float(np.mean(confidences))
                confidence_std = float(np.std(confidences))
                
                # Check for invalid values
                if np.isnan(confidence_mean) or np.isinf(confidence_mean):
                    logger.warning(
                        "Invalid confidence mean calculated (NaN or Inf), defaulting to 0.0",
                        extra={"confidences_sample": confidences[:5]}
                    )
                    confidence_mean = 0.0
                
                if np.isnan(confidence_std) or np.isinf(confidence_std):
                    logger.warning(
                        "Invalid confidence std calculated (NaN or Inf), defaulting to 0.0",
                        extra={"confidences_sample": confidences[:5]}
                    )
                    confidence_std = 0.0
            else:
                confidence_mean = 0.0
                confidence_std = 0.0
                
        except (ValueError, TypeError) as e:
            logger.error(
                f"Failed to calculate confidence statistics: {e}",
                extra={
                    "confidences_count": len(confidences),
                    "operation": "accuracy_stats"
                }
            )
            confidence_mean = 0.0
            confidence_std = 0.0


            return {
                "total_classifications": total,
                "correct_classifications": correct,
                "overall_accuracy": correct / total if total > 0 else 0.0,
                "by_fault_type": by_fault,
                "confidence_mean": confidence_mean,
                "confidence_std": confidence_std,
            }
        except (TypeError, ValueError, ZeroDivisionError) as e:
            logger.exception("Error while computing accuracy statistics")
            raise

    def _calculate_per_fault_stats(self) -> Dict[str, Dict[str, Any]]:
        """
        Calculate precision, recall, F1 per fault type.
        """
        try:
            fault_types = set()
            for c in self.agent_classifications:
                if c.predicted_fault:
                    fault_types.add(c.predicted_fault)
            for e in self.ground_truth_events:
                if e.expected_fault_type:
                    fault_types.add(e.expected_fault_type)

            stats = {}

            for fault_type in sorted(fault_types):
                tp = sum(
                    1
                    for c in self.agent_classifications
                    if c.predicted_fault == fault_type and c.is_correct
                )

                fp = sum(
                    1
                    for c in self.agent_classifications
                    if c.predicted_fault == fault_type and not c.is_correct
                )

                fn = sum(
                    1
                    for c in self.agent_classifications
                    if c.predicted_fault != fault_type
                    and c.is_correct is False
                    and self._find_ground_truth_fault(
                        c.satellite_id, c.timestamp_s
                    )
                    == fault_type
                )

            predictions = [
                c for c in self.agent_classifications if c.predicted_fault == fault_type
            ]

            # Calculate average confidence with error handling
            try:
                avg_confidence = (
                    float(np.mean([c.confidence for c in predictions]))
                    if predictions
                    else 0.0
                )
                
                # Validate result
                if np.isnan(avg_confidence) or np.isinf(avg_confidence):
                    logger.warning(
                        f"Invalid average confidence for fault type '{fault_type}', using 0.0",
                        extra={
                            "fault_type": fault_type,
                            "predictions_count": len(predictions)
                        }
                    )
                    avg_confidence = 0.0
                    
            except (ValueError, TypeError) as e:
                logger.warning(
                    f"Failed to calculate average confidence for '{fault_type}': {e}",
                    extra={"fault_type": fault_type, "predictions_count": len(predictions)}
                )
                avg_confidence = 0.0

            stats[fault_type] = {
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "true_positives": tp,
                "false_positives": fp,
                "false_negatives": fn,
                "total_predictions": len(predictions),
                "correct_predictions": tp,
                "avg_confidence": avg_confidence,
            }


                predictions = [
                    c
                    for c in self.agent_classifications
                    if c.predicted_fault == fault_type
                ]

                stats[fault_type] = {
                    "precision": precision,
                    "recall": recall,
                    "f1": f1,
                    "true_positives": tp,
                    "false_positives": fp,
                    "false_negatives": fn,
                    "total_predictions": len(predictions),
                    "correct_predictions": tp,
                    "avg_confidence": (
                        float(np.mean([c.confidence for c in predictions]))
                        if predictions
                        else 0.0
                    ),
                }

            return stats
        except (TypeError, ValueError, ZeroDivisionError) as e:
            logger.exception("Error while calculating per-fault statistics")
            raise

    def _find_ground_truth_fault(self, sat_id: str, timestamp_s: float) -> Optional[str]:
        """
        Find ground truth fault type for satellite at given time.
        
        Uses binary search for efficient lookup in sorted ground truth events.
        
        Args:
            sat_id: Satellite identifier
            timestamp_s: Simulation time
            
        Returns:
            Expected fault type at that time, or None if nominal
        """
        if sat_id not in self._ground_truth_by_sat:
            logger.warning(
                f"No ground truth data for satellite '{sat_id}'",
                extra={
                    "satellite_id": sat_id,
                    "timestamp_s": timestamp_s,
                    "available_satellites": list(self._ground_truth_by_sat.keys())
                }
            )
            return None
        
        events = self._ground_truth_by_sat[sat_id]
        
        if not events:
            return None
        
        # Binary search for closest event at or before timestamp
        idx = bisect.bisect_right(events, timestamp_s, key=lambda e: e.timestamp_s)
        
        if idx == 0:
            # Timestamp is before first event
            return None
        
        # Get closest event before or at timestamp
        closest_event = events[idx - 1]
        
        return closest_event.expected_fault_type

    def get_stats_by_satellite(self) -> Dict[str, Dict[str, Any]]:
        """
        Calculate accuracy statistics per satellite.
        """
        try:
            by_satellite = defaultdict(list)

            # Calculate average confidence with error handling
            try:
                avg_confidence = (
                    float(np.mean([c.confidence for c in classifications]))
                    if classifications
                    else 0.0
                )
                
                if np.isnan(avg_confidence) or np.isinf(avg_confidence):
                    logger.warning(
                        f"Invalid average confidence for satellite '{sat_id}', using 0.0",
                        extra={
                            "satellite_id": sat_id,
                            "classifications_count": len(classifications)
                        }
                    )
                    avg_confidence = 0.0
                    
            except (ValueError, TypeError) as e:
                logger.warning(
                    f"Failed to calculate average confidence for satellite '{sat_id}': {e}",
                    extra={"satellite_id": sat_id, "classifications_count": len(classifications)}
                )
                avg_confidence = 0.0

            stats[sat_id] = {
                "total_classifications": total,
                "correct_classifications": correct,
                "accuracy": correct / total if total > 0 else 0.0,
                "avg_confidence": avg_confidence,
            }

        return stats


    def get_confusion_matrix(self) -> Dict[str, Dict[str, int]]:
        """
        Build confusion matrix of predicted vs actual fault types.
        """
        confusion = defaultdict(lambda: defaultdict(int))

        try:
            for c in self.agent_classifications:
                actual_fault = self._find_ground_truth_fault(
                    c.satellite_id, c.timestamp_s
                )

                predicted = c.predicted_fault or "nominal"
                actual = actual_fault or "nominal"

                confusion[predicted][actual] += 1

            return dict(confusion)
        except (TypeError, ValueError) as e:
            logger.exception("Failed while building confusion matrix")
            raise

    def export_csv(self, filename: str) -> None:
        """
        Export classifications to CSV for analysis.

        Args:
            filename: Path to output CSV file
            
        Raises:
            ValueError: If filename is invalid
            OSError: If file cannot be created or written
        """
        import csv
        from pathlib import Path
        
        # INPUT VALIDATION
        if not filename or not isinstance(filename, str):
            raise ValueError(f"Invalid filename: must be non-empty string, got {filename!r}")
        
        if not filename.endswith('.csv'):
            logger.warning(f"Filename '{filename}' does not have .csv extension")
        
        try:
            filepath = Path(filename)
            
            # Create parent directories
            try:
                filepath.parent.mkdir(parents=True, exist_ok=True)
            except PermissionError as e:
                logger.error(
                    f"Permission denied creating directory: {e}",
                    extra={
                        "directory": str(filepath.parent),
                        "operation": "csv_export",
                        "filename": filename
                    }
                )
                raise
            except OSError as e:
                logger.error(
                    f"Failed to create directory: {e}",
                    extra={
                        "directory": str(filepath.parent),
                        "operation": "csv_export",
                        "error_type": type(e).__name__
                    }
                )
                raise
            
            # Write CSV file
            try:
                with open(filepath, "w", newline="", encoding='utf-8') as f:
                    fieldnames = [
                        "timestamp_s",
                        "satellite_id",
                        "predicted_fault",
                        "confidence",
                        "is_correct",
                    ]
                    writer = csv.DictWriter(f, fieldnames=fieldnames)
                    writer.writeheader()

                    for c in self.agent_classifications:
                        writer.writerow({

                            "timestamp_s": c.timestamp_s,
                            "satellite_id": c.satellite_id,
                            "predicted_fault": c.predicted_fault or "nominal",
                            "confidence": c.confidence,
                            "is_correct": c.is_correct,
                        })
                
                logger.info(
                    f"Exported {len(self.agent_classifications)} classifications to CSV",
                    extra={
                        "filepath": str(filepath),
                        "classification_count": len(self.agent_classifications),
                        "operation": "csv_export"
                    }
                )
                
            except PermissionError as e:
                logger.error(
                    f"Permission denied writing CSV file: {e}",
                    extra={
                        "filepath": str(filepath),
                        "operation": "csv_export"
                    }
                )
                raise
            except OSError as e:
                if e.errno == 28:  # ENOSPC - No space left on device
                    logger.error(
                        "Cannot write CSV file: disk full",
                        extra={
                            "filepath": str(filepath),
                            "error_code": e.errno,
                            "operation": "csv_export"
                        }
                    )
                else:
                    logger.error(
                        f"Failed to write CSV file: {e}",
                        extra={
                            "filepath": str(filepath),
                            "operation": "csv_export",
                            "error_type": type(e).__name__
                        }
                    )
                raise
                
        except Exception as e:
            # Catch any unexpected errors during CSV export
            logger.error(
                f"Unexpected error during CSV export: {e}",
                extra={
                    "filename": filename,
                    "operation": "csv_export",
                    "error_type": type(e).__name__
                },
                exc_info=True
            )
            raise

    def get_summary(self) -> Dict[str, Any]:
        """
        Get comprehensive accuracy summary.
        """
        try:
            return {
                "total_events": len(self.ground_truth_events),
                "total_classifications": len(self.agent_classifications),
                "stats": self.get_accuracy_stats(),
                "stats_by_satellite": self.get_stats_by_satellite(),
                "confusion_matrix": self.get_confusion_matrix(),
            }
        except (TypeError, ValueError) as e:
            logger.exception("Failed to generate summary")
            raise

    def _find_ground_truth_fault(
        self, sat_id: str, timestamp_s: float
    ) -> Optional[str]:
        """
        Find the ground truth fault type for a satellite at a given timestamp.
        """
        if sat_id not in self._ground_truth_by_sat:
            return None

        events = self._ground_truth_by_sat[sat_id]
        if not events:
            return None

        try:
            idx = bisect.bisect_right(
                events, timestamp_s, key=lambda e: e.timestamp_s
            ) - 1

            if idx < 0:
                return None

            return events[idx].expected_fault_type
        except (TypeError, ValueError) as e:
            logger.exception(
                "Binary search failed while finding ground truth fault"
            )
            raise

    def reset(self) -> None:
        """Clear all data."""
        self.ground_truth_events.clear()
        self.agent_classifications.clear()
        self._ground_truth_by_sat.clear()

    def __len__(self) -> int:
        """Return number of classifications."""
        return len(self.agent_classifications)
