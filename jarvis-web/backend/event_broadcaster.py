# event_broadcaster.py
"""
JARVIS Event Broadcaster

Manages out-of-band (OOB) event broadcasting to WebSocket clients.
Events are filtered by auth level before sending.

Event Types:
- Planning events (plan created, step started, step completed)
- Search events (query, results, cache hit)
- Intent classification (intent detected, routing)
- System status (state changes, queue updates)
- Logs (errors, warnings, debug info)
"""

from enum import Enum
from typing import Callable, Dict, Set, Any, Optional, Awaitable
from datetime import datetime
from pydantic import BaseModel
import asyncio
import logging

logger = logging.getLogger(__name__)

class EventType(str, Enum):
    """Event types for OOB messages"""
    
    # Planning events
    PLANNING_CREATED = "planning.plan_created"
    PLANNING_APPROVED = "planning.plan_approved"
    PLANNING_REJECTED = "planning.plan_rejected"
    PLANNING_STARTED = "planning.plan_started"
    PLANNING_STEP_STARTED = "planning.step_started"
    PLANNING_STEP_PROGRESS = "planning.step_progress"
    PLANNING_STEP_COMPLETED = "planning.step_completed"
    PLANNING_STEP_FAILED = "planning.step_failed"
    PLANNING_COMPLETED = "planning.plan_completed"
    PLANNING_FAILED = "planning.plan_failed"
    PLANNING_NEEDS_INPUT = "planning.needs_input"  # User interaction required
    
    # Search events
    SEARCH_QUERY = "search.query"
    SEARCH_RESULTS = "search.results"
    SEARCH_CACHE_HIT = "search.cache_hit"
    SEARCH_FAILED = "search.failed"
    
    # Intent classification
    INTENT_CLASSIFYING = "intent.classifying"
    INTENT_CLASSIFIED = "intent.classified"
    INTENT_ROUTING = "intent.routing"
    
    # Memory operations
    MEMORY_CREATE = "memory.create"
    MEMORY_READ = "memory.read"
    MEMORY_UPDATE = "memory.update"
    MEMORY_DELETE = "memory.delete"
    
    # System status
    SYSTEM_STATUS = "system.status"
    SYSTEM_STATE_CHANGE = "system.state_change"
    SYSTEM_QUEUE_UPDATE = "system.queue_update"
    
    # Logs
    LOG_EVENT = "log.event"  # Generic log event
    LOG_ERROR = "log.error"
    LOG_WARNING = "log.warning"
    LOG_INFO = "log.info"
    LOG_DEBUG = "log.debug"

class Event(BaseModel):
    """Event model"""
    event_type: EventType
    data: Dict[str, Any]
    timestamp: str = None
    min_auth_level: int = 0  # Minimum auth level required to receive
    
    def __init__(self, **data):
        if 'timestamp' not in data:
            data['timestamp'] = datetime.now().isoformat()
        super().__init__(**data)
    
    def to_websocket_message(self) -> dict:
        """Convert to WebSocket message format"""
        return {
            "channel": "oob",
            "type": self.event_type.value,
            "data": self.data,
            "timestamp": self.timestamp
        }

class EventBroadcaster:
    """
    Broadcast events to subscribed clients
    
    Features:
    - Auth-level filtering
    - Async event delivery
    - Automatic cleanup of dead subscribers
    """
    
    def __init__(self):
        """Initialize broadcaster"""
        # subscriber_id -> (auth_level, send_function)
        self.subscribers: Dict[str, tuple[int, Callable]] = {}
        
        # Statistics
        self.stats = {
            "events_sent": 0,
            "events_by_type": {},
            "failed_deliveries": 0
        }
    
    def subscribe(
        self,
        subscriber_id: str,
        auth_level: int,
        send_function: Callable[[str, dict], Awaitable[None]]
    ):
        """
        Subscribe to events
        
        Args:
            subscriber_id: Unique subscriber ID (user_id)
            auth_level: Subscriber's auth level
            send_function: Async function to send message: (user_id, message) -> None
        """
        self.subscribers[subscriber_id] = (auth_level, send_function)
        logger.info(f"Subscriber {subscriber_id} registered (auth level: {auth_level})")
    
    def unsubscribe(self, subscriber_id: str):
        """Unsubscribe from events"""
        if subscriber_id in self.subscribers:
            del self.subscribers[subscriber_id]
            logger.info(f"Subscriber {subscriber_id} unregistered")
    
    async def broadcast(self, event: Event):
        """
        Broadcast event to all eligible subscribers
        
        Args:
            event: Event to broadcast
        """
        
        # Update stats
        self.stats["events_sent"] += 1
        event_type_key = event.event_type.value
        self.stats["events_by_type"][event_type_key] = \
            self.stats["events_by_type"].get(event_type_key, 0) + 1
        
        # Convert to WebSocket message
        message = event.to_websocket_message()
        
        # Send to eligible subscribers
        failed_subscribers = []
        
        for subscriber_id, (auth_level, send_func) in self.subscribers.items():
            # Check auth level
            if auth_level < event.min_auth_level:
                continue
            
            # Send event
            try:
                await send_func(subscriber_id, message)
            except Exception as e:
                logger.error(f"Failed to send event to {subscriber_id}: {e}")
                failed_subscribers.append(subscriber_id)
                self.stats["failed_deliveries"] += 1
        
        # Clean up failed subscribers
        for subscriber_id in failed_subscribers:
            self.unsubscribe(subscriber_id)
    
    async def send_to_subscriber(self, subscriber_id: str, event: Event):
        """
        Send event to specific subscriber
        
        Args:
            subscriber_id: Subscriber ID
            event: Event to send
        """
        
        if subscriber_id not in self.subscribers:
            logger.warning(f"Subscriber {subscriber_id} not found")
            return
        
        auth_level, send_func = self.subscribers[subscriber_id]
        
        # Check auth level
        if auth_level < event.min_auth_level:
            logger.warning(
                f"Subscriber {subscriber_id} (level {auth_level}) "
                f"not authorized for event (requires {event.min_auth_level})"
            )
            return
        
        # Send event
        try:
            message = event.to_websocket_message()
            await send_func(subscriber_id, message)
            self.stats["events_sent"] += 1
        except Exception as e:
            logger.error(f"Failed to send event to {subscriber_id}: {e}")
            self.stats["failed_deliveries"] += 1
    
    def get_stats(self) -> dict:
        """Get broadcaster statistics"""
        return {
            **self.stats,
            "active_subscribers": len(self.subscribers),
            "subscribers_by_auth_level": self._count_by_auth_level()
        }
    
    def _count_by_auth_level(self) -> dict:
        """Count subscribers by auth level"""
        counts = {}
        for auth_level, _ in self.subscribers.values():
            counts[auth_level] = counts.get(auth_level, 0) + 1
        return counts


# ==================== HELPER FUNCTIONS ====================

# Global broadcaster instance (will be created by server)
_broadcaster: Optional[EventBroadcaster] = None

def get_broadcaster() -> EventBroadcaster:
    """Get global broadcaster instance"""
    global _broadcaster
    if _broadcaster is None:
        _broadcaster = EventBroadcaster()
    return _broadcaster

async def emit_planning_event(
    event_type: EventType,
    plan_id: str,
    data: dict,
    min_auth_level: int = 1
):
    """
    Helper to emit planning events
    
    Args:
        event_type: Event type
        plan_id: Plan ID
        data: Event data
        min_auth_level: Minimum auth level
    """
    broadcaster = get_broadcaster()
    event = Event(
        event_type=event_type,
        data={"plan_id": plan_id, **data},
        min_auth_level=min_auth_level
    )
    await broadcaster.broadcast(event)

async def emit_search_event(
    event_type: EventType,
    query: str,
    data: dict,
    min_auth_level: int = 1
):
    """
    Helper to emit search events
    
    Args:
        event_type: Event type
        query: Search query
        data: Event data
        min_auth_level: Minimum auth level
    """
    broadcaster = get_broadcaster()
    event = Event(
        event_type=event_type,
        data={"query": query, **data},
        min_auth_level=min_auth_level
    )
    await broadcaster.broadcast(event)

async def emit_intent_event(
    event_type: EventType,
    user_input: str,
    data: dict,
    min_auth_level: int = 2
):
    """
    Helper to emit intent classification events
    
    Args:
        event_type: Event type
        user_input: User input
        data: Event data
        min_auth_level: Minimum auth level (default: power users)
    """
    broadcaster = get_broadcaster()
    event = Event(
        event_type=event_type,
        data={"input": user_input, **data},
        min_auth_level=min_auth_level
    )
    await broadcaster.broadcast(event)

async def emit_log_event(
    level: str,
    category: str,
    message: str,
    min_auth_level: int = 2
):
    """
    Helper to emit log events
    
    Args:
        level: Log level (ERROR, WARNING, INFO, DEBUG)
        category: Log category
        message: Log message
        min_auth_level: Minimum auth level
    """
    broadcaster = get_broadcaster()
    
    event_type_map = {
        "ERROR": EventType.LOG_ERROR,
        "WARNING": EventType.LOG_WARNING,
        "INFO": EventType.LOG_INFO,
        "DEBUG": EventType.LOG_DEBUG
    }
    
    event_type = event_type_map.get(level, EventType.LOG_INFO)
    
    event = Event(
        event_type=event_type,
        data={
            "level": level,
            "category": category,
            "message": message
        },
        min_auth_level=min_auth_level
    )
    await broadcaster.broadcast(event)


# Example usage
if __name__ == "__main__":
    async def test_broadcaster():
        # Create broadcaster
        broadcaster = EventBroadcaster()
        
        # Mock send function
        async def mock_send(user_id: str, message: dict):
            print(f"[{user_id}] Received: {message['type']}")
        
        # Subscribe users with different auth levels
        broadcaster.subscribe("user1", 1, mock_send)  # Standard user
        broadcaster.subscribe("user2", 2, mock_send)  # Power user
        broadcaster.subscribe("admin", 4, mock_send)  # Admin
        
        # Send events with different auth requirements
        await broadcaster.broadcast(Event(
            event_type=EventType.PLANNING_CREATED,
            data={"plan_id": "123", "description": "Test plan"},
            min_auth_level=1  # All users
        ))
        
        await broadcaster.broadcast(Event(
            event_type=EventType.INTENT_CLASSIFIED,
            data={"intent": "task", "confidence": 0.85},
            min_auth_level=2  # Power users only
        ))
        
        await broadcaster.broadcast(Event(
            event_type=EventType.LOG_DEBUG,
            data={"message": "Debug info"},
            min_auth_level=3  # Developers only
        ))
        
        # Stats
        stats = broadcaster.get_stats()
        print(f"\nStats: {stats}")
    
    asyncio.run(test_broadcaster())