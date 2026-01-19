"""
Memory Replay Engine

Replay past incidents for analysis and debugging.
"""

from datetime import datetime
from typing import List, Dict


class ReplayEngine:
    """
    Replay events from memory like a security flight recorder.

    Features:
    - Time-range queries
    - Event filtering
    - Chronological playback
    - Incident reconstruction
    """

    def __init__(self, memory_store):
        """
        Initialize replay engine.

        Args:
            memory_store: AdaptiveMemoryStore instance
        """
        self.memory = memory_store

    def replay_time_range(self, start_time: datetime, end_time: datetime) -> List[Dict]:
        """
        Replay events within time range.

        Args:
            start_time: Start of replay window
            end_time: End of replay window

        Returns:
            List of events in chronological order
        """
        return self.memory.replay(start_time, end_time)

    def replay_incident(self, incident_id: str) -> Dict:
        """
        Replay a specific incident by ID.

        Args:
            incident_id: Unique incident identifier

        Returns:
            Incident details with timeline
        """
        events = [
            event
            for event in self.memory.memory
            if event.metadata.get("incident_id") == incident_id
        ]

        if not events:
            return {"error": "Incident not found"}

        # Sort chronologically
        events.sort(key=lambda x: x.timestamp)

        return {
            "incident_id": incident_id,
            "start_time": events[0].timestamp,
            "end_time": events[-1].timestamp,
            "event_count": len(events),
            "timeline": [
                {
                    "timestamp": e.timestamp,
                    "metadata": e.metadata,
                    "recurrence_count": e.recurrence_count,
                }
                for e in events
            ],
        }

    def find_similar_incidents(self, incident_id: str, top_k: int = 5) -> List[Dict]:
        """
        Find similar past incidents.

        Args:
            incident_id: Reference incident ID
            top_k: Number of similar incidents to return

        Returns:
            List of similar incidents
        """
        # Get reference incident
        ref_events = [
            e
            for e in self.memory.memory
            if e.metadata.get("incident_id") == incident_id
        ]

        if not ref_events:
            return []

        # Use first event as reference
        ref_embedding = ref_events[0].embedding

        # Retrieve similar events
        similar = self.memory.retrieve(ref_embedding, top_k=top_k * 2)

        # Group by incident_id
        incidents = {}
        for score, metadata, timestamp in similar:
            iid = metadata.get("incident_id")
            if iid and iid != incident_id:
                if iid not in incidents:
                    incidents[iid] = {
                        "incident_id": iid,
                        "similarity": score,
                        "timestamp": timestamp,
                        "metadata": metadata,
                    }

        # Return top_k incidents
        result = list(incidents.values())
        result.sort(key=lambda x: x["similarity"], reverse=True)
        return result[:top_k]
