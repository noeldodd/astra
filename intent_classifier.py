# intent_classifier.py
"""
JARVIS Intent Classifier

Extracts and handles intent classification logic.
Determines what the user wants to do and routes to appropriate handlers.

Intent Types:
- QUESTION: Information retrieval, queries
- TASK: Goal decomposition and execution
- CHAT: Conversational interaction
- COMMAND: Direct system commands
"""

import json
from typing import Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum


class IntentType(Enum):
    """Types of user intents"""
    QUESTION = "question"
    TASK = "task"
    CHAT = "chat"
    COMMAND = "command"
    UNCLEAR = "unclear"


@dataclass
class IntentResult:
    """Result of intent classification"""
    intent_type: IntentType
    confidence: float
    reasoning: str
    requires_decomposition: bool = False
    is_simple_query: bool = False
    suggested_handler: Optional[str] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for logging"""
        return {
            "intent": self.intent_type.value,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            "requires_decomposition": self.requires_decomposition,
            "is_simple_query": self.is_simple_query,
            "suggested_handler": self.suggested_handler
        }


class IntentClassifier:
    """
    Classifies user intents and routes to appropriate handlers.
    
    Features:
    - LLM-based intent classification
    - Confidence scoring
    - Simple pattern matching for common cases
    - Intent history tracking
    - Performance metrics
    """
    
    def __init__(self, jarvis_core):
        """
        Initialize with reference to JarvisCore
        
        Args:
            jarvis_core: Main JARVIS instance for accessing state
        """
        self.core = jarvis_core
        self.classification_history = []
        self.stats = {
            "total_classifications": 0,
            "by_intent": {},
            "high_confidence": 0,
            "low_confidence": 0
        }
    
    # ==================== MAIN CLASSIFICATION ====================
    
    async def classify(self, user_input: str, context: Optional[Dict] = None) -> IntentResult:
        """
        Classify user intent
        
        Args:
            user_input: The user's message
            context: Optional context (conversation history, current task, etc.)
            
        Returns:
            IntentResult with classification and metadata
        """
        
        # Quick pattern matching for obvious cases
        quick_result = self._quick_classify(user_input)
        if quick_result:
            self._update_stats(quick_result)
            return quick_result
        
        # LLM-based classification for complex cases
        self.core._log("INTENT", f"Classifying: '{user_input[:50]}...'")
        
        llm_result = await self._llm_classify(user_input, context)
        
        if llm_result:
            self._update_stats(llm_result)
            return llm_result
        
        # Fallback: unclear intent
        fallback = IntentResult(
            intent_type=IntentType.UNCLEAR,
            confidence=0.0,
            reasoning="Classification failed",
            suggested_handler="chat"
        )
        
        self._update_stats(fallback)
        return fallback
    
    def _quick_classify(self, user_input: str) -> Optional[IntentResult]:
        """
        Quick pattern-based classification for obvious cases
        
        Returns:
            IntentResult if confident, None if needs LLM classification
        """
        
        text = user_input.lower().strip()
        
        # Direct commands (high confidence)
        if text in ["help", "status", "exit", "quit", "clear"]:
            return IntentResult(
                intent_type=IntentType.COMMAND,
                confidence=1.0,
                reasoning="Direct system command",
                suggested_handler="command"
            )
        
        # Simple greetings (high confidence)
        greetings = ["hi", "hello", "hey", "good morning", "good afternoon", "good evening"]
        if text in greetings or any(text.startswith(g) for g in greetings):
            return IntentResult(
                intent_type=IntentType.CHAT,
                confidence=0.95,
                reasoning="Simple greeting",
                suggested_handler="chat"
            )
        
        # Question indicators (medium-high confidence)
        question_words = ["what", "when", "where", "who", "why", "how", "which", "can you tell me"]
        if any(text.startswith(qw) for qw in question_words) and "?" in text:
            return IntentResult(
                intent_type=IntentType.QUESTION,
                confidence=0.85,
                reasoning="Clear question format",
                is_simple_query=True,
                suggested_handler="question"
            )
        
        # Task indicators (medium confidence)
        task_verbs = ["create", "make", "build", "write", "generate", "find", "search", "organize"]
        if any(text.startswith(tv) for tv in task_verbs):
            # Check if it's complex enough to need decomposition
            word_count = len(text.split())
            requires_decomp = word_count > 10 or " and " in text or " then " in text
            
            return IntentResult(
                intent_type=IntentType.TASK,
                confidence=0.75,
                reasoning="Starts with action verb",
                requires_decomposition=requires_decomp,
                suggested_handler="task"
            )
        
        # If input is very short (1-3 words), likely chat
        if len(text.split()) <= 3 and not text.endswith("?"):
            return IntentResult(
                intent_type=IntentType.CHAT,
                confidence=0.7,
                reasoning="Very short input, likely conversational",
                suggested_handler="chat"
            )
        
        # Need LLM classification
        return None
    
    async def _llm_classify(
        self,
        user_input: str,
        context: Optional[Dict] = None
    ) -> Optional[IntentResult]:
        """
        Use LLM to classify intent for complex cases
        
        Returns:
            IntentResult or None if classification fails
        """
        
        # Build classification prompt
        classification_prompt = self._build_classification_prompt(user_input, context)
        
        # Execute via prompt manager
        result = await self.core.prompt_manager.execute_prompt(
            prompt_text=classification_prompt,
            prompt_id="classify_intent",
            use_smart_model=False,  # Fast model is fine for classification
            max_tokens=200
        )
        
        if not result.success or not result.parsed_json:
            self.core._log("INTENT", "⚠️ Classification failed, using fallback")
            return None
        
        # Parse LLM response
        return self._parse_classification_result(result.parsed_json)
    
    def _build_classification_prompt(
        self,
        user_input: str,
        context: Optional[Dict] = None
    ) -> str:
        """Build the classification prompt"""
        
        context_info = ""
        if context:
            if context.get("active_plan"):
                context_info = "\nContext: User has an active plan in progress."
            if context.get("recent_topic"):
                context_info += f"\nRecent topic: {context['recent_topic']}"
        
        prompt = f"""Classify the user's intent.

USER INPUT:
"{user_input}"{context_info}

INTENT TYPES:
- QUESTION: User wants information, asking about something
- TASK: User wants to accomplish something that may require multiple steps
- CHAT: Conversational, greeting, or simple response
- COMMAND: Direct system command

Consider:
1. Is this a question that needs an answer?
2. Is this a goal/task that needs execution?
3. Is this just conversation?
4. Does this need decomposition into steps?

Respond with JSON:
{{
  "intent": "question|task|chat|command",
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation (1 sentence)",
  "requires_decomposition": true|false,
  "is_simple_query": true|false
}}"""
        
        return prompt
    
    def _parse_classification_result(self, llm_json: Dict) -> Optional[IntentResult]:
        """Parse LLM classification response into IntentResult"""
        
        try:
            intent_str = llm_json.get("intent", "unclear").lower()
            
            # Map string to enum
            intent_map = {
                "question": IntentType.QUESTION,
                "task": IntentType.TASK,
                "chat": IntentType.CHAT,
                "command": IntentType.COMMAND
            }
            
            intent_type = intent_map.get(intent_str, IntentType.UNCLEAR)
            
            # Determine suggested handler
            handler_map = {
                IntentType.QUESTION: "question",
                IntentType.TASK: "task",
                IntentType.CHAT: "chat",
                IntentType.COMMAND: "command",
                IntentType.UNCLEAR: "chat"
            }
            
            return IntentResult(
                intent_type=intent_type,
                confidence=llm_json.get("confidence", 0.5),
                reasoning=llm_json.get("reasoning", "No reasoning provided"),
                requires_decomposition=llm_json.get("requires_decomposition", False),
                is_simple_query=llm_json.get("is_simple_query", False),
                suggested_handler=handler_map[intent_type]
            )
            
        except Exception as e:
            self.core._log("INTENT", f"⚠️ Error parsing classification: {e}")
            return None
    
    # ==================== ROUTING ====================
    
    def get_handler_for_intent(self, intent_result: IntentResult) -> str:
        """
        Determine which handler should process this intent
        
        Args:
            intent_result: Classification result
            
        Returns:
            Handler name (method name in JarvisCore)
        """
        
        # Use suggested handler from classification
        handler = intent_result.suggested_handler or "chat"
        
        # Log routing decision
        self.core._log(
            "INTENT",
            f"Routing to '{handler}' handler (confidence: {intent_result.confidence:.2f})"
        )
        
        return handler
    
    # ==================== STATISTICS & HISTORY ====================
    
    def _update_stats(self, result: IntentResult):
        """Update classification statistics"""
        
        self.stats["total_classifications"] += 1
        
        intent_name = result.intent_type.value
        if intent_name not in self.stats["by_intent"]:
            self.stats["by_intent"][intent_name] = 0
        self.stats["by_intent"][intent_name] += 1
        
        if result.confidence >= 0.8:
            self.stats["high_confidence"] += 1
        elif result.confidence < 0.5:
            self.stats["low_confidence"] += 1
        
        # Store in history (keep last 100)
        self.classification_history.append({
            "timestamp": self.core._get_timestamp() if hasattr(self.core, '_get_timestamp') else "unknown",
            "intent": intent_name,
            "confidence": result.confidence,
            "reasoning": result.reasoning
        })
        
        if len(self.classification_history) > 100:
            self.classification_history = self.classification_history[-100:]
    
    def get_stats(self) -> Dict:
        """Get classification statistics"""
        
        total = self.stats["total_classifications"]
        if total == 0:
            return {"error": "No classifications yet"}
        
        return {
            "total_classifications": total,
            "by_intent": self.stats["by_intent"],
            "high_confidence_rate": self.stats["high_confidence"] / total,
            "low_confidence_rate": self.stats["low_confidence"] / total,
            "avg_confidence": sum(
                h["confidence"] for h in self.classification_history
            ) / len(self.classification_history) if self.classification_history else 0
        }
    
    def get_recent_history(self, limit: int = 10) -> list:
        """Get recent classification history"""
        return self.classification_history[-limit:]
    
    # ==================== CONFIDENCE HELPERS ====================
    
    def is_confident(self, result: IntentResult, threshold: float = 0.7) -> bool:
        """Check if classification confidence is above threshold"""
        return result.confidence >= threshold
    
    def needs_clarification(self, result: IntentResult) -> bool:
        """Check if user input needs clarification"""
        return (
            result.intent_type == IntentType.UNCLEAR or
            result.confidence < 0.5
        )
    
    def suggest_clarification_question(self, result: IntentResult) -> str:
        """Generate a clarification question for unclear intents"""
        
        if result.confidence < 0.5:
            return "I'm not quite sure what you'd like me to do. Could you rephrase that?"
        
        if result.intent_type == IntentType.UNCLEAR:
            return "I didn't quite understand. Are you asking a question, or would you like me to help with a task?"
        
        return "Could you provide more details about what you need?"