# interaction_handler.py
"""
Interaction Handler

Manages pending user interactions:
- Tracks active questions
- Handles timeouts
- Routes responses back to planning
- Manages execution modes
"""

import asyncio
from typing import Dict, Optional, Callable, Any
from datetime import datetime
import logging
from interaction_classifier import InteractionClassifier, QuestionClassification, ExecutionMode

logger = logging.getLogger(__name__)


class PendingInteraction:
    """Represents a question waiting for user response"""
    
    def __init__(
        self,
        interaction_id: str,
        plan_id: str,
        user_id: str,
        question_text: str,
        classification: QuestionClassification,
        created_at: str
    ):
        self.interaction_id = interaction_id
        self.plan_id = plan_id
        self.user_id = user_id
        self.question_text = question_text
        self.classification = classification
        self.created_at = created_at
        self.response_future = asyncio.Future()
        self.timeout_task = None
    
    def set_response(self, response: Any):
        """Set user's response"""
        if not self.response_future.done():
            self.response_future.set_result(response)
            if self.timeout_task:
                self.timeout_task.cancel()
    
    def cancel(self):
        """Cancel this interaction"""
        if not self.response_future.done():
            self.response_future.set_exception(asyncio.CancelledError())
            if self.timeout_task:
                self.timeout_task.cancel()


class InteractionHandler:
    """
    Handles user interactions during plan execution
    """
    
    def __init__(self, event_broadcaster):
        """
        Initialize handler
        
        Args:
            event_broadcaster: For emitting interaction events
        """
        self.broadcaster = event_broadcaster
        self.classifier = InteractionClassifier()
        self.pending_interactions: Dict[str, PendingInteraction] = {}
        self.execution_modes: Dict[str, ExecutionMode] = {}  # Per-plan modes
        self.interaction_counter = 0
    
    async def ask_user(
        self,
        plan_id: str,
        user_id: str,
        question_text: str,
        context: Optional[Dict] = None
    ) -> Any:
        """
        Ask user a question and wait for response
        
        Args:
            plan_id: ID of the plan asking
            user_id: User to ask
            question_text: The question
            context: Optional context for classification
            
        Returns:
            User's response or default action
        """
        
        # Check execution mode
        mode = self.execution_modes.get(plan_id, ExecutionMode.INTERACTIVE)
        
        # Classify the question
        classification = self.classifier.classify(question_text, context)
        
        logger.info(f"Question classified: type={classification.type.value}, risk={classification.risk_level.value}")
        
        # In autonomous mode, auto-answer non-critical questions
        if mode == ExecutionMode.AUTONOMOUS and classification.risk_level.value != "critical":
            logger.info("Autonomous mode: auto-answering with default")
            return self._get_default_response(classification)
        
        # In supervised mode, only ask for high/critical risk
        if mode == ExecutionMode.SUPERVISED:
            if classification.risk_level.value in ["low", "medium"]:
                logger.info("Supervised mode: auto-answering low/medium risk")
                return self._get_default_response(classification)
        
        # Create interaction
        self.interaction_counter += 1
        interaction_id = f"interaction_{self.interaction_counter}"
        
        interaction = PendingInteraction(
            interaction_id=interaction_id,
            plan_id=plan_id,
            user_id=user_id,
            question_text=question_text,
            classification=classification,
            created_at=datetime.now().isoformat()
        )
        
        self.pending_interactions[interaction_id] = interaction
        
        # Emit interaction event to UI
        await self._emit_interaction_event(interaction)
        
        # Set up timeout if applicable
        if classification.timeout_ms:
            interaction.timeout_task = asyncio.create_task(
                self._handle_timeout(interaction)
            )
        
        try:
            # Wait for response
            logger.info(f"Waiting for user response to interaction {interaction_id}")
            response = await interaction.response_future
            logger.info(f"Got response: {response}")
            return response
            
        except asyncio.CancelledError:
            logger.warning(f"Interaction {interaction_id} cancelled")
            return None
            
        finally:
            # Clean up
            if interaction_id in self.pending_interactions:
                del self.pending_interactions[interaction_id]
    
    async def submit_response(
        self,
        interaction_id: str,
        response: Any
    ) -> bool:
        """
        Submit user's response to a pending interaction
        
        Args:
            interaction_id: ID of the interaction
            response: User's response
            
        Returns:
            True if accepted, False if interaction not found
        """
        
        interaction = self.pending_interactions.get(interaction_id)
        
        if not interaction:
            logger.warning(f"Interaction {interaction_id} not found")
            return False
        
        logger.info(f"Submitting response to {interaction_id}: {response}")
        interaction.set_response(response)
        
        return True
    
    def set_execution_mode(self, plan_id: str, mode: ExecutionMode):
        """Set execution mode for a plan"""
        self.execution_modes[plan_id] = mode
        logger.info(f"Set execution mode for plan {plan_id}: {mode.value}")
    
    def get_pending_interaction(self, plan_id: str) -> Optional[PendingInteraction]:
        """Get pending interaction for a plan"""
        for interaction in self.pending_interactions.values():
            if interaction.plan_id == plan_id:
                return interaction
        return None
    
    def get_pending_interaction_by_user(self, user_id: str) -> Optional[PendingInteraction]:
        """Get any pending interaction for a user"""
        for interaction in self.pending_interactions.values():
            if interaction.user_id == user_id:
                return interaction
        return None
    
    async def _handle_timeout(self, interaction: PendingInteraction):
        """Handle interaction timeout"""
        
        timeout_ms = interaction.classification.timeout_ms
        
        if not timeout_ms:
            return  # No timeout
        
        try:
            await asyncio.sleep(timeout_ms / 1000.0)
            
            # Timeout reached
            logger.warning(f"Interaction {interaction.interaction_id} timed out")
            
            # Get default action
            default_response = self._get_default_response(interaction.classification)
            
            # Emit timeout event
            await self._emit_timeout_event(interaction, default_response)
            
            # Set default response
            interaction.set_response(default_response)
            
        except asyncio.CancelledError:
            # Timeout was cancelled (user responded)
            pass
    
    def _get_default_response(self, classification: QuestionClassification) -> Any:
        """Get default response based on classification"""
        
        default_action = classification.default_action
        
        if default_action == "yes":
            return {"action": "yes", "value": True}
        elif default_action == "no":
            return {"action": "no", "value": False}
        elif default_action == "skip":
            return {"action": "skip", "value": None}
        elif default_action == "cancel":
            return {"action": "cancel", "value": None}
        elif default_action == "first":
            # First suggested action
            if classification.suggested_actions:
                return {"action": "choice", "value": classification.suggested_actions[0]}
            return {"action": "skip", "value": None}
        else:
            return {"action": "continue", "value": None}
    
    async def _emit_interaction_event(self, interaction: PendingInteraction):
        """Emit event to UI about new interaction"""
        
        from event_broadcaster import Event, EventType
        
        classification = interaction.classification
        
        event = Event(
            event_type=EventType.PLANNING_NEEDS_INPUT,
            data={
                "interaction_id": interaction.interaction_id,
                "plan_id": interaction.plan_id,
                "question": interaction.question_text,
                "type": classification.type.value,
                "risk_level": classification.risk_level.value,
                "timeout_ms": classification.timeout_ms,
                "require_explicit": classification.require_explicit,
                "suggested_actions": classification.suggested_actions,
                "disclaimer": classification.disclaimer,
                "warning_level": classification.warning_level,
                "amount": classification.amount,
                "domain": classification.domain,
                "timestamp": interaction.created_at
            },
            min_auth_level=1
        )
        
        await self.broadcaster.broadcast(event)
    
    async def _emit_timeout_event(self, interaction: PendingInteraction, default_response: Any):
        """Emit event about timeout"""
        
        from event_broadcaster import Event, EventType
        
        event = Event(
            event_type=EventType.LOG_EVENT,
            data={
                "level": "WARNING",
                "category": "INTERACTION_TIMEOUT",
                "message": f"Interaction timed out, using default: {default_response.get('action')}",
                "interaction_id": interaction.interaction_id,
                "plan_id": interaction.plan_id
            },
            min_auth_level=2
        )
        
        await self.broadcaster.broadcast(event)