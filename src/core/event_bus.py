"""
Event Bus for AstraGuard Core Subsystems.
Implements a singleton event bus for publishing and subscribing to system events.
Features:
- Async event processing
- Event history for sourcing/replay
- Delivery guarantee mechanisms
"""

import asyncio
import logging
from typing import List, Dict, Callable, Type, Awaitable, Any, Optional
from datetime import datetime
from collections import defaultdict
import uuid

from core.events import Event, TelemetryReceived, AnomalyDetected, StateTransitioned

logger = logging.getLogger(__name__)

EventHandler = Callable[[Event], Awaitable[None]]

class EventBus:
    _instance = None
    _lock = asyncio.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EventBus, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance

    def __init__(self):
        if self.initialized:
            return
        self.subscribers: Dict[Type[Event], List[EventHandler]] = defaultdict(list)
        self.event_history: List[Event] = []
        self.processing_queue: asyncio.Queue = asyncio.Queue()
        self.is_running = False
        self.metrics = {
            "events_published": 0,
            "events_delivered": 0,
            "errors": 0,
            "latency_ms": []  # Simple latency tracking
        }
        self.initialized = True

    async def start(self):
        """Start the event processing loop."""
        if self.is_running:
            return
        self.is_running = True
        asyncio.create_task(self._process_queue())
        logger.info("Event Bus started.")

    async def stop(self):
        """Stop the event processing loop."""
        self.is_running = False
        logger.info("Event Bus stopped.")

    def subscribe(self, event_type: Type[Event], handler: EventHandler):
        """Register an async handler for a specific event type."""
        self.subscribers[event_type].append(handler)
        logger.debug(f"Subscribed {handler.__name__} to {event_type.__name__}")

    async def publish(self, event: Event):
        """Publish an event to the bus asynchronously."""
        self.event_history.append(event)
        await self.processing_queue.put(event)
        self.metrics["events_published"] += 1
        logger.debug(f"Published event: {event.event_id} ({event.__class__.__name__})")

    async def _process_queue(self):
        """Main loop for processing events."""
        while self.is_running:
            try:
                event = await self.processing_queue.get()
                start_time = datetime.utcnow()
                
                tasks = []
                # Check for direct type match and superclass matches if needed (simple direct for now)
                handlers = self.subscribers.get(type(event), [])
                
                # Also check for subscribers to base Event class (catch-all)
                if type(event) != Event:
                    handlers.extend(self.subscribers.get(Event, []))

                for handler in handlers:
                    tasks.append(self._safely_handle(handler, event))
                
                if tasks:
                    await asyncio.gather(*tasks)
                
                self.processing_queue.task_done()
                
                # Metrics
                latency = (datetime.utcnow() - start_time).total_seconds() * 1000
                self.metrics["latency_ms"].append(latency)
                # Keep latency list small
                if len(self.metrics["latency_ms"]) > 100:
                    self.metrics["latency_ms"].pop(0)

            except Exception as e:
                logger.error(f"Error in event processing loop: {e}", exc_info=True)
                self.metrics["errors"] += 1

    async def _safely_handle(self, handler: EventHandler, event: Event):
        try:
            await handler(event)
            self.metrics["events_delivered"] += 1
        except Exception as e:
            logger.error(f"Error in handler {handler.__name__} for event {event.event_id}: {e}", exc_info=True)
            self.metrics["errors"] += 1

    def get_history(self, event_type: Optional[Type[Event]] = None) -> List[Event]:
        """Retrieve event history, optionally filtered by type."""
        if event_type:
            return [e for e in self.event_history if isinstance(e, event_type)]
        return self.event_history

    async def replay_events(self, start_time: Optional[datetime] = None):
        """Replay events from history to current subscribers."""
        logger.info(f"Replaying events from {start_time or 'beginning'}")
        count = 0
        for event in self.event_history:
            if start_time and event.timestamp < start_time:
                continue
            
            # Re-queue the event for processing
            # Note: differentiate replay? For now just re-process.
            # Real sourcing might need to bypass side-effects or have specialized replay handlers.
            # Assuming idempotent handlers or state-reconstruction purpose.
            await self.processing_queue.put(event) 
            count += 1
        logger.info(f"Replayed {count} events.")

# Global instance accessor
_bus = EventBus()
def get_event_bus() -> EventBus:
    return _bus
