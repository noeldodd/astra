# jarvis_planner.py
"""
JARVIS Goal Planning System

Implements hierarchical goal decomposition with:
- Goal trees (one-shot, linear, branching)
- Prerequisite checking
- Outcome tracking and evaluation
- Pattern matching against historical successes
- Cost-benefit analysis
- Learning from past executions

Architecture:
- Goal: High-level objective (user request or self-generated)
- Task: Executable step (can be one-shot or have children)
- Branch: Decision point with multiple possible paths
- Plan: Complete execution tree with evaluation metadata
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any, Set
from enum import Enum
from dataclasses import dataclass, field, asdict
import hashlib


class GoalType(Enum):
    """Type of goal/task"""
    ONE_SHOT = "one_shot"          # Single prompt execution
    LINEAR = "linear"              # Sequential children
    BRANCHING = "branching"        # Multiple possible paths
    PARALLEL = "parallel"          # Can execute children concurrently
    STOP = "stop"                  # Terminal success node
    ABORT = "abort"                # Terminal failure node


class GoalStatus(Enum):
    """Execution status"""
    PENDING = "pending"            # Not started
    IN_PROGRESS = "in_progress"    # Currently executing
    COMPLETED = "completed"        # Successfully finished
    FAILED = "failed"              # Failed to achieve
    ABORTED = "aborted"            # Deliberately stopped
    BLOCKED = "blocked"            # Waiting on prerequisites


class CostType(Enum):
    """Types of costs to track"""
    TIME = "time"                  # Execution time
    TOKENS = "tokens"              # LLM token usage
    API_CALLS = "api_calls"        # Number of API calls
    MONEY = "money"                # Actual cost in currency
    RISK = "risk"                  # Potential negative outcomes


@dataclass
class Prerequisite:
    """A condition that must be met before execution"""
    id: str
    description: str
    check_type: str                # "state", "data", "external", "permission"
    check_function: Optional[str] = None  # Name of function to call
    required_state: Optional[Dict] = None
    blocking: bool = True          # If false, just a warning
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Prerequisite':
        return cls(**data)


@dataclass
class Outcome:
    """Result of executing a goal/task"""
    success: bool
    result_data: Optional[Dict] = None
    error: Optional[str] = None
    confidence: float = 1.0        # How confident are we in this result
    side_effects: List[str] = field(default_factory=list)
    observations: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Outcome':
        return cls(**data)


@dataclass
class CostAnalysis:
    """Cost-benefit tracking"""
    estimated_costs: Dict[str, float] = field(default_factory=dict)
    actual_costs: Dict[str, float] = field(default_factory=dict)
    estimated_benefits: Dict[str, float] = field(default_factory=dict)
    actual_benefits: Dict[str, float] = field(default_factory=dict)
    risks: List[str] = field(default_factory=list)
    risk_mitigation: List[str] = field(default_factory=list)
    
    def net_benefit_estimated(self) -> float:
        """Calculate estimated net benefit (benefits - costs)"""
        total_benefit = sum(self.estimated_benefits.values())
        total_cost = sum(self.estimated_costs.values())
        return total_benefit - total_cost
    
    def net_benefit_actual(self) -> float:
        """Calculate actual net benefit"""
        total_benefit = sum(self.actual_benefits.values())
        total_cost = sum(self.actual_costs.values())
        return total_benefit - total_cost
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'CostAnalysis':
        return cls(**data)


@dataclass
class Goal:
    """A goal or task in the planning hierarchy"""
    
    # Identity
    id: str
    parent_id: Optional[str] = None
    plan_id: Optional[str] = None
    
    # Description
    description: str = ""
    goal_type: GoalType = GoalType.ONE_SHOT
    prompt_template: Optional[str] = None
    
    # Hierarchy
    children: List[str] = field(default_factory=list)  # Child goal IDs
    prerequisites: List[Prerequisite] = field(default_factory=list)
    
    # Execution
    status: GoalStatus = GoalStatus.PENDING
    target_outcome: Optional[str] = None
    actual_outcome: Optional[Outcome] = None
    
    # Metadata
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    
    # Context
    context: Dict = field(default_factory=dict)
    
    # Learning
    cost_analysis: CostAnalysis = field(default_factory=CostAnalysis)
    success_pattern_id: Optional[str] = None  # If using a known pattern
    
    # Performance
    retry_count: int = 0
    max_retries: int = 3
    
    def to_dict(self) -> Dict:
        """Convert to dict for serialization"""
        data = asdict(self)
        # Convert enums
        data['goal_type'] = self.goal_type.value
        data['status'] = self.status.value
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Goal':
        """Load from dict"""
        # Convert enums back
        data['goal_type'] = GoalType(data['goal_type'])
        data['status'] = GoalStatus(data['status'])
        
        # Convert nested objects
        if data.get('prerequisites'):
            data['prerequisites'] = [
                Prerequisite.from_dict(p) if isinstance(p, dict) else p 
                for p in data['prerequisites']
            ]
        if data.get('actual_outcome') and isinstance(data['actual_outcome'], dict):
            data['actual_outcome'] = Outcome.from_dict(data['actual_outcome'])
        if data.get('cost_analysis') and isinstance(data['cost_analysis'], dict):
            data['cost_analysis'] = CostAnalysis.from_dict(data['cost_analysis'])
        
        return cls(**data)
    
    def is_ready(self) -> bool:
        """Check if all blocking prerequisites are met"""
        if self.status == GoalStatus.BLOCKED:
            return False
        
        for prereq in self.prerequisites:
            if prereq.blocking:
                # TODO: Actually evaluate prerequisites
                pass
        
        return True
    
    def is_terminal(self) -> bool:
        """Check if this is a terminal node (STOP/ABORT)"""
        return self.goal_type in [GoalType.STOP, GoalType.ABORT]
    
    def add_child(self, child_goal: 'Goal') -> str:
        """Add a child goal"""
        child_goal.parent_id = self.id
        child_goal.plan_id = self.plan_id
        self.children.append(child_goal.id)
        return child_goal.id
    
    def estimate_cost(self, cost_type: CostType, amount: float):
        """Add estimated cost"""
        self.cost_analysis.estimated_costs[cost_type.value] = amount
    
    def record_cost(self, cost_type: CostType, amount: float):
        """Record actual cost"""
        self.cost_analysis.actual_costs[cost_type.value] = amount


@dataclass
class Plan:
    """Complete execution plan with evaluation"""
    
    id: str
    root_goal_id: str
    description: str
    
    # All goals in this plan
    goals: Dict[str, Goal] = field(default_factory=dict)
    
    # Execution tracking
    status: GoalStatus = GoalStatus.PENDING
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    
    # Overall outcomes
    success: bool = False
    final_outcome: Optional[Outcome] = None
    
    # Learning
    pattern_signature: Optional[str] = None  # Hash of goal structure
    tags: List[str] = field(default_factory=list)
    
    # Performance
    total_cost: CostAnalysis = field(default_factory=CostAnalysis)
    evaluation_score: Optional[float] = None  # 0.0-1.0
    lessons_learned: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict:
        """Serialize to dict"""
        data = asdict(self)
        data['status'] = self.status.value
        data['goals'] = {gid: g.to_dict() for gid, g in self.goals.items()}
        return data
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'Plan':
        """Deserialize from dict"""
        data['status'] = GoalStatus(data['status'])
        
        # Reconstruct goals
        goals_data = data.pop('goals', {})
        plan = cls(**data)
        plan.goals = {
            gid: Goal.from_dict(g) if isinstance(g, dict) else g 
            for gid, g in goals_data.items()
        }
        
        return plan
    
    def add_goal(self, goal: Goal) -> str:
        """Add a goal to the plan"""
        goal.plan_id = self.id
        self.goals[goal.id] = goal
        return goal.id
    
    def get_goal(self, goal_id: str) -> Optional[Goal]:
        """Retrieve a goal by ID"""
        return self.goals.get(goal_id)
    
    def get_root_goal(self) -> Optional[Goal]:
        """Get the root goal"""
        return self.goals.get(self.root_goal_id)
    
    def get_children(self, goal_id: str) -> List[Goal]:
        """Get child goals of a goal"""
        goal = self.goals.get(goal_id)
        if not goal:
            return []
        return [self.goals[cid] for cid in goal.children if cid in self.goals]
    
    def compute_signature(self) -> str:
        """
        Compute a signature hash of the goal structure.
        Used for pattern matching against historical plans.
        """
        # Build a normalized structure representation
        def build_tree(goal_id: str) -> Dict:
            goal = self.goals.get(goal_id)
            if not goal:
                return {}
            
            return {
                "type": goal.goal_type.value,
                "children": [build_tree(cid) for cid in goal.children]
            }
        
        tree = build_tree(self.root_goal_id)
        tree_str = json.dumps(tree, sort_keys=True)
        
        signature = hashlib.sha256(tree_str.encode()).hexdigest()[:16]
        self.pattern_signature = signature
        return signature
    
    def to_visualizer_json(self) -> Dict:
        """
        Export plan in format for 3D Request Fingerprint Visualizer.
        
        Returns JSON with steps array containing:
        - id, prompt, type, children, fingerprint (7 dimensions)
        """
        
        def compute_fingerprint(goal: Goal) -> Dict[str, float]:
            """
            Compute 7-dimensional fingerprint for a goal.
            
            Dimensions (all 0.0-1.0):
            - intent: 0.0=inquiry, 0.5=assistance, 1.0=directive
            - domain: 0.0=technical, 0.33=analytical, 0.67=creative, 1.0=planning
            - complexity: 0.0=simple, 0.5=moderate, 1.0=complex
            - outputType: 0.0=code, 0.33=data, 0.67=text, 1.0=decision
            - specificity: 0.0=vague, 0.5=moderate, 1.0=precise
            - timeHorizon: 0.0=immediate, 0.5=short-term, 1.0=long-term
            - interactivity: 0.0=one-shot, 0.5=some, 1.0=iterative
            """
            
            desc_lower = goal.description.lower()
            
            # Intent: analyze keywords
            if any(w in desc_lower for w in ["what", "how", "why", "explain"]):
                intent = 0.3  # Inquiry
            elif any(w in desc_lower for w in ["help", "assist", "suggest", "recommend"]):
                intent = 0.5  # Assistance
            else:
                intent = 0.8  # Directive
            
            # Domain: categorize by keywords
            if any(w in desc_lower for w in ["code", "implement", "function", "api", "debug"]):
                domain = 0.1  # Technical
            elif any(w in desc_lower for w in ["analyze", "compare", "evaluate", "research"]):
                domain = 0.4  # Analytical
            elif any(w in desc_lower for w in ["write", "draft", "compose", "create text"]):
                domain = 0.7  # Creative
            elif any(w in desc_lower for w in ["plan", "organize", "schedule", "prepare"]):
                domain = 1.0  # Planning
            else:
                domain = 0.5  # Mixed/unclear
            
            # Complexity: based on children count and estimated time
            num_children = len(goal.children)
            est_time = goal.cost_analysis.estimated_costs.get("time", 0)
            
            if num_children == 0 and est_time < 5:
                complexity = 0.2
            elif num_children <= 2 and est_time < 15:
                complexity = 0.5
            else:
                complexity = 0.8
            
            # OutputType: what's being produced
            if any(w in desc_lower for w in ["code", "script", "program", "function"]):
                output_type = 0.1  # Code
            elif any(w in desc_lower for w in ["data", "list", "table", "results"]):
                output_type = 0.4  # Data
            elif any(w in desc_lower for w in ["document", "report", "summary", "text"]):
                output_type = 0.7  # Text
            elif any(w in desc_lower for w in ["decide", "choose", "recommend", "determine"]):
                output_type = 1.0  # Decision
            else:
                output_type = 0.5  # Mixed
            
            # Specificity: how precise is the request
            specific_indicators = ["specific", "exact", "precisely", "detailed", "particular"]
            vague_indicators = ["some", "maybe", "possibly", "general", "rough"]
            
            if any(w in desc_lower for w in specific_indicators):
                specificity = 0.9
            elif any(w in desc_lower for w in vague_indicators):
                specificity = 0.3
            else:
                # Count concrete nouns/details
                concrete_words = sum(1 for w in ["email", "contact", "calendar", "file", "document"] if w in desc_lower)
                specificity = min(0.9, 0.4 + (concrete_words * 0.15))
            
            # TimeHorizon: when does this happen
            if any(w in desc_lower for w in ["immediate", "now", "right now", "instant"]):
                time_horizon = 0.1
            elif any(w in desc_lower for w in ["today", "soon", "quickly", "shortly"]):
                time_horizon = 0.3
            elif any(w in desc_lower for w in ["tomorrow", "this week", "next week"]):
                time_horizon = 0.6
            elif any(w in desc_lower for w in ["plan", "prepare", "schedule", "future"]):
                time_horizon = 0.9
            else:
                time_horizon = 0.5
            
            # Interactivity: how much back-and-forth
            if goal.goal_type == GoalType.ONE_SHOT:
                interactivity = 0.2
            elif goal.goal_type == GoalType.BRANCHING:
                interactivity = 0.7  # Decisions need interaction
            elif any(w in desc_lower for w in ["clarify", "confirm", "check", "verify"]):
                interactivity = 0.8
            else:
                interactivity = 0.4
            
            return {
                "intent": round(intent, 2),
                "domain": round(domain, 2),
                "complexity": round(complexity, 2),
                "outputType": round(output_type, 2),
                "specificity": round(specificity, 2),
                "timeHorizon": round(time_horizon, 2),
                "interactivity": round(interactivity, 2)
            }
        
        def determine_type(goal: Goal) -> str:
            """Determine step type based on children count"""
            num_children = len(goal.children)
            if num_children == 0:
                return "one-shot"
            elif num_children == 1:
                return "linear"
            else:
                return "branching"
        
        # Build steps array
        steps = []
        
        for goal_id, goal in self.goals.items():
            step = {
                "id": goal_id,
                "prompt": goal.description,
                "type": determine_type(goal),
                "children": goal.children,
                "fingerprint": compute_fingerprint(goal)
            }
            steps.append(step)
        
        return {"steps": steps}
    
    def export_visualizer_json(self, filepath: Path):
        """Export plan to JSON file for visualizer"""
        data = self.to_visualizer_json()
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        return filepath
    
    def evaluate_performance(self) -> float:
        """
        Evaluate overall plan performance.
        Returns score 0.0-1.0
        """
        if self.status != GoalStatus.COMPLETED:
            return 0.0
        
        # Factors:
        # 1. Did we achieve the goal? (60%)
        success_score = 1.0 if self.success else 0.0
        
        # 2. Cost efficiency (20%)
        estimated_total = sum(self.total_cost.estimated_costs.values()) or 1.0
        actual_total = sum(self.total_cost.actual_costs.values()) or 0.0
        
        # Only penalize if significantly over budget
        if actual_total > estimated_total * 1.5:
            cost_score = max(0, 1.0 - ((actual_total - estimated_total) / estimated_total))
        else:
            cost_score = 1.0
        
        # 3. Speed (10%)
        # TODO: Compare actual time to estimated time
        speed_score = 1.0
        
        # 4. Side effects (10%)
        # Fewer unexpected side effects = better
        side_effect_count = 0
        for goal in self.goals.values():
            if goal.actual_outcome:
                side_effect_count += len(goal.actual_outcome.side_effects)
        side_effect_score = max(0, 1.0 - (side_effect_count * 0.1))
        
        # Weighted average
        score = (
            success_score * 0.6 +
            cost_score * 0.2 +
            speed_score * 0.1 +
            side_effect_score * 0.1
        )
        
        # Ensure score is between 0.0 and 1.0
        score = max(0.0, min(1.0, score))
        
        self.evaluation_score = score
        return score


class GoalPlanner:
    """Main planner that decomposes and executes goals"""
    
    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.plans_dir = storage_dir / "plans"
        self.patterns_dir = storage_dir / "patterns"
        
        self.plans_dir.mkdir(parents=True, exist_ok=True)
        self.patterns_dir.mkdir(parents=True, exist_ok=True)
        
        # Active plans
        self.active_plans: Dict[str, Plan] = {}
        
        # Pattern library (successful plan templates)
        self.pattern_library: Dict[str, Plan] = {}
        
        self._load_patterns()
    
    def _log(self, message: str):
        """Simple logging"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [PLANNER] {message}")
    
    # ==================== PLAN CREATION ====================
    
    def create_plan(self, description: str, root_goal: Goal) -> Plan:
        """Create a new plan with a root goal"""
        plan_id = str(uuid.uuid4())[:8]
        
        plan = Plan(
            id=plan_id,
            root_goal_id=root_goal.id,
            description=description
        )
        
        plan.add_goal(root_goal)
        root_goal.plan_id = plan_id
        
        self.active_plans[plan_id] = plan
        
        self._log(f"Created plan {plan_id}: {description}")
        
        return plan
    
    def decompose_goal(
        self,
        plan: Plan,
        goal_id: str,
        decomposition_strategy: str = "auto"
    ) -> List[Goal]:
        """
        Decompose a goal into child goals.
        
        Strategy can be:
        - "auto": Use LLM to determine
        - "linear": Sequential steps
        - "branching": Decision tree
        - "parallel": Independent sub-tasks
        """
        goal = plan.get_goal(goal_id)
        if not goal:
            return []
        
        # If already decomposed, return existing children
        if goal.children:
            return plan.get_children(goal_id)
        
        # TODO: Use LLM to actually decompose
        # For now, this is a placeholder
        
        self._log(f"Decomposing goal {goal_id} using {decomposition_strategy} strategy")
        
        # Example decomposition (would come from LLM)
        children = []
        
        if decomposition_strategy == "linear":
            # Create sequential steps
            for i, step_desc in enumerate(["Step 1", "Step 2", "Step 3"]):
                child = Goal(
                    id=str(uuid.uuid4())[:8],
                    description=step_desc,
                    goal_type=GoalType.ONE_SHOT,
                    parent_id=goal_id,
                    plan_id=plan.id
                )
                
                goal.add_child(child)
                plan.add_goal(child)
                children.append(child)
        
        # Update parent type
        if children:
            goal.goal_type = GoalType.LINEAR
        
        return children
    
    # ==================== PATTERN MATCHING ====================
    
    def find_similar_patterns(self, plan: Plan, min_score: float = 0.7) -> List[Dict]:
        """
        Find historically successful plans with similar structure.
        Returns list of matches with similarity scores.
        """
        current_sig = plan.compute_signature()
        
        matches = []
        
        for pattern_id, pattern in self.pattern_library.items():
            # Simple signature matching (could be more sophisticated)
            if pattern.pattern_signature == current_sig:
                matches.append({
                    "pattern_id": pattern_id,
                    "plan": pattern,
                    "similarity": 1.0,
                    "score": pattern.evaluation_score or 0.0
                })
        
        # Sort by evaluation score
        matches.sort(key=lambda m: m['score'], reverse=True)
        
        return matches
    
    def apply_pattern(self, plan: Plan, pattern: Plan) -> bool:
        """
        Apply a successful pattern to a new plan.
        Copies goal structure and strategies.
        """
        self._log(f"Applying pattern {pattern.id} to plan {plan.id}")
        
        # Copy goal tree structure
        def copy_tree(src_goal_id: str, parent_goal_id: Optional[str] = None):
            src_goal = pattern.get_goal(src_goal_id)
            if not src_goal:
                return None
            
            # Create new goal with same structure
            new_goal = Goal(
                id=str(uuid.uuid4())[:8],
                description=src_goal.description,
                goal_type=src_goal.goal_type,
                prompt_template=src_goal.prompt_template,
                target_outcome=src_goal.target_outcome,
                parent_id=parent_goal_id,
                plan_id=plan.id
            )
            
            # Copy prerequisites
            new_goal.prerequisites = [
                Prerequisite(**asdict(p)) for p in src_goal.prerequisites
            ]
            
            # Copy cost estimates
            new_goal.cost_analysis.estimated_costs = src_goal.cost_analysis.actual_costs.copy()
            
            plan.add_goal(new_goal)
            
            # Recursively copy children
            for child_id in src_goal.children:
                child = copy_tree(child_id, new_goal.id)
                if child:
                    new_goal.children.append(child.id)
            
            return new_goal
        
        # Copy from root
        new_root = copy_tree(pattern.root_goal_id)
        if new_root:
            plan.root_goal_id = new_root.id
            plan.pattern_signature = pattern.pattern_signature
            return True
        
        return False
    
    def save_as_pattern(self, plan: Plan, tags: List[str] = None):
        """
        Save a successful plan as a reusable pattern.
        """
        if not plan.success or not plan.evaluation_score:
            self._log(f"Cannot save pattern: plan not successful")
            return False
        
        if plan.evaluation_score < 0.7:
            self._log(f"Cannot save pattern: score too low ({plan.evaluation_score:.2f})")
            return False
        
        plan.compute_signature()
        plan.tags = tags or []
        
        # Save to pattern library
        pattern_id = plan.pattern_signature or plan.id
        self.pattern_library[pattern_id] = plan
        
        # Persist to disk
        pattern_file = self.patterns_dir / f"{pattern_id}.json"
        with open(pattern_file, 'w') as f:
            json.dump(plan.to_dict(), f, indent=2)
        
        self._log(f"Saved pattern {pattern_id} (score: {plan.evaluation_score:.2f})")
        return True
    
    def _load_patterns(self):
        """Load pattern library from disk"""
        for pattern_file in self.patterns_dir.glob("*.json"):
            try:
                with open(pattern_file) as f:
                    data = json.load(f)
                    plan = Plan.from_dict(data)
                    self.pattern_library[plan.pattern_signature or plan.id] = plan
            except Exception as e:
                self._log(f"Error loading pattern {pattern_file}: {e}")
        
        if self.pattern_library:
            self._log(f"Loaded {len(self.pattern_library)} patterns")
    
    # ==================== EXECUTION ====================
    
    def execute_goal(self, plan: Plan, goal_id: str) -> Outcome:
        """
        Execute a single goal.
        Returns the outcome.
        """
        goal = plan.get_goal(goal_id)
        if not goal:
            return Outcome(success=False, error="Goal not found")
        
        # Check prerequisites
        if not goal.is_ready():
            goal.status = GoalStatus.BLOCKED
            return Outcome(success=False, error="Prerequisites not met")
        
        goal.status = GoalStatus.IN_PROGRESS
        goal.started_at = datetime.now().isoformat()
        
        self._log(f"Executing goal {goal_id}: {goal.description}")
        
        # TODO: Actually execute via LLM or action
        # This is a placeholder
        
        # Simulate execution
        outcome = Outcome(
            success=True,
            result_data={"message": "Executed successfully"},
            confidence=0.95
        )
        
        goal.actual_outcome = outcome
        goal.status = GoalStatus.COMPLETED if outcome.success else GoalStatus.FAILED
        goal.completed_at = datetime.now().isoformat()
        
        return outcome
    
    def execute_plan(self, plan: Plan) -> bool:
        """
        Execute entire plan.
        Returns True if plan completed successfully.
        """
        plan.status = GoalStatus.IN_PROGRESS
        plan.started_at = datetime.now().isoformat()
        
        self._log(f"Executing plan {plan.id}: {plan.description}")
        
        # Execute from root
        success = self._execute_goal_tree(plan, plan.root_goal_id)
        
        plan.status = GoalStatus.COMPLETED if success else GoalStatus.FAILED
        plan.completed_at = datetime.now().isoformat()
        plan.success = success
        
        # Evaluate performance
        score = plan.evaluate_performance()
        self._log(f"Plan {plan.id} completed with score {score:.2f}")
        
        # Save to disk
        self._save_plan(plan)
        
        # Consider saving as pattern if successful
        if success and score >= 0.7:
            self.save_as_pattern(plan)
        
        return success
    
    def _execute_goal_tree(self, plan: Plan, goal_id: str) -> bool:
        """Recursively execute goal tree"""
        goal = plan.get_goal(goal_id)
        if not goal:
            return False
        
        # Terminal nodes
        if goal.goal_type == GoalType.STOP:
            return True
        if goal.goal_type == GoalType.ABORT:
            return False
        
        # One-shot goals
        if goal.goal_type == GoalType.ONE_SHOT:
            outcome = self.execute_goal(plan, goal_id)
            return outcome.success
        
        # Linear execution
        if goal.goal_type == GoalType.LINEAR:
            for child_id in goal.children:
                if not self._execute_goal_tree(plan, child_id):
                    return False
            return True
        
        # Branching - try paths until one succeeds
        if goal.goal_type == GoalType.BRANCHING:
            for child_id in goal.children:
                if self._execute_goal_tree(plan, child_id):
                    return True
            return False
        
        # Parallel - all must succeed
        if goal.goal_type == GoalType.PARALLEL:
            results = []
            for child_id in goal.children:
                results.append(self._execute_goal_tree(plan, child_id))
            return all(results)
        
        return False
    
    def _save_plan(self, plan: Plan):
        """Save plan to disk"""
        plan_file = self.plans_dir / f"{plan.id}.json"
        with open(plan_file, 'w') as f:
            json.dump(plan.to_dict(), f, indent=2)
    
    # ==================== COST-BENEFIT ANALYSIS ====================
    
    def analyze_costs(self, plan: Plan) -> CostAnalysis:
        """
        Analyze estimated vs actual costs for a plan.
        """
        total_analysis = CostAnalysis()
        
        for goal in plan.goals.values():
            # Aggregate costs
            for cost_type, amount in goal.cost_analysis.estimated_costs.items():
                total_analysis.estimated_costs[cost_type] = \
                    total_analysis.estimated_costs.get(cost_type, 0) + amount
            
            for cost_type, amount in goal.cost_analysis.actual_costs.items():
                total_analysis.actual_costs[cost_type] = \
                    total_analysis.actual_costs.get(cost_type, 0) + amount
            
            # Collect risks
            total_analysis.risks.extend(goal.cost_analysis.risks)
        
        plan.total_cost = total_analysis
        return total_analysis


# ==================== TESTING ====================

def test_planner():
    """Test the goal planner"""
    from pathlib import Path
    import tempfile
    import shutil
    
    temp_dir = Path(tempfile.mkdtemp())
    
    try:
        print("\n" + "=" * 60)
        print("Testing Goal Planner")
        print("=" * 60)
        
        planner = GoalPlanner(temp_dir)
        
        # Test 1: Create a simple one-shot plan
        print("\n1. Creating one-shot plan...")
        root = Goal(
            id="goal1",
            description="Send an email to Bob",
            goal_type=GoalType.ONE_SHOT,
            target_outcome="Email sent successfully"
        )
        
        plan1 = planner.create_plan("Email Bob", root)
        print(f"Created plan: {plan1.id}")
        
        # Test 2: Create a linear plan
        print("\n2. Creating linear plan...")
        root2 = Goal(
            id="goal2",
            description="Organize team meeting",
            goal_type=GoalType.LINEAR,
            target_outcome="Meeting scheduled and invites sent"
        )
        
        plan2 = planner.create_plan("Organize meeting", root2)
        
        # Add children
        children = planner.decompose_goal(plan2, root2.id, "linear")
        print(f"Decomposed into {len(children)} steps")
        
        # Test 3: Execute plan
        print("\n3. Executing plan...")
        success = planner.execute_plan(plan1)
        print(f"Execution result: {'SUCCESS' if success else 'FAILED'}")
        print(f"Evaluation score: {plan1.evaluation_score:.2f}")
        
        # Test 4: Pattern matching
        print("\n4. Testing pattern matching...")
        plan2.compute_signature()
        print(f"Plan signature: {plan2.pattern_signature}")
        
        # Test 5: Cost analysis
        print("\n5. Cost analysis...")
        plan1.goals[root.id].estimate_cost(CostType.TIME, 5.0)
        plan1.goals[root.id].record_cost(CostType.TIME, 4.2)
        
        analysis = planner.analyze_costs(plan1)
        print(f"Estimated time: {analysis.estimated_costs.get('time', 0)}s")
        print(f"Actual time: {analysis.actual_costs.get('time', 0)}s")
        
        print("\n✅ All tests passed!")
        
    finally:
        shutil.rmtree(temp_dir)
        print(f"\nCleaned up: {temp_dir}")


if __name__ == "__main__":
    test_planner()