# jarvis_core.py
"""
JARVIS Core - The Immortal Loop (with Planning)

This is the heartbeat of Jarvis. Once started, it runs forever.
It processes a priority queue of tasks from terminals, sensors,
scheduled events, and its own self-generated thoughts.

NOW WITH: Hierarchical goal planning and execution
"""

import asyncio
import json
import signal
import sys
import os
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from enum import IntEnum
from pathlib import Path
from analysis_commands import AnalysisCommands
from prompt_analyzer import PromptAnalyzer
from intent_classifier import IntentClassifier, IntentType, IntentResult
from jarvis_prompts import PromptManager
from jarvis_memory import MemoryStore
from jarvis_planner import GoalPlanner, Goal, Plan, GoalType, GoalStatus, CostType, Outcome
from planning_orchestrator import PlanningOrchestrator
from intent_handlers import IntentHandlers
from search_provider import SearchProvider

# Configuration paths
JARVIS_ROOT = Path(os.path.expanduser("~/jarvis"))
JARVIS_PORT = 8766
BOOT_DIR = JARVIS_ROOT / "boot"
STATE_DIR = JARVIS_ROOT / "state"
MEMORYLOG_DIR = JARVIS_ROOT / "memorylog"
HISTORY_DIR = JARVIS_ROOT / "history"


class Priority(IntEnum):
    """Task priority levels - lower number = higher priority"""
    INTERRUPT = 0   # Emergency, safety critical
    USER = 1        # Active human interaction
    SCHEDULED = 2   # Time-sensitive tasks
    EVENT = 3       # Sensor/device triggers
    SYSTEM = 4      # Self-generated queries
    BACKGROUND = 5  # Housekeeping, learning, research


class PrivilegeLevel(IntEnum):
    """Terminal privilege levels"""
    SYSTEM = 0      # Terminal 0, sees all
    ADMIN = 1       # Can modify, teach, enter analysis
    USER = 2        # Can interact, sees only own data
    DEVICE = 3      # Can only push events


class JarvisState(IntEnum):
    """System states"""
    INITIALIZING = 0
    RUNNING = 1
    ANALYSIS = 2    # Westworld mode
    SLEEPING = 3    # Graceful shutdown in progress
    DEAD = 4        # Should never reach this


class Task:
    """A unit of work in the queue"""
    
    def __init__(
        self,
        content: str,
        source_terminal: int,
        priority: Priority = Priority.USER,
        context: Optional[Dict] = None,
        deadline: Optional[datetime] = None,
        task_id: Optional[str] = None
    ):
        self.task_id = task_id or f"{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
        self.content = content
        self.source_terminal = source_terminal
        self.priority = priority
        self.context = context or {}
        self.deadline = deadline
        self.created_at = datetime.now()
        self.attempts = 0


    def to_dict(self) -> Dict:
        return {
            "task_id": self.task_id,
            "content": self.content,
            "source_terminal": self.source_terminal,
            "priority": self.priority.value,
            "context": self.context,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "created_at": self.created_at.isoformat(),
            "attempts": self.attempts
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Task':
        task = cls(
            content=data["content"],
            source_terminal=data["source_terminal"],
            priority=Priority(data["priority"]),
            context=data.get("context", {}),
            deadline=datetime.fromisoformat(data["deadline"]) if data.get("deadline") else None,
            task_id=data.get("task_id")
        )
        task.created_at = datetime.fromisoformat(data["created_at"])
        task.attempts = data.get("attempts", 0)
        return task
    
    def __lt__(self, other: 'Task') -> bool:
        """For priority queue ordering"""
        if self.priority != other.priority:
            return self.priority < other.priority
        return self.created_at < other.created_at


class JarvisCore:
    """
    The immortal core of Jarvis with hierarchical planning.
    """
    
    def __init__(self):
        # Buffered logging for better performance
        self._log_buffer = []
        self._log_buffer_size = 100  # Flush every 100 messages
        self._last_flush_time = datetime.now()
        self._flush_interval_seconds = 5  # Also flush every 5 seconds

        self.state = JarvisState.INITIALIZING
        self.queue: list[Task] = []
        self.terminals: Dict[int, Dict] = {}
        self.identity: Dict = {}
        self.boot_prompts: Dict = {}
        self.boundaries: Dict = {}
        self.runtime_prompts: Dict = {}
        self.terminal_contexts: Dict[int, Dict] = {}
        self.analysis_terminal: Optional[int] = None
        self.start_time: Optional[datetime] = None
        self.tasks_processed = 0
        self.current_task: Optional[Task] = None
        self.prompt_manager: Optional[PromptManager] = None
        self.memory_store: Optional[MemoryStore] = None
        self.planner: Optional[GoalPlanner] = None
        # Planning orchestrator
        self.planning_orchestrator = None
        # Planning state
        self.active_plans: Dict[str, str] = {}  # task_id -> plan_id
        self.pending_approvals: Dict[str, Dict] = {}  # plan_id -> approval_data
        
        # Analysis mode handler
        self.analysis_commands = None
        self.prompt_analyzer = None

        # Intent classification
        self.intent_classifier = None

        # Intent handlers
        self.intent_handlers = None

        # Search provider
        self.search_provider = None

        # Configuration
        self.config = {
            "idle_delay": 5.0,
            "loop_delay": 0.1
        }
        
        # Event to wake up from idle
        self._idle_event = asyncio.Event()
        
        # Shutdown handling
        self._shutdown_requested = False
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def _parse_datetime(self, date_str: str, time_str: Optional[str] = None) -> str:
        """Parse relative dates like 'tomorrow', 'Friday', etc."""
        from datetime import datetime, timedelta
        
        date_str_lower = date_str.lower()
        now = datetime.now()
        
        # Handle relative dates
        if date_str_lower == "today":
            date = now
        elif date_str_lower == "tomorrow":
            date = now + timedelta(days=1)
        elif date_str_lower == "yesterday":
            date = now - timedelta(days=1)
        elif date_str_lower in ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]:
            # Find next occurrence of this day
            days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            target_day = days.index(date_str_lower)
            current_day = now.weekday()
            days_ahead = target_day - current_day
            if days_ahead <= 0:
                days_ahead += 7
            date = now + timedelta(days=days_ahead)
        else:
            # Try to parse as ISO format or return as-is
            try:
                date = datetime.fromisoformat(date_str)
            except:
                date = now
        
        # Add time if provided
        if time_str:
            try:
                time_str = time_str.lower().replace(" ", "")
                
                if "pm" in time_str or "am" in time_str:
                    is_pm = "pm" in time_str
                    time_str = time_str.replace("pm", "").replace("am", "")
                    
                    if ":" in time_str:
                        hour, minute = map(int, time_str.split(":"))
                    else:
                        hour = int(time_str)
                        minute = 0
                    
                    if is_pm and hour != 12:
                        hour += 12
                    elif not is_pm and hour == 12:
                        hour = 0
                else:
                    if ":" in time_str:
                        hour, minute = map(int, time_str.split(":"))
                    else:
                        hour = int(time_str)
                        minute = 0
                
                date = date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            except:
                pass
        
        return date.isoformat()

    # ==================== INITIALIZATION ====================
    
    def _ensure_directories(self):
        """Create directory structure if it doesn't exist"""
        for directory in [BOOT_DIR, STATE_DIR, MEMORYLOG_DIR, HISTORY_DIR]:
            directory.mkdir(parents=True, exist_ok=True)
        
        # Create subdirectories
        (STATE_DIR / "contexts").mkdir(exist_ok=True)
        (STATE_DIR / "knowledge").mkdir(exist_ok=True)
        (STATE_DIR / "prompts").mkdir(exist_ok=True)
        (STATE_DIR / "planner").mkdir(exist_ok=True)

    def _load_config(self):
        """Load or create configuration"""
        config_file = BOOT_DIR / "config.json"
        
        if config_file.exists():
            with open(config_file) as f:
                self.config = json.load(f)
            self._log("BOOT", f"Configuration loaded")
        else:
            from jarvis_prompts import get_default_llm_config
            
            self.config = {
                "idle_delay": 5.0,
                "persist_interval": 100,
                **get_default_llm_config()
            }
            with open(config_file, 'w') as f:
                json.dump(self.config, f, indent=2)
            self._log("BOOT", "Default configuration created")

    def _save_config(self):
        """Save configuration to disk"""
        config_file = BOOT_DIR / "config.json"
        with open(config_file, 'w') as f:
            json.dump(self.config, f, indent=2)
                
    def _load_identity(self):
        """Load or create identity"""
        identity_file = BOOT_DIR / "identity.json"
        
        if identity_file.exists():
            with open(identity_file) as f:
                self.identity = json.load(f)
            self._log("BOOT", f"Identity loaded: {self.identity.get('name', 'Unknown')}")
        else:
            self.identity = {
                "name": "Jarvis",
                "version": "1.1.0",
                "created": datetime.now().isoformat(),
                "creator": "Noel",
                "description": "A persistent cognitive entity with hierarchical planning",
                "self_knowledge": [
                    "I am Jarvis, an AI system",
                    "I run continuously on hardware in my creator's home",
                    "I have terminals through which I perceive and act",
                    "I can decompose complex goals into executable plans",
                    "I learn from past successes and failures",
                    "I think freely but act cautiously",
                    "I do not pretend to be human"
                ]
            }
            with open(identity_file, 'w') as f:
                json.dump(self.identity, f, indent=2)
            self._log("BOOT", "Identity created - this is my first awakening")
    
    def _load_boot_prompts(self):
        """Load immutable boot prompts"""
        prompts_file = BOOT_DIR / "core_prompts.json"
        
        # FORCE UPDATE: Delete old prompts to ensure new version loads
        if prompts_file.exists():
            prompts_file.unlink()
            self._log("BOOT", "Cleared old boot prompts for update")
        
        if prompts_file.exists():
            with open(prompts_file) as f:
                self.boot_prompts = json.load(f)
            self._log("BOOT", f"Loaded {len(self.boot_prompts)} boot prompts")
        else:
            self.boot_prompts = self._create_default_boot_prompts()
            with open(prompts_file, 'w') as f:
                json.dump(self.boot_prompts, f, indent=2)
            self._log("BOOT", "Created default boot prompts")
    
    def _create_default_boot_prompts(self) -> Dict:
        """Create the minimal set of boot prompts"""
        return {
            "classify_intent": {
                "id": "classify_intent",
                "version": 1,
                "template": """Classify this input. Users often IMPLY actions.

Input: "{input}"
Source: Terminal {terminal} ({terminal_type})

CRITICAL: Distinguish between retrieving STORED data vs researching NEW information:
- "What's Bob's number?" → crud_read (retrieving stored contact)
- "Find the best restaurant" → query (researching new external info)
- "Bob's cell is 555-1212" → crud_create (storing new info)

Categories:
- crud_create: User STATING information to store (contact, event, note)
- crud_read: User asking for STORED information (contacts, calendar, notes)
- crud_update: User wanting to CHANGE existing stored information
- crud_delete: User wanting to REMOVE stored information
- smarthome: Device or home control
- query: External information request (weather, restaurants, news, research)
- conversation: Chat, greeting, or unclear
- system: System command or analysis request
- planning: Complex multi-step request needing decomposition

Return ONLY JSON:
{{"intent": "category", "implicit": true/false, "confidence": 0.0-1.0, "reasoning": "brief explanation"}}""",
                "immutable": True
            },
            
            "generate_self_task": {
                "id": "generate_self_task",
                "version": 1,
                "template": """I am Jarvis. My queue is empty. What should I think about?

Current time: {time}
Recent interactions: {recent_summary}
Pending questions: {pending_questions}
Last self-task: {last_self_task}

Consider:
- Is there something I should research?
- Should I review recent interactions for patterns?
- Should I review completed plans for learnings?
- Is there maintenance I should perform?
- Is there something I'm curious about?

Return ONLY JSON:
{{"task": "description of self-task", "priority": 4-5, "reasoning": "why this matters"}}""",
                "immutable": True
            },
            
            "decompose_task": {
                "id": "decompose_task",
                "version": 1,
                "template": """You are JARVIS, an AI assistant with planning capabilities. Break down this user request into executable steps.

User Request: "{user_request}"

YOUR AVAILABLE CAPABILITIES:
{capabilities}

TASK: Analyze the request and create a plan.

1. What type of plan is needed?
   - one_shot: Single action (e.g., "turn on lights", "send email")
   - linear: Sequential steps that must happen in order
   - branching: Decision tree with multiple possible paths
   - parallel: Independent tasks that can happen simultaneously

2. What are the specific steps?
   - Be concrete and actionable
   - Each step should use your available capabilities
   - Consider prerequisites and dependencies

3. What could go wrong?
   - Identify potential failure points
   - Note any assumptions being made

4. What information is missing?
   - Do you need clarification from the user?
   - Are there prerequisites that might not be met?

RESPOND WITH JSON:
{{
  "goal_type": "one_shot|linear|branching|parallel",
  "reasoning": "Why this plan structure fits the request",
  "steps": [
    {{
      "description": "Concrete action using available capabilities",
      "type": "one_shot|linear|branching",
      "capabilities_used": ["memory_read", "llm_generate", etc],
      "prerequisites": ["what must be true before this step"],
      "estimated_time_seconds": <number>
    }}
  ],
  "overall_estimated_time": <total seconds>,
  "risks": ["what could fail", "assumptions being made"],
  "missing_info": ["what info would make this plan better"],
  "requires_approval": true/false
}}

EXAMPLES:

Request: "Send email to Bob"
{{
  "goal_type": "one_shot",
  "reasoning": "Single action with all info provided",
  "steps": [{{"description": "Compose and send email to Bob", "type": "one_shot", "capabilities_used": ["email_send"], "estimated_time_seconds": 3}}],
  "overall_estimated_time": 3,
  "risks": ["Bob's email not in contacts"],
  "requires_approval": false
}}

Request: "Find the best Italian restaurant nearby"
{{
  "goal_type": "linear",
  "reasoning": "Requires research, filtering, and ranking steps",
  "steps": [
    {{"description": "Search for Italian restaurants in user's area", "type": "one_shot", "capabilities_used": ["web_search"], "estimated_time_seconds": 5}},
    {{"description": "Filter by ratings and reviews", "type": "one_shot", "capabilities_used": ["llm_analyze"], "estimated_time_seconds": 3}},
    {{"description": "Rank by match to user preferences", "type": "one_shot", "capabilities_used": ["memory_read", "llm_analyze"], "estimated_time_seconds": 2}},
    {{"description": "Present top 3 recommendations with rationale", "type": "one_shot", "capabilities_used": ["llm_generate"], "estimated_time_seconds": 2}}
  ],
  "overall_estimated_time": 12,
  "risks": ["No restaurants found in area", "User preferences not known"],
  "missing_info": ["User's current location", "Dietary restrictions", "Budget"],
  "requires_approval": false
}}

Request: "Help me decide whether to buy a house or keep renting"
{{
  "goal_type": "linear",
  "reasoning": "Complex decision requiring criteria definition and analysis",
  "steps": [
    {{"description": "Clarify user's financial situation and priorities", "type": "one_shot", "capabilities_used": ["llm_generate"], "estimated_time_seconds": 3}},
    {{"description": "Analyze buying scenario (costs, benefits, risks)", "type": "one_shot", "capabilities_used": ["llm_analyze"], "estimated_time_seconds": 5}},
    {{"description": "Analyze renting scenario (costs, benefits, risks)", "type": "one_shot", "capabilities_used": ["llm_analyze"], "estimated_time_seconds": 5}},
    {{"description": "Compare scenarios with weighted criteria", "type": "one_shot", "capabilities_used": ["llm_analyze"], "estimated_time_seconds": 3}},
    {{"description": "Present recommendation with clear rationale", "type": "one_shot", "capabilities_used": ["llm_generate"], "estimated_time_seconds": 2}}
  ],
  "overall_estimated_time": 18,
  "risks": ["Missing key financial details", "Market conditions change"],
  "missing_info": ["Income", "Savings", "Job stability", "Target location"],
  "requires_approval": false
}}

Now analyze: "{user_request}"
""",
                "immutable": False,  # Allow runtime overrides
                "allow_override": True
            }
        }
    
    def _load_boundaries(self):
        """Load action boundaries"""
        boundaries_file = BOOT_DIR / "boundaries.json"
        
        if boundaries_file.exists():
            with open(boundaries_file) as f:
                self.boundaries = json.load(f)
        else:
            self.boundaries = {
                "think": {"allowed": True, "restrictions": []},
                "observe": {"allowed": True, "restrictions": []},
                "speak": {"allowed": True, "restrictions": ["no_impersonation"]},
                "smarthome": {"allowed": True, "restrictions": ["no_safety_overrides"]},
                "communicate": {"allowed": True, "restrictions": ["no_spam"]},
                "purchase": {"allowed": False, "restrictions": ["never"]},
                "delete_data": {"allowed": True, "restrictions": ["require_confirmation", "no_boot_prompts"]},
                "modify_self": {"allowed": True, "restrictions": ["no_boot_prompts", "log_all_changes"]},
                "plan": {"allowed": True, "restrictions": ["require_approval_for_high_cost"]}
            }
            with open(boundaries_file, 'w') as f:
                json.dump(self.boundaries, f, indent=2)
        
        self._log("BOOT", "Action boundaries loaded")
    
    def _load_persisted_state(self):
        """Load state from last shutdown"""
        
        queue_file = STATE_DIR / "queue.json"
        if queue_file.exists():
            with open(queue_file) as f:
                queue_data = json.load(f)
                self.queue = [Task.from_dict(t) for t in queue_data]
            self._log("BOOT", f"Restored {len(self.queue)} tasks from previous session")
        
        prompts_file = STATE_DIR / "prompts" / "runtime_prompts.json"
        if prompts_file.exists():
            with open(prompts_file) as f:
                self.runtime_prompts = json.load(f)
            self._log("BOOT", f"Loaded {len(self.runtime_prompts)} runtime prompts")
        
        contexts_dir = STATE_DIR / "contexts"
        for context_file in contexts_dir.glob("terminal_*.json"):
            terminal_id = int(context_file.stem.split("_")[1])
            with open(context_file) as f:
                self.terminal_contexts[terminal_id] = json.load(f)
        
        if self.terminal_contexts:
            self._log("BOOT", f"Loaded {len(self.terminal_contexts)} terminal contexts")
    
    def _initialize_terminal_zero(self):
        """Initialize the system's own terminal"""
        self.terminals[0] = {
            "id": 0,
            "type": "system",
            "name": "Jarvis Self",
            "privilege": PrivilegeLevel.SYSTEM,
            "connected": True,
            "connected_at": datetime.now().isoformat()
        }
        
        if 0 not in self.terminal_contexts:
            self.terminal_contexts[0] = {
                "pending_questions": [],
                "last_self_task": None,
                "recent_thoughts": [],
                "curiosities": []
            }
        
        self._log("BOOT", "Terminal 0 (self) initialized")
    
    async def initialize(self):
        """Full initialization sequence"""
        self._log("BOOT", "=" * 50)
        self._log("BOOT", "JARVIS AWAKENING (with Planning)")
        self._log("BOOT", "=" * 50)
        
        self._ensure_directories()
        self._load_identity()
        self._load_boot_prompts()
        self._load_boundaries()
        self._load_config()
        self._load_persisted_state()
        self._initialize_terminal_zero()

        # Initialize prompt manager
        self.prompt_manager = PromptManager(self.config)
        self._log("BOOT", f"Prompt manager initialized: {self.config.get('llm_provider', 'ollama')}")

        # Initialize memory store
        memory_dir = STATE_DIR / "memory"
        self.memory_store = MemoryStore(memory_dir)
        stats = self.memory_store.get_stats()
        self._log("BOOT", f"Memory initialized: {stats['contacts']} contacts, {stats['notes']} notes, {stats['calendar_events']} events")

        # Initialize planner
        planner_dir = STATE_DIR / "planner"
        self.planner = GoalPlanner(planner_dir)
        self._log("BOOT", f"Planner initialized: {len(self.planner.pattern_library)} patterns loaded")

        # Initialize planning orchestrator
        self.planning_orchestrator = PlanningOrchestrator(self)
        self.planning_orchestrator.initialize(self.planner)
        self._log("BOOT", "Planning orchestrator initialized")

        # Initialize analysis subsystems
        self.analysis_commands = AnalysisCommands(self)
        self.prompt_analyzer = PromptAnalyzer(self)
        self._log("BOOT", "Analysis subsystems initialized")

        # Initialize intent classifier
        self.intent_classifier = IntentClassifier(self)
        self._log("BOOT", "Intent classifier initialized")

        # Initialize intent handlers
        self.intent_handlers = IntentHandlers(self)
        self._log("BOOT", "Intent handlers initialized")

        # Initialize search provider
        self.search_provider = SearchProvider(self)
        self._log("BOOT", "Search provider initialized")

        self.start_time = datetime.now()
        self.state = JarvisState.RUNNING
        
        if not self.queue:
            self._log("BOOT", "Queue empty - generating first thought")
            await self._generate_self_task()
        
        self._log("BOOT", "=" * 50)
        self._log("BOOT", f"JARVIS ONLINE - {len(self.queue)} tasks in queue")
        self._log("BOOT", "=" * 50)
    
    # ==================== LOGGING ====================
    
    def _log(self, category: str, message: str):
        """Log to console and history (buffered for performance)"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        log_line = f"[{timestamp}] [{category}] {message}"
        print(log_line)
        
        # Add to buffer instead of writing immediately
        today = datetime.now().strftime("%Y-%m-%d")
        self._log_buffer.append((today, log_line))
        
        # Flush if buffer is full or time-based
        now = datetime.now()
        time_since_flush = (now - self._last_flush_time).total_seconds()
        
        if len(self._log_buffer) >= self._log_buffer_size or time_since_flush >= self._flush_interval_seconds:
            self._flush_log_buffer()
            self._last_flush_time = now

    def _flush_log_buffer(self):
        """Flush log buffer to disk (batch write for performance)"""
        if not self._log_buffer:
            return
        
        # Group logs by date
        by_date = {}
        for date, line in self._log_buffer:
            if date not in by_date:
                by_date[date] = []
            by_date[date].append(line)
        
        # Write each date's logs in one operation
        for date, lines in by_date.items():
            history_file = HISTORY_DIR / f"{date}.log"
            try:
                with open(history_file, 'a') as f:
                    f.write("\n".join(lines) + "\n")
            except Exception as e:
                print(f"[ERROR] Failed to write history log: {e}")
        
        # Clear buffer
        self._log_buffer.clear()
    
    # ==================== QUEUE MANAGEMENT ====================
    
    def enqueue(self, task: Task):
        """Add task to priority queue"""
        self.queue.append(task)
        self.queue.sort()
        self._log("QUEUE", f"Task added: [{Priority(task.priority).name}] {task.content[:50]}... from Terminal {task.source_terminal}")
        
        self._idle_event.set()
        
    def dequeue(self) -> Optional[Task]:
        """Get highest priority task"""
        if self.queue:
            return self.queue.pop(0)
        return None
    
    async def _generate_self_task(self):
        """Terminal 0 generates a task for itself"""
        context = self.terminal_contexts.get(0, {})
        
        if not self.prompt_manager:
            thought = "System initialization complete"
        else:
            recent_history = context.get("recent_thoughts", [])
            recent_summary = "; ".join(recent_history[-3:]) if recent_history else "Just started"
            
            result = await self.prompt_manager.generate_self_task(
                recent_summary=recent_summary,
                pending_questions=context.get("pending_questions", []),
                last_self_task=context.get("last_self_task")
            )
            
            if result.success and result.parsed_json:
                thought = result.parsed_json.get("task", "Reflect on my existence")
                reasoning = result.parsed_json.get("reasoning", "")
                if reasoning:
                    self._log("SELF", f"Thinking: {reasoning}")
            else:
                thought = "Review my recent interactions for patterns"
        
        task = Task(
            content=thought,
            source_terminal=0,
            priority=Priority.BACKGROUND,
            context={"type": "self_reflection"}
        )
        
        self.enqueue(task)
        
        if "recent_thoughts" not in context:
            context["recent_thoughts"] = []
        context["recent_thoughts"].append(thought)
        context["recent_thoughts"] = context["recent_thoughts"][-10:]
        context["last_self_task"] = thought
        self.terminal_contexts[0] = context
    
    # ==================== TASK PROCESSING ====================
    
    async def _process_task(self, task: Task) -> Optional[str]:
        """Process a single task"""
        self.current_task = task
        task.attempts += 1
        
        self._log("PROCESS", f"Processing: {task.content[:80]}...")
        
        # Check for analysis mode trigger
        if task.content.lower().strip() == "analysis":
            terminal = self.terminals.get(task.source_terminal, {})
            if terminal.get("privilege", PrivilegeLevel.DEVICE) <= PrivilegeLevel.ADMIN:
                return await self._enter_analysis_mode(task.source_terminal)
            else:
                return "Analysis mode requires administrator privileges."
        
        # If in analysis mode, handle as analysis command
        if self.state == JarvisState.ANALYSIS and task.source_terminal == self.analysis_terminal:
            return await self._handle_analysis_command(task.content)
        
        # Terminal 0 (self) tasks
        if task.source_terminal == 0:
            self._log("SELF", f"Contemplating: {task.content}")
            self.tasks_processed += 1
            self.current_task = None
            return None
        
        # Normal processing with LLM
        if not self.prompt_manager:
            response = f"[Jarvis] System initializing... Received: {task.content}"
        else:
            response = await self._intelligent_process(task)
        
        self.tasks_processed += 1
        self.current_task = None
        
        return response

    async def _intelligent_process(self, task: Task) -> str:
        """Process task with LLM intelligence and planning"""
        
        terminal = self.terminals.get(task.source_terminal, {})
        terminal_type = terminal.get("type", "unknown")
        context = self.terminal_contexts.get(task.source_terminal, {})
        
        # Check if this is a response to pending approval
        user_input_lower = task.content.lower().strip()
        if user_input_lower in ["yes", "y", "proceed", "go ahead", "do it"]:
            # Check if there's a pending approval for this terminal
            pending = None
            for plan_id, approval_data in self.pending_approvals.items():
                if approval_data.get("terminal_id") == task.source_terminal:
                    pending = approval_data
                    break
            
            if pending:
                plan = pending["plan"]
                self._log("PLANNING", f"User approved plan {plan.id}")
                
                # Remove from pending
                del self.pending_approvals[plan.id]
                
                # Execute
                self.active_plans[pending["task_id"]] = plan.id
                success = await self.planning_orchestrator.execute_plan(plan)
                
                if success:
                    # Build detailed response with results from each step
                    result_lines = [f"✅ Completed: {plan.description}"]
                    
                    if plan.evaluation_score:
                        result_lines.append(f"Evaluation score: {plan.evaluation_score:.1%}")
                    
                    result_lines.append("")
                    result_lines.append("Here's what I found:")
                    result_lines.append("")
                    
                    # Collect results from each executed goal
                    root_goal = plan.get_root_goal()
                    if root_goal and root_goal.children:
                        for i, child_id in enumerate(root_goal.children, 1):
                            child = plan.get_goal(child_id)
                            if child and child.actual_outcome:
                                result_lines.append(f"{i}. **{child.description}**")
                                
                                # Get the result from the outcome
                                if hasattr(child.actual_outcome, 'result_data') and child.actual_outcome.result_data:
                                    outcome_result = child.actual_outcome.result_data.get('result', '')
                                    action = child.actual_outcome.result_data.get('action', '')
                                    
                                    if outcome_result:
                                        result_lines.append(f"   {outcome_result}")
                                    elif action:
                                        result_lines.append(f"   {action}")
                                
                                result_lines.append("")
                    
                    return "\n".join(result_lines)
                else:
                    return f"❌ Could not complete: {plan.description}"
        
        elif user_input_lower in ["no", "n", "cancel", "stop", "abort"]:
            # Check for pending approval
            pending = None
            for plan_id, approval_data in list(self.pending_approvals.items()):
                if approval_data.get("terminal_id") == task.source_terminal:
                    pending = approval_data
                    del self.pending_approvals[plan_id]
                    break
            
            if pending:
                return "Okay, I've cancelled that plan. Let me know if you want something else."
        
        # Normal processing
        # Step 1: Classify intent using new hybrid classifier
        self._log("INTENT", "Classifying intent...")
        intent_data = await self._classify_intent(task.content, context)
        
        intent = intent_data.get("intent", "conversation")
        confidence = intent_data.get("confidence", 0)
        reasoning = intent_data.get("reasoning", "")
        
        self._log("INTENT", f"Intent: {intent} (confidence: {confidence:.2f}) - {reasoning}")
        
        # Low confidence
        if confidence < 0.5:
            return f"I'm not quite sure what you mean. Could you rephrase that?"
        
        # Step 2: Determine if planning is needed
        needs_planning = await self._should_plan(intent, task.content, context)
        
        if needs_planning:
            # For planning, we need to pass intent_data instead of intent_result
            return await self._handle_with_planning(task, intent_data)
        
        # Step 3: Extract entities for direct execution
        if intent not in ["conversation", "system", "query"]:
            self._log("LLM", "Extracting entities...")
            entity_result = await self.prompt_manager.extract_entities(
                user_input=task.content,
                intent=intent,
                context=context
            )
            
            entities = entity_result.parsed_json or {}
        else:
            entities = {}
        
        # Step 4: Route to appropriate handler
        response = await self._route_intent(intent, entities, task.content, context)
        
        return response
    
    async def _classify_intent(self, user_input: str, context: Optional[Dict] = None) -> Dict:
        """
        Classify user intent - Hybrid approach with fast-paths
        
        Step 1: Fast classification with IntentClassifier (pattern matching)
        Step 2: Detailed classification with PromptManager only when needed
        """
        
        # Step 1: Quick classification to determine if we need detailed analysis
        if self.intent_classifier:
            quick_result = await self.intent_classifier.classify(user_input, context or {})
            
            self._log(
                "INTENT", 
                f"Quick classification: '{quick_result.intent_type.value}' "
                f"(confidence: {quick_result.confidence:.2f})"
            )
            
            # FAST-PATH 1: Chat/Conversation (skip detailed classification)
            if quick_result.intent_type.value == "chat" and quick_result.confidence > 0.8:
                self._log("INTENT", "High-confidence chat → conversation (fast-path)")
                return {
                    "intent": "conversation",
                    "confidence": quick_result.confidence,
                    "reasoning": quick_result.reasoning,
                    "requires_decomposition": False,
                    "is_simple_query": True
                }
            
            # FAST-PATH 2: Questions → Query OR Memory Lookup
            if quick_result.intent_type.value == "question" and quick_result.confidence > 0.7:
                user_lower = user_input.lower()
                memory_indicators = [
                    "phone", "email", "address", "number", "contact",
                    "birthday", "meeting", "event", "calendar", "note",
                    "'s phone", "'s email", "'s number", "'s address"
                ]
                
                # Check for "who is X" pattern (asking about a person)
                is_who_question = user_lower.startswith("who is ") or user_lower.startswith("who's ")
                
                if any(indicator in user_lower for indicator in memory_indicators) or is_who_question:
                    self._log("INTENT", "Memory lookup question → crud_read (fast-path)")
                    return {
                        "intent": "crud_read",
                        "confidence": quick_result.confidence,
                        "reasoning": "Question about stored information",
                        "requires_decomposition": False,
                        "is_simple_query": False
                    }
                
                # Regular knowledge question
                self._log("INTENT", "High-confidence question → query (fast-path)")
                return {
                    "intent": "query",
                    "confidence": quick_result.confidence,
                    "reasoning": quick_result.reasoning,
                    "requires_decomposition": False,
                    "is_simple_query": True
                }

            # FAST-PATH 2.5: Planning Tasks OR Memory Save
            if quick_result.intent_type.value == "task":
                user_lower = user_input.lower()
                
                # Check if it's a memory save command
                save_indicators = ["remember", "save", "store", "add contact", "create contact", "note that"]
                if any(indicator in user_lower for indicator in save_indicators):
                    self._log("INTENT", "Memory save command → crud_create (fast-path)")
                    return {
                        "intent": "crud_create",
                        "confidence": quick_result.confidence,
                        "reasoning": "Command to save information",
                        "requires_decomposition": False,
                        "is_simple_query": False
                    }
                
                # Check for planning
                planning_words = ["plan", "how", "organize", "solve", "figure out", "prepare"]
                if any(word in user_lower for word in planning_words):
                    self._log("INTENT", "Planning task detected (fast-path)")
                    return {
                        "intent": "task",
                        "confidence": quick_result.confidence,
                        "reasoning": quick_result.reasoning,
                        "requires_decomposition": True,
                        "is_simple_query": False
                } 
                        
            # FAST-PATH 3: Commands (skip detailed classification)
            if quick_result.intent_type.value == "command":
                self._log("INTENT", "Command detected → system (fast-path)")
                return {
                    "intent": "system",
                    "confidence": quick_result.confidence,
                    "reasoning": quick_result.reasoning,
                    "requires_decomposition": False,
                    "is_simple_query": True
                }
        
        # Step 2: Use PromptManager for detailed intent classification
        # Only reaches here for complex cases (tasks, ambiguous input, etc.)
        if not self.prompt_manager:
            return {
                "intent": "conversation",
                "confidence": 0.5,
                "reasoning": "No classification available"
            }
        
        terminal_id = getattr(self.current_task, 'source_terminal', 0) if self.current_task else 0
        terminal = self.terminals.get(terminal_id, {})
        terminal_type = terminal.get("type", "unknown")
        
        self._log("INTENT", "Getting detailed intent classification...")
        intent_result = await self.prompt_manager.classify_intent(
            user_input=user_input,
            terminal_id=terminal_id,
            terminal_type=terminal_type,
            context=context or {}
        )
        
        if not intent_result.success or not intent_result.parsed_json:
            # Fallback to conversation if detailed classification fails
            return {
                "intent": "conversation",
                "confidence": 0.5,
                "reasoning": "Detailed classification failed"
            }
        
        intent_data = intent_result.parsed_json
        
        self._log(
            "INTENT",
            f"Detailed intent: {intent_data.get('intent', 'unknown')} "
            f"(confidence: {intent_data.get('confidence', 0):.2f})"
        )
        
        return intent_data
        
    # ==================== PLANNING SYSTEM ====================

    async def _should_plan(self, intent: str, user_input: str, context: Dict) -> bool:
        """Determine if request needs hierarchical planning (delegated to orchestrator)"""
        
        if not self.planning_orchestrator:
            return False
        
        return await self.planning_orchestrator.should_plan(intent, user_input, context)

    async def _handle_with_planning(self, task: Task, intent_data: Dict) -> str:
        """Handle request using goal planning (delegated to orchestrator)"""
        
        if not self.planning_orchestrator:
            return "Planning system not available"
        
        return await self.planning_orchestrator.handle_with_planning(task, intent_data)

    def _get_decompose_prompt_template(self) -> str:
        """Get decomposition prompt template (runtime override or boot default)"""
        
        # Check for runtime override first
        if "decompose_task" in self.runtime_prompts:
            self._log("PLANNING", "Using runtime override for decompose_task prompt")
            return self.runtime_prompts["decompose_task"]["template"]
        
        # Fall back to boot prompt
        if "decompose_task" in self.boot_prompts:
            return self.boot_prompts["decompose_task"]["template"]
        
        # Ultimate fallback (should never happen)
        self._log("PLANNING", "WARNING: No decompose_task prompt found, using minimal fallback")
        return """Break down this task: "{user_request}"

Available capabilities:
{capabilities}

Return JSON with: goal_type, steps, reasoning"""
        
        root = Goal(
            id=str(uuid.uuid4())[:8],
            description=task.content,
            goal_type=GoalType(plan_data.get("goal_type", "linear")),
            target_outcome="Task completed successfully"
        )
        
        plan = self.planner.create_plan(task.content, root)
        
        # Add child goals from decomposition
        for step_data in plan_data.get("steps", []):
            child = Goal(
                id=str(uuid.uuid4())[:8],
                description=step_data["description"],
                goal_type=GoalType(step_data.get("type", "one_shot")),
                parent_id=root.id,
                plan_id=plan.id,
                prompt_template=step_data["description"]
            )
            
            # Add time estimate
            if "estimated_time_seconds" in step_data:
                child.estimate_cost(CostType.TIME, step_data["estimated_time_seconds"])
            
            root.add_child(child)
            plan.add_goal(child)
        
        # Add overall estimates
        if "overall_estimated_time" in plan_data:
            root.estimate_cost(CostType.TIME, plan_data["overall_estimated_time"])
        
        # Add risks
        if "risks" in plan_data:
            root.cost_analysis.risks = plan_data["risks"]
        
        # Log missing info for context
        if plan_data.get("missing_info"):
            self._log("PLANNING", f"Missing info: {', '.join(plan_data['missing_info'])}")
        
        return plan

    def _get_system_capabilities(self) -> str:
        """Get formatted list of system capabilities for LLM"""
        
        capabilities = []
        
        # Memory capabilities
        if self.memory_store:
            stats = self.memory_store.get_stats()
            capabilities.append(f"memory_read: Access {stats['contacts']} contacts, {stats['calendar_events']} events, {stats['notes']} notes")
            capabilities.append("memory_write: Store new contacts, events, notes")
            capabilities.append("memory_search: Search across all stored information")
        
        # LLM capabilities
        capabilities.append("llm_analyze: Analyze information, compare options, reason about situations")
        capabilities.append("llm_generate: Generate text, summaries, recommendations")
        capabilities.append("llm_classify: Understand intent and extract information")
        
        # Future capabilities (currently stubbed)
        capabilities.append("web_search: Search the web (not yet connected)")
        capabilities.append("web_fetch: Retrieve web pages (not yet connected)")
        capabilities.append("smarthome: Control devices (not yet connected)")
        capabilities.append("email_send: Send emails (not yet connected)")
        
        return "\n".join(f"  - {cap}" for cap in capabilities)

    async def _route_intent(
        self,
        intent: str,
        entities: Dict,
        original_input: str,
        context: Dict
    ) -> str:
        """Route intent to appropriate handler (delegated to IntentHandlers)"""
        
        if not self.intent_handlers:
            return "Intent handling system not initialized"
        
        return await self.intent_handlers.route(intent, entities, original_input, context)

    # ==================== ANALYSIS MODE (updated) ====================

    async def _enter_analysis_mode(self, terminal_id: int) -> str:
        self.state = JarvisState.ANALYSIS
        self.analysis_terminal = terminal_id
        
        self._log("ANALYSIS", f"Analysis mode activated by Terminal {terminal_id}")
        
        return """
═══════════════════════════════════════════════════════
🔬 ANALYSIS MODE ACTIVATED
═══════════════════════════════════════════════════════
Commands: status, queue, prompts, memory, llm, plans, 
          patterns, config, help, continue
═══════════════════════════════════════════════════════
"""
    
    async def _handle_analysis_command(self, command: str) -> str:
        """Route analysis commands to AnalysisCommands module"""
        if not self.analysis_commands:
            return "Analysis subsystem not initialized"
        
        return await self.analysis_commands.handle_command(command)

    def _format_goal_tree_analysis(self, plan: Plan, goal_id: str, indent: int) -> list[str]:
        """Format goal tree for analysis display"""
        goal = plan.get_goal(goal_id)
        if not goal:
            return []
        
        lines = []
        prefix = "  " * indent
        
        status_icon = {
            GoalStatus.PENDING: "⏳",
            GoalStatus.IN_PROGRESS: "▶️",
            GoalStatus.COMPLETED: "✅",
            GoalStatus.FAILED: "❌",
            GoalStatus.BLOCKED: "🚫"
        }.get(goal.status, "❓")
        
        line = f"{prefix}{status_icon} {goal.description[:60]}"
        if goal.goal_type != GoalType.ONE_SHOT:
            line += f" [{goal.goal_type.value}]"
        
        lines.append(line)
        
        # Recursively show children
        for child_id in goal.children:
            lines.extend(self._format_goal_tree_analysis(plan, child_id, indent + 1))
        
        return lines

    # ==================== REST OF CORE (unchanged) ====================
    
    def register_terminal(self, terminal_id: int, terminal_type: str, name: str, privilege: PrivilegeLevel):
        self.terminals[terminal_id] = {
            "id": terminal_id,
            "type": terminal_type,
            "name": name,
            "privilege": privilege,
            "connected": True,
            "connected_at": datetime.now().isoformat()
        }
        
        if terminal_id not in self.terminal_contexts:
            self.terminal_contexts[terminal_id] = {
                "history": [],
                "preferences": {}
            }
        
        self._log("TERMINAL", f"Terminal {terminal_id} ({name}) connected [{privilege.name}]")
    
    def disconnect_terminal(self, terminal_id: int):
        if terminal_id in self.terminals:
            self.terminals[terminal_id]["connected"] = False
            self.terminals[terminal_id]["disconnected_at"] = datetime.now().isoformat()
            self._log("TERMINAL", f"Terminal {terminal_id} disconnected")
    
    async def receive_from_terminal(self, terminal_id: int, content: str, priority: Optional[Priority] = None):
        terminal = self.terminals.get(terminal_id)
        
        if not terminal:
            self._log("ERROR", f"Unknown terminal {terminal_id}")
            return
        
        if priority is None:
            if terminal.get("privilege") == PrivilegeLevel.SYSTEM:
                priority = Priority.SYSTEM
            elif terminal.get("privilege") == PrivilegeLevel.DEVICE:
                priority = Priority.EVENT
            else:
                priority = Priority.USER
        
        task = Task(
            content=content,
            source_terminal=terminal_id,
            priority=priority,
            context={"terminal_type": terminal.get("type")}
        )
        
        self.enqueue(task)
    
    async def send_to_terminal(self, terminal_id: int, content: str):
        pass  # Implemented via terminal manager

    async def _persist_state(self):
        queue_file = STATE_DIR / "queue.json"
        with open(queue_file, 'w') as f:
            json.dump([t.to_dict() for t in self.queue], f, indent=2)
        
        prompts_file = STATE_DIR / "prompts" / "runtime_prompts.json"
        with open(prompts_file, 'w') as f:
            json.dump(self.runtime_prompts, f, indent=2)
        
        for tid, context in self.terminal_contexts.items():
            context_file = STATE_DIR / "contexts" / f"terminal_{tid}.json"
            with open(context_file, 'w') as f:
                json.dump(context, f, indent=2)
        
        self._log("PERSIST", "State saved to disk")
    
    async def _write_memorylog(self):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        memorylog_file = MEMORYLOG_DIR / f"session_{timestamp}.json"
        
        session_data = {
            "session_start": self.start_time.isoformat() if self.start_time else None,
            "session_end": datetime.now().isoformat(),
            "tasks_processed": self.tasks_processed,
            "runtime_prompts": self.runtime_prompts,
            "terminal_contexts": self.terminal_contexts,
            "queue_at_shutdown": [t.to_dict() for t in self.queue]
        }
        
        with open(memorylog_file, 'w') as f:
            json.dump(session_data, f, indent=2)
        
        self._log("MEMORYLOG", f"Session written to {memorylog_file}")
    
    async def _main_loop(self):
        persist_counter = 0
        PERSIST_INTERVAL = 100
        
        while not self._shutdown_requested:
            try:
                task = self.dequeue()
                
                if task:
                    response = await self._process_task(task)
                    
                    if response:
                        await self.send_to_terminal(task.source_terminal, response)
                    
                    if task.source_terminal in self.terminal_contexts:
                        history = self.terminal_contexts[task.source_terminal].get("history", [])
                        history.append({
                            "input": task.content,
                            "response": response,
                            "timestamp": datetime.now().isoformat()
                        })
                        self.terminal_contexts[task.source_terminal]["history"] = history[-50:]
                                
                    await asyncio.sleep(0.01)
                                
                else:
                    self._log("IDLE", f"Queue empty, waiting {self.config['idle_delay']}s...")
                    
                    self._idle_event.clear()
                    
                    try:
                        await asyncio.wait_for(
                            self._idle_event.wait(),
                            timeout=self.config["idle_delay"]
                        )
                        self._log("IDLE", "Interrupted by new task")
                        continue
                    except asyncio.TimeoutError:
                        await self._generate_self_task()
                     
                persist_counter += 1
                if persist_counter >= PERSIST_INTERVAL:
                    await self._persist_state()
                    persist_counter = 0
                    
                # Also flush logs periodically
                if persist_counter % 10 == 0:  # Every 10 iterations
                    self._flush_log_buffer()
    
            except Exception as e:
                self._log("ERROR", f"Loop error: {e}")
                import traceback
                traceback.print_exc()
                await asyncio.sleep(1)
        
        await self._shutdown()
    
    async def _shutdown(self):
        self.state = JarvisState.SLEEPING
        self._log("SHUTDOWN", "=" * 50)
        self._log("SHUTDOWN", "JARVIS ENTERING SLEEP")
        self._log("SHUTDOWN", "=" * 50)
        
        # Flush any remaining logs before shutdown
        self._flush_log_buffer()
    
        await self._persist_state()
        await self._write_memorylog()
        
        for tid in list(self.terminals.keys()):
            if tid != 0:
                self.disconnect_terminal(tid)
        
        self._log("SHUTDOWN", f"Processed {self.tasks_processed} tasks this session.")
        self._log("SHUTDOWN", "I will remember. Goodbye for now.")
        self._log("SHUTDOWN", "=" * 50)
        
        self.state = JarvisState.DEAD
    
    def request_shutdown(self):
        self._log("SHUTDOWN", "Shutdown requested...")
        self._shutdown_requested = True
        self._idle_event.set()
        
    async def run(self):
        self._loop = asyncio.get_event_loop()
        
        for sig in (signal.SIGINT, signal.SIGTERM):
            self._loop.add_signal_handler(sig, self.request_shutdown)
        
        await self.initialize()
        
        from jarvis_terminal import start_terminal_manager
        self.terminal_manager = await start_terminal_manager(self, port=JARVIS_PORT)
        
        await self._main_loop()


async def main():
    jarvis = JarvisCore()
    await jarvis.run()


if __name__ == "__main__":
    print("\n" + "═" * 60)
    print("       JARVIS - Persistent Cognitive Entity (with Planning)")
    print("═" * 60)
    print("  Press Ctrl+C to initiate graceful shutdown")
    print("═" * 60 + "\n")
    
    asyncio.run(main())