# planning_events.py
"""
Planning Event Emission Wrapper

Wraps planning orchestrator calls to emit WebSocket events
for real-time UI updates without modifying core JARVIS code.
"""

import asyncio
from typing import Optional, Dict, Any
from datetime import datetime


class PlanningEventEmitter:
    """
    Wraps planning orchestrator to emit events during execution
    
    Events emitted:
    - planning.plan_created
    - planning.step_started
    - planning.step_progress
    - planning.step_completed
    - planning.step_failed
    - planning.plan_completed
    """
    
    def __init__(self, planning_orchestrator, event_broadcaster):
        """
        Initialize event emitter
        
        Args:
            planning_orchestrator: The actual PlanningOrchestrator instance
            event_broadcaster: EventBroadcaster for sending events
        """
        self.orchestrator = planning_orchestrator
        self.broadcaster = event_broadcaster
        self.active_plans = {}  # Track active plans
    
    async def handle_with_planning(self, task, intent_data):
        """
        Wrapper around planning_orchestrator.handle_with_planning
        
        Emits events as planning progresses
        """
        
        plan_id = task.task_id
        
        # Emit: Plan starting
        await self._emit_event(
            "planning.plan_started",
            plan_id,
            {
                "description": task.content,
                "user_id": task.user_id,
                "intent": intent_data.get("intent"),
                "requires_decomposition": intent_data.get("requires_decomposition", False)
            }
        )
        
        # Track plan
        self.active_plans[plan_id] = {
            "task": task,
            "intent_data": intent_data,
            "started_at": datetime.now().isoformat(),
            "status": "in_progress"
        }
        
        try:
            # Call actual planning orchestrator
            # We'll intercept by wrapping the planner object itself
            result = await self._execute_with_events(task, intent_data)
            
            # Emit: Plan completed
            await self._emit_event(
                "planning.plan_completed",
                plan_id,
                {
                    "description": task.content,
                    "status": "completed",
                    "duration_ms": self._get_duration(plan_id)
                }
            )
            
            # Clean up
            if plan_id in self.active_plans:
                del self.active_plans[plan_id]
            
            return result
            
        except Exception as e:
            # Emit: Plan failed
            await self._emit_event(
                "planning.plan_failed",
                plan_id,
                {
                    "description": task.content,
                    "error": str(e)
                }
            )
            
            # Clean up
            if plan_id in self.active_plans:
                del self.active_plans[plan_id]
            
            raise
    
    async def _execute_with_events(self, task, intent_data):
        """
        Execute planning with event emission
        
        This wraps the actual planner to intercept step execution
        """
        
        plan_id = task.task_id
        
        # For now, call the real orchestrator
        # We'll add step interception in next iteration
        result = await self.orchestrator.handle_with_planning(task, intent_data)
        
        # TODO: In Phase 2, we'll intercept individual step execution
        # For now, emit a single "steps executed" event
        
        return result
    
    async def _emit_event(self, event_type: str, plan_id: str, data: Dict[str, Any]):
        """Emit event through broadcaster"""
        
        from event_broadcaster import Event, EventType
        
        # Map our event types to EventBroadcaster types
        event_type_map = {
            "planning.plan_started": EventType.PLANNING_STARTED,
            "planning.plan_created": EventType.PLANNING_CREATED,
            "planning.step_started": EventType.PLANNING_STEP_STARTED,
            "planning.step_progress": EventType.PLANNING_STEP_PROGRESS,
            "planning.step_completed": EventType.PLANNING_STEP_COMPLETED,
            "planning.step_failed": EventType.PLANNING_STEP_FAILED,
            "planning.plan_completed": EventType.PLANNING_COMPLETED,
            "planning.plan_failed": EventType.PLANNING_FAILED
        }
        
        broadcaster_type = event_type_map.get(event_type)
        if not broadcaster_type:
            return
        
        event = Event(
            event_type=broadcaster_type,
            data={
                "plan_id": plan_id,
                **data,
                "timestamp": datetime.now().isoformat()
            },
            min_auth_level=1  # All authenticated users can see planning events
        )
        
        await self.broadcaster.broadcast(event)
    
    def _get_duration(self, plan_id: str) -> int:
        """Calculate duration of plan execution"""
        if plan_id not in self.active_plans:
            return 0
        
        started_at = self.active_plans[plan_id]["started_at"]
        started = datetime.fromisoformat(started_at)
        duration = (datetime.now() - started).total_seconds() * 1000
        return int(duration)
    
    # Proxy other methods to orchestrator
    def __getattr__(self, name):
        """Pass through any other method calls to the real orchestrator"""
        return getattr(self.orchestrator, name)