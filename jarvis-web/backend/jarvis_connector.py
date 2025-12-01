# jarvis_connector.py
"""
JARVIS Core Connector

Bridges WebSocket server with JARVIS core system.
Routes messages between UI clients and JARVIS, emits events.
"""

import asyncio
import sys
from pathlib import Path
from typing import Optional, Callable, Awaitable
import logging

# Import event broadcaster
from event_broadcaster import (
    EventBroadcaster,
    emit_planning_event,
    emit_search_event,
    emit_intent_event,
    emit_log_event,
    EventType
)

logger = logging.getLogger(__name__)


class JarvisConnector:
    """
    Connects WebSocket server to JARVIS core
    
    Responsibilities:
    - Route messages from WebSocket to JARVIS
    - Capture JARVIS responses back to WebSocket
    - Emit events for planning, search, intent, etc.
    - Handle async communication
    """
    
    def __init__(self, jarvis_core_path: Optional[str] = None, event_broadcaster = None):
        """
        Initialize connector
        
        Args:
            jarvis_core_path: Path to JARVIS core directory
            event_broadcaster: EventBroadcaster instance for emitting events
        """
        # Determine JARVIS path
        if jarvis_core_path is None:
            # Try to find JARVIS relative to this script
            # Backend is in jarvis-web/backend/, JARVIS core is in parent of jarvis-web/
            backend_dir = Path(__file__).parent
            jarvis_web_dir = backend_dir.parent
            jarvis_core_path = jarvis_web_dir.parent
            
            logger.info(f"Auto-detecting JARVIS path from backend location")
            logger.info(f"  Backend: {backend_dir}")
            logger.info(f"  Looking for JARVIS in: {jarvis_core_path}")
        
        self.jarvis_core_path = Path(jarvis_core_path)
        self.jarvis_core = None
        self.is_initialized = False
        self.response_callbacks = {}
        self.event_broadcaster = event_broadcaster  # Store for event emission
        self.interaction_handler = None  # Will be initialized after event_broadcaster is set
        
        logger.info(f"JARVIS connector path: {self.jarvis_core_path}")
        
    async def initialize(self):
        """Initialize connection to JARVIS core"""
        
        logger.info("Initializing JARVIS connector...")
        
        # Verify jarvis_core.py exists
        jarvis_core_file = self.jarvis_core_path / "jarvis_core.py"
        
        if not jarvis_core_file.exists():
            logger.error(f"jarvis_core.py not found at: {jarvis_core_file}")
            logger.error(f"Checked directory: {self.jarvis_core_path}")
            logger.error(f"Directory exists: {self.jarvis_core_path.exists()}")
            if self.jarvis_core_path.exists():
                logger.error(f"Contents: {list(self.jarvis_core_path.glob('*.py'))}")
            logger.warning("Falling back to mock implementation")
            self.jarvis_core = MockJarvisCore()
            await self.jarvis_core.initialize()
            self.is_initialized = True
            return
        
        # Add JARVIS path to sys.path
        jarvis_path_str = str(self.jarvis_core_path)
        if jarvis_path_str not in sys.path:
            sys.path.insert(0, jarvis_path_str)
            logger.info(f"✓ Added {jarvis_path_str} to Python path")
        
        try:
            # Try to import real JARVIS core
            logger.info("Attempting to import JARVIS core...")
            from jarvis_core import JarvisCore
            
            logger.info("✓ JarvisCore imported successfully")
            
            # Create instance
            self.jarvis_core = JarvisCore()
            
            # Initialize (this is async in JARVIS)
            logger.info("Initializing JARVIS core...")
            await self.jarvis_core.initialize()
            
            logger.info("✓ JARVIS core initialized successfully!")
            logger.info(f"  - State: {self.jarvis_core.state}")
            logger.info(f"  - Memory: {'✓' if hasattr(self.jarvis_core, 'memory_manager') and self.jarvis_core.memory_manager else '✗'}")
            logger.info(f"  - Planner: {'✓' if hasattr(self.jarvis_core, 'planning_orchestrator') and self.jarvis_core.planning_orchestrator else '✗'}")
            logger.info(f"  - Intent: {'✓' if hasattr(self.jarvis_core, 'intent_classifier') and self.jarvis_core.intent_classifier else '✗'}")
            
            # Wrap planning orchestrator with event emitter
            if hasattr(self.jarvis_core, 'planning_orchestrator') and self.jarvis_core.planning_orchestrator:
                logger.info("Wrapping planning orchestrator with event emitter...")
                from planning_events import PlanningEventEmitter
                
                if self.event_broadcaster:
                    self.planning_emitter = PlanningEventEmitter(
                        self.jarvis_core.planning_orchestrator,
                        self.event_broadcaster
                    )
                    logger.info("✓ Planning events enabled")
                else:
                    logger.warning("Event broadcaster not available - events disabled")
                    self.planning_emitter = None
            else:
                self.planning_emitter = None
                logger.warning("Planning orchestrator not available - events disabled")
            
            # Initialize interaction handler
            if self.event_broadcaster:
                from interaction_handler import InteractionHandler
                self.interaction_handler = InteractionHandler(self.event_broadcaster)
                logger.info("✓ Interaction handler initialized")
            else:
                logger.warning("Event broadcaster not available - interaction handler disabled")
            
            # Setup WebSocket logging
            if self.event_broadcaster:
                from websocket_log_handler import setup_websocket_logging
                self.ws_log_handler = setup_websocket_logging(
                    self.event_broadcaster,
                    logger_names=['jarvis_connector', 'jarvis_core', '__main__']
                )
                logger.info("✓ WebSocket logging enabled")
            else:
                logger.warning("Event broadcaster not available - WebSocket logging disabled")
            
            # Log available methods for debugging
            public_methods = [m for m in dir(self.jarvis_core) if not m.startswith('__') and callable(getattr(self.jarvis_core, m))]
            logger.info(f"  - Total methods: {len(public_methods)}")
            logger.info(f"  - First 15 methods: {public_methods[:15]}")
            logger.info(f"  - Has handle_query: {hasattr(self.jarvis_core, 'handle_query')}")
            logger.info(f"  - Has query: {hasattr(self.jarvis_core, 'query')}")
            logger.info(f"  - Has process_query: {hasattr(self.jarvis_core, 'process_query')}")
            logger.info(f"  - Has process_input: {hasattr(self.jarvis_core, 'process_input')}")
            logger.info(f"  - Has _classify_intent: {hasattr(self.jarvis_core, '_classify_intent')}")
            
            # Check for main entry methods
            entry_methods = [m for m in public_methods if 'process' in m.lower() or 'handle' in m.lower() or 'execute' in m.lower()]
            logger.info(f"  - Potential entry methods: {entry_methods[:10]}")
            
            self.is_initialized = True
            
        except ImportError as e:
            logger.error(f"Could not import JARVIS core: {e}")
            logger.error(f"sys.path: {sys.path[:3]}")
            logger.warning("Using mock JARVIS implementation")
            self.jarvis_core = MockJarvisCore()
            await self.jarvis_core.initialize()
            self.is_initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize JARVIS core: {e}")
            import traceback
            logger.error(traceback.format_exc())
            logger.warning("Using mock JARVIS implementation")
            self.jarvis_core = MockJarvisCore()
            await self.jarvis_core.initialize()
            self.is_initialized = True
    
    async def process_user_message(
        self,
        user_id: str,
        message: str,
        send_response: Callable[[str, dict], Awaitable[None]]
    ) -> dict:
        """
        Process user message through JARVIS
        
        Args:
            user_id: User ID
            message: User message
            send_response: Callback to send response to user
            
        Returns:
            Response dict
        """
        
        if not self.is_initialized:
            return {
                "success": False,
                "error": "JARVIS not initialized"
            }
        
        logger.info(f"Processing message from {user_id}: {message[:50]}...")
        
        # Check if this is a response to a pending interaction
        if self.interaction_handler:
            pending = self.interaction_handler.get_pending_interaction_by_user(user_id)
            if pending:
                logger.info(f"Detected response to pending interaction: {pending.interaction_id}")
                # Submit the response
                await self.interaction_handler.submit_response(
                    pending.interaction_id,
                    {"action": "user_input", "value": message}
                )
                # Acknowledge receipt
                await send_response(user_id, {
                    "type": "assistant_message",
                    "content": "Got it! Continuing...",
                    "timestamp": self._get_timestamp()
                })
                return {"success": True, "handled": "interaction_response"}
        
        try:
            # Check if this is real JARVIS (look for _classify_intent which your JARVIS has)
            is_real_jarvis = hasattr(self.jarvis_core, '_classify_intent') and hasattr(self.jarvis_core, 'planning_orchestrator')
            
            if is_real_jarvis:
                # Your JARVIS is terminal-based, not API-based
                # We need to simulate a terminal query
                logger.info("Using real JARVIS core (terminal-based)")
                logger.info(f"Processing query: {message[:100]}")
                
                try:
                    # Classify intent using the private method
                    intent_result = await self.jarvis_core._classify_intent(message)
                    logger.info(f"Intent classified: {intent_result}")
                    
                    # Route based on intent
                    intent_type = intent_result.get('intent', 'unknown')
                    
                    if intent_type == 'task':
                        # This is a planning request - use planning orchestrator with events
                        orchestrator = self.planning_emitter if self.planning_emitter else (
                            self.jarvis_core.planning_orchestrator if hasattr(self.jarvis_core, 'planning_orchestrator') else None
                        )
                        
                        if orchestrator:
                            logger.info(f"Creating plan with planning orchestrator (events: {'enabled' if self.planning_emitter else 'disabled'})")
                            
                            # Your PlanningOrchestrator uses handle_with_planning(goal, intent_data)
                            if hasattr(orchestrator, 'handle_with_planning'):
                                logger.info("Using handle_with_planning method")
                                logger.info(f"Passing intent_data: {intent_result}")
                                
                                # Your planning_orchestrator expects task.content, so wrap the message
                                # Create a simple object with required attributes
                                import uuid
                                from datetime import datetime
                                
                                class TaskMessage:
                                    def __init__(self, content, user_id):
                                        self.content = content
                                        self.task_id = str(uuid.uuid4())  # Generate unique ID
                                        self.user_id = user_id  # User who requested
                                        self.timestamp = datetime.now().isoformat()  # Current time
                                        self.source_terminal = 0  # WebSocket terminal (ID 0)
                                    
                                    def __str__(self):
                                        return self.content
                                
                                task_obj = TaskMessage(message, user_id)
                                logger.info(f"Created task object: id={task_obj.task_id}, terminal={task_obj.source_terminal}, content={task_obj.content[:50]}")
                                
                                # CAPTURE PLAN OUTPUT - intercept stdout
                                import io
                                from contextlib import redirect_stdout, redirect_stderr
                                
                                captured_output = io.StringIO()
                                
                                try:
                                    # Capture both stdout and stderr
                                    with redirect_stdout(captured_output):
                                        # Call with task object and intent_data
                                        result = await orchestrator.handle_with_planning(
                                            task_obj,  # Object with .content attribute
                                            intent_result
                                        )
                                    
                                    # Get captured text (plan description)
                                    plan_text = captured_output.getvalue()
                                    
                                    logger.info(f"Captured plan output: {plan_text[:200]}")
                                    
                                    # Check if plan is asking for approval
                                    if plan_text and ("Reply 'yes'" in plan_text or "y/n" in plan_text.lower() or "proceed" in plan_text.lower()):
                                        logger.info("Plan requires approval - sending to UI")
                                        
                                        # Send plan to UI for approval via interaction handler
                                        if self.interaction_handler:
                                            user_response = await self.interaction_handler.ask_user(
                                                plan_id=task_obj.task_id,
                                                user_id=user_id,
                                                question_text=plan_text,
                                                context={
                                                    "type": "plan_approval",
                                                    "plan_id": task_obj.task_id
                                                }
                                            )
                                            
                                            logger.info(f"User response: {user_response}")
                                            
                                            # Check response
                                            if user_response and user_response.get('action') in ['yes', 'approve', 'input']:
                                                # User approved - continue execution
                                                # The plan has already been created, now we need to execute it
                                                # For now, send confirmation
                                                response_text = "Plan approved! Execution starting..."
                                            else:
                                                # User rejected or cancelled
                                                response_text = "Plan cancelled by user."
                                                
                                                # Send response and return early
                                                await send_response(user_id, {
                                                    "type": "assistant_message",
                                                    "content": response_text,
                                                    "timestamp": self._get_timestamp()
                                                })
                                                
                                                return {"success": True, "cancelled": True}
                                        else:
                                            # No interaction handler - send plan text as message
                                            response_text = f"Plan created:\n\n{plan_text}\n\n(Interaction handler not available - cannot request approval)"
                                    else:
                                        # No approval needed or plan already executed
                                        logger.info("Plan does not require approval or already completed")
                                    # Call with task object and intent_data
                                    result = await orchestrator.handle_with_planning(
                                        task_obj,  # Object with .content attribute
                                        intent_result
                                    )
                                    
                                    logger.info(f"Planning returned type: {type(result)}")
                                    logger.info(f"Planning returned value: {str(result)[:200]}")
                                    
                                    # Extract response from result - be very flexible
                                    if result is None:
                                        response_text = "Plan completed successfully."
                                    elif isinstance(result, str):
                                        # Result is just a string - format any embedded JSON
                                        response_text = self._format_response(result)
                                        logger.info("Result is plain string")
                                    elif hasattr(result, 'response'):
                                        # Result is an Outcome object with .response
                                        response_text = self._format_response(result.response)
                                        logger.info("Extracted .response attribute")
                                    elif hasattr(result, 'content'):
                                        # Result has .content attribute
                                        response_text = self._format_response(result.content)
                                        logger.info("Extracted .content attribute")
                                    elif isinstance(result, dict):
                                        # Result is a dict
                                        raw_text = result.get('response') or result.get('content') or str(result)
                                        response_text = self._format_response(raw_text)
                                        logger.info("Extracted from dict")
                                    else:
                                        # Unknown type - convert to string
                                        response_text = self._format_response(str(result))
                                        logger.info(f"Converted to string from type: {type(result)}")
                                    
                                    logger.info(f"Final response_text: {response_text[:100]}")
                                    logger.info(f"Planning completed successfully")
                                    
                                    # Check if response contains a question
                                    if self.interaction_handler and self._contains_question(response_text):
                                        logger.info("Response contains a question - checking for interaction")
                                        
                                        # Classify the question
                                        from interaction_classifier import InteractionClassifier
                                        classifier = InteractionClassifier()
                                        classification = classifier.classify(response_text, {
                                            "plan_id": task_obj.task_id,
                                            "user_id": user_id
                                        })
                                        
                                        logger.info(f"Question classified: type={classification.type.value}, risk={classification.risk_level.value}")
                                        
                                        # For now, just send the response - interaction will trigger on next message
                                        # Full integration would pause here and wait
                                    
                                except Exception as plan_error:
                                    logger.error("=" * 60)
                                    logger.error("PLANNING ERROR DETAILS:")
                                    logger.error(f"Error type: {type(plan_error)}")
                                    logger.error(f"Error message: {str(plan_error)}")
                                    logger.error("=" * 60)
                                    logger.error("FULL TRACEBACK:")
                                    import traceback
                                    for line in traceback.format_exc().split('\n'):
                                        logger.error(line)
                                    logger.error("=" * 60)
                                    response_text = f"Planning error: {str(plan_error)}"
                            else:
                                logger.error("handle_with_planning not found")
                                response_text = "Planning system available but method not accessible."
                        else:
                            response_text = "I understand you want me to help with a task. Planning system is available."
                    
                    elif intent_type == 'query':
                        # This is a question - for now, acknowledge it
                        # In a full integration, you'd route to search or knowledge
                        response_text = f"I understand you're asking: '{message}'. Let me help with that.\n\n[Full query handling will be implemented with your search provider integration]"
                    
                    elif intent_type == 'conversation':
                        # Conversational
                        response_text = "I'm here and ready to help! What would you like to do?"
                    
                    else:
                        # Unknown intent type - try to be helpful
                        logger.warning(f"Unknown intent type: {intent_type} - treating as potential task")
                        
                        # If it seems like something actionable, route to planning
                        if intent_type in ['crud_create', 'crud_read', 'crud_update', 'crud_delete'] or \
                           'want' in message.lower() or 'need' in message.lower() or 'help' in message.lower():
                            # Treat as a task
                            logger.info(f"Re-routing {intent_type} to planning")
                            orchestrator = self.planning_emitter if self.planning_emitter else (
                                self.jarvis_core.planning_orchestrator if hasattr(self.jarvis_core, 'planning_orchestrator') else None
                            )
                            
                            if orchestrator and hasattr(orchestrator, 'handle_with_planning'):
                                import uuid
                                from datetime import datetime
                                
                                class TaskMessage:
                                    def __init__(self, content, user_id):
                                        self.content = content
                                        self.task_id = str(uuid.uuid4())
                                        self.user_id = user_id
                                        self.timestamp = datetime.now().isoformat()
                                        self.source_terminal = 0
                                    def __str__(self):
                                        return self.content
                                
                                task_obj = TaskMessage(message, user_id)
                                
                                try:
                                    result = await orchestrator.handle_with_planning(task_obj, intent_result)
                                    
                                    if isinstance(result, str):
                                        response_text = self._format_response(result)
                                    elif hasattr(result, 'response'):
                                        response_text = self._format_response(result.response)
                                    else:
                                        response_text = str(result)
                                except Exception as plan_error:
                                    logger.error(f"Planning failed for {intent_type}: {plan_error}")
                                    response_text = f"I understood you want to '{message}', but I encountered an error. Let me know if you'd like to try rephrasing."
                            else:
                                response_text = f"I understood you want to '{message}'. I'm working on adding support for this type of request!"
                        else:
                            response_text = f"I'm not sure how to help with that yet. Could you rephrase or tell me what you'd like me to do?"
                    
                    # Send response
                    await send_response(user_id, {
                        "type": "assistant_message",
                        "content": response_text,
                        "timestamp": self._get_timestamp()
                    })
                    
                    logger.info(f"Response sent: {response_text}")
                    
                    return {"success": True, "intent": intent_result}
                    
                except Exception as e:
                    logger.error(f"Error in JARVIS processing: {e}")
                    import traceback
                    logger.error(traceback.format_exc())
                    raise
            
            else:
                # Use mock implementation
                logger.warning("Could not detect real JARVIS methods, using mock")
                logger.warning(f"Has _classify_intent: {hasattr(self.jarvis_core, '_classify_intent')}")
                return await self._mock_process_message(user_id, message, send_response)
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            import traceback
            logger.error(traceback.format_exc())
            
            await emit_log_event(
                "ERROR",
                "MESSAGE_PROCESSING",
                f"Failed to process message: {str(e)}",
                min_auth_level=2
            )
            
            await send_response(user_id, {
                "type": "assistant_message",
                "content": f"Sorry, I encountered an error: {str(e)}",
                "timestamp": self._get_timestamp()
            })
            
            return {"success": False, "error": str(e)}
    
    async def _mock_process_message(
        self,
        user_id: str,
        message: str,
        send_response: Callable
    ) -> dict:
        """Process message with mock JARVIS (original implementation)"""
        
        # Step 1: Classify intent
        await emit_intent_event(
            EventType.INTENT_CLASSIFYING,
            message,
            {"user_id": user_id},
            min_auth_level=2
        )
        
        intent = await self.jarvis_core.classify_intent(message)
        
        await emit_intent_event(
            EventType.INTENT_CLASSIFIED,
            message,
            {
                "intent": intent["intent"],
                "confidence": intent.get("confidence", 1.0),
                "fast_path_used": intent.get("fast_path", False)
            },
            min_auth_level=2
        )
        
        # Step 2: Route based on intent
        if intent["intent"] == "task":
            # This is a planning request
            response = await self._handle_task(user_id, message, send_response)
        
        elif intent["intent"] == "query":
            # This is a question/query
            response = await self._handle_query(user_id, message, send_response)
        
        elif intent["intent"] == "conversation":
            # This is conversational
            response = await self._handle_conversation(user_id, message, send_response)
        
        else:
            response = {
                "success": True,
                "content": f"I understand this as a '{intent['intent']}' intent. Let me help with that."
            }
        
        # Send response
        await send_response(user_id, {
            "type": "assistant_message",
            "content": response.get("content", "I processed your request."),
            "timestamp": self._get_timestamp()
        })
        
        return response
    
    async def _handle_task(
        self,
        user_id: str,
        message: str,
        send_response: Callable
    ) -> dict:
        """Handle task/planning requests"""
        
        logger.info(f"Creating plan for: {message[:50]}...")
        
        # Step 1: Decompose into plan
        plan = await self.jarvis_core.create_plan(message)
        
        # Step 2: Emit plan created event
        await emit_planning_event(
            EventType.PLANNING_CREATED,
            plan["id"],
            {
                "description": plan["description"],
                "steps": plan["steps"],
                "requires_approval": True
            },
            min_auth_level=1
        )
        
        # Step 3: Wait for approval (in real implementation)
        # For now, auto-approve
        logger.info(f"Plan {plan['id']} created, awaiting approval...")
        
        # Simulate approval delay
        await asyncio.sleep(1)
        
        # Auto-approve for demo
        await emit_planning_event(
            EventType.PLANNING_APPROVED,
            plan["id"],
            {"approved_by": user_id},
            min_auth_level=1
        )
        
        # Step 4: Execute plan
        await self._execute_plan(user_id, plan, send_response)
        
        return {
            "success": True,
            "content": f"I've created a plan with {len(plan['steps'])} steps and started execution.",
            "plan_id": plan["id"]
        }
    
    async def _execute_plan(
        self,
        user_id: str,
        plan: dict,
        send_response: Callable
    ):
        """Execute plan steps"""
        
        plan_id = plan["id"]
        
        # Emit plan started
        await emit_planning_event(
            EventType.PLANNING_STARTED,
            plan_id,
            {
                "description": plan["description"],
                "steps": plan["steps"]
            },
            min_auth_level=1
        )
        
        # Execute each step
        for i, step in enumerate(plan["steps"]):
            step_id = str(i + 1)
            
            # Step started
            await emit_planning_event(
                EventType.PLANNING_STEP_STARTED,
                plan_id,
                {
                    "step_id": step_id,
                    "description": step["description"]
                },
                min_auth_level=1
            )
            
            # Execute step (with search if needed)
            result = await self._execute_step(step)
            
            # Step completed
            await emit_planning_event(
                EventType.PLANNING_STEP_COMPLETED,
                plan_id,
                {
                    "step_id": step_id,
                    "result": result["result"],
                    "duration_ms": result.get("duration_ms", 1000)
                },
                min_auth_level=1
            )
        
        # Plan completed
        await emit_planning_event(
            EventType.PLANNING_COMPLETED,
            plan_id,
            {
                "description": plan["description"],
                "total_steps": len(plan["steps"])
            },
            min_auth_level=1
        )
        
        # Send completion message
        await send_response(user_id, {
            "type": "assistant_message",
            "content": f"✓ Plan completed! All {len(plan['steps'])} steps finished.",
            "timestamp": self._get_timestamp()
        })
    
    async def _execute_step(self, step: dict) -> dict:
        """Execute a single plan step"""
        
        description = step["description"]
        
        # Check if step needs search
        search_keywords = ["research", "find", "search", "look up", "what are"]
        needs_search = any(kw in description.lower() for kw in search_keywords)
        
        if needs_search:
            # Emit search event
            query = description
            
            await emit_search_event(
                EventType.SEARCH_QUERY,
                query,
                {"num_results": 5},
                min_auth_level=1
            )
            
            # Simulate search
            await asyncio.sleep(1)
            
            await emit_search_event(
                EventType.SEARCH_RESULTS,
                query,
                {
                    "results_count": 5,
                    "duration_ms": 1200
                },
                min_auth_level=1
            )
            
            result = f"Found information about: {description}"
        else:
            # Regular execution
            await asyncio.sleep(0.5)
            result = f"Completed: {description}"
        
        return {
            "result": result,
            "duration_ms": 1200
        }
    
    async def _handle_query(
        self,
        user_id: str,
        message: str,
        send_response: Callable
    ) -> dict:
        """Handle query/question"""
        
        # Check if needs search
        response = await self.jarvis_core.answer_query(message)
        
        return {
            "success": True,
            "content": response
        }
    
    async def _handle_conversation(
        self,
        user_id: str,
        message: str,
        send_response: Callable
    ) -> dict:
        """Handle conversational message"""
        
        response = await self.jarvis_core.converse(message)
        
        return {
            "success": True,
            "content": response
        }
    
    def _get_timestamp(self):
        """Get current timestamp"""
        from datetime import datetime
        return datetime.now().isoformat()
    
    def _contains_question(self, text: str) -> bool:
        """Check if text contains a question"""
        if not text:
            return False
        
        # Check for question marks
        if '?' in text:
            return True
        
        # Check for common question patterns
        question_patterns = [
            r"reply ['\"]?yes['\"]?",
            r"reply ['\"]?no['\"]?",
            r"confirm",
            r"approve",
            r"what (date|time|when|where|who|color|preference)",
            r"which (option|choice|one)",
            r"how (many|much|long)",
            r"would you like",
            r"do you want"
        ]
        
        import re
        return any(re.search(pattern, text, re.I) for pattern in question_patterns)
    
    def _format_response(self, text: str) -> str:
        """Format response text to make dict strings more readable"""
        if not isinstance(text, str):
            text = str(text)
        
        import re
        import json
        
        # Try to find and format dict/JSON strings
        try:
            # Look for dict patterns like {'key': 'value'}
            formatted = text
            
            # Replace dict-style strings with more readable format
            # {'hotel': 'The Hermitage Hotel', 'address': '...'} 
            # becomes:
            # Hotel: The Hermitage Hotel
            # Address: ...
            
            def format_dict_match(match):
                dict_str = match.group(0)
                try:
                    # Try to eval as dict
                    d = eval(dict_str)
                    if isinstance(d, dict):
                        lines = []
                        for k, v in d.items():
                            # Format key nicely (capitalize, remove underscores)
                            nice_key = k.replace('_', ' ').title()
                            if isinstance(v, dict):
                                # Nested dict
                                lines.append(f"\n{nice_key}:")
                                for k2, v2 in v.items():
                                    nice_key2 = k2.replace('_', ' ').title()
                                    lines.append(f"  • {nice_key2}: {v2}")
                            else:
                                lines.append(f"  • {nice_key}: {v}")
                        return '\n'.join(lines)
                except:
                    pass
                return dict_str
            
            # Find dict patterns
            formatted = re.sub(r"\{[^{}]+\}", format_dict_match, formatted)
            
            return formatted
            
        except Exception as e:
            # If formatting fails, just return original
            return text
    
    def _format_response(self, text: str) -> str:
        """Format response text to make embedded dicts/lists more readable"""
        if not isinstance(text, str):
            return str(text)
        
        import re
        
        # Simple approach: detect {'key': 'value'} patterns and format them
        # This handles the common case of embedded Python repr() output
        
        formatted = text
        
        # Replace bullet-separated dicts with line breaks
        # Match patterns like: • Key: {'nested': 'dict'}
        formatted = re.sub(r'(\{[^}]+\})', lambda m: '\n    ' + m.group(0), formatted)
        
        # Replace dict/list brackets to be more readable
        formatted = formatted.replace("{'", "\n      ")
        formatted = formatted.replace("'}", "")
        formatted = formatted.replace("', '", "\n      ")
        formatted = formatted.replace("': '", ": ")
        formatted = formatted.replace("':", ":")
        
        return formatted


class MockJarvisCore:
    """Mock JARVIS core for testing"""
    
    async def initialize(self):
        """Initialize mock"""
        logger.info("Mock JARVIS initialized")
    
    async def classify_intent(self, message: str) -> dict:
        """Mock intent classification"""
        
        # Simple keyword-based classification
        message_lower = message.lower()
        
        if any(kw in message_lower for kw in ["plan", "help me", "create", "make"]):
            return {"intent": "task", "confidence": 0.9, "fast_path": True}
        elif any(kw in message_lower for kw in ["what", "how", "why", "when", "where"]):
            return {"intent": "query", "confidence": 0.85, "fast_path": True}
        else:
            return {"intent": "conversation", "confidence": 0.8, "fast_path": True}
    
    async def create_plan(self, task: str) -> dict:
        """Mock plan creation"""
        
        import uuid
        
        # Create a simple plan
        plan = {
            "id": f"plan_{uuid.uuid4().hex[:8]}",
            "description": task,
            "steps": [
                {"description": f"Research requirements for: {task}"},
                {"description": f"Gather necessary information"},
                {"description": f"Execute the main task"},
                {"description": f"Verify results"}
            ]
        }
        
        return plan
    
    async def answer_query(self, query: str) -> str:
        """Mock query answering"""
        return f"Here's what I found about: {query}\n\n[This is a mock response - integrate with real JARVIS for actual answers]"
    
    async def converse(self, message: str) -> str:
        """Mock conversation"""
        return f"I understand you said: '{message}'. How can I help you further?"


# Global connector instance
_connector: Optional[JarvisConnector] = None

def get_connector(event_broadcaster=None) -> JarvisConnector:
    """Get global connector instance"""
    global _connector
    if _connector is None:
        _connector = JarvisConnector(event_broadcaster=event_broadcaster)
    return _connector