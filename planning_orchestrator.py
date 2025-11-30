# planning_orchestrator.py
"""
JARVIS Planning Orchestrator

Handles planning orchestration, decision-making, and execution.
Extracted from jarvis_core.py to improve modularity.

Features:
- Decides when planning is needed
- Creates plans from user requests
- Executes plans with proper error handling
- Manages approval workflows
- Tracks execution metrics
"""

import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from jarvis_planner import GoalPlanner, Goal, Plan, GoalType, GoalStatus, CostType, Outcome


class PlanningOrchestrator:
    """
    Orchestrates the planning and execution workflow.
    
    Responsibilities:
    - Determine when planning is needed
    - Create plans (from scratch or patterns)
    - Execute plans with goal tree traversal
    - Handle approvals for high-risk plans
    - Track success metrics
    """
    
    def __init__(self, jarvis_core):
        """
        Initialize with reference to JarvisCore
        
        Args:
            jarvis_core: Main JARVIS instance for accessing state
        """
        self.core = jarvis_core
        self.planner: Optional[GoalPlanner] = None
        
        # Execution statistics
        self.stats = {
            "plans_created": 0,
            "plans_executed": 0,
            "plans_succeeded": 0,
            "plans_failed": 0,
            "patterns_applied": 0,
            "approvals_requested": 0
        }
    
    def initialize(self, planner: GoalPlanner):
        """Initialize with the planner instance"""
        self.planner = planner
        self.core._log("PLANNING", "Planning orchestrator initialized")
    
    # ==================== PLANNING DECISION ====================
    
    async def should_plan(self, intent: str, user_input: str, context: Dict) -> bool:
        """
        Determine if request needs hierarchical planning
        
        Args:
            intent: Classified intent type
            user_input: Raw user input
            context: Additional context
            
        Returns:
            True if planning is needed, False otherwise
        """
        
        user_lower = user_input.lower()
        
        # Keywords that strongly suggest planning
        planning_keywords = [
            "plan", "organize", "prepare", "schedule",
            "help me", "how should i", "how do i", "how can i",
            "what's the best way", "but how", "how to",
            "figure out", "work out", "find a way to"
        ]
        
        if any(kw in user_lower for kw in planning_keywords):
            self.core._log("PLANNING", f"Planning keyword detected")
            return True
        
        # Research/comparison queries that need multi-step investigation
        research_indicators = [
            "find the best", "what's the best", "best",
            "compare", "recommend", "recommendation",
            "vs", "versus", "should i buy", "should i get",
            "find a", "find good", "find some"
        ]
        
        # Check for research patterns
        for indicator in research_indicators:
            if indicator in user_lower:
                # Additional check: if it's not asking about stored data
                if not any(word in user_lower for word in ["my", "bob", "sarah", "contact", "calendar", "note"]):
                    self.core._log("PLANNING", f"Research indicator detected: '{indicator}'")
                    return True
        
        # Multi-step implicit requests
        if " and " in user_lower and intent not in ["conversation", "crud_read", "query"]:
            self.core._log("PLANNING", f"Multi-step request detected")
            return True
        
        return False
    
    # ==================== PLAN CREATION ====================
    
    async def handle_with_planning(self, task, intent_data: Dict) -> str:
        """
        Handle request using goal planning
        
        Args:
            task: Task object with user request
            intent_data: Intent classification data
            
        Returns:
            Response string
        """
        
        self.core._log("PLANNING", f"Creating plan for: {task.content}")
        self.stats["plans_created"] += 1
        
        # Check for similar patterns first
        temp_plan = await self._create_plan_structure(task)
        similar_patterns = self.planner.find_similar_patterns(temp_plan, min_score=0.7)
        
        if similar_patterns:
            # Use existing pattern
            pattern = similar_patterns[0]['plan']
            self.core._log("PLANNING", f"Found matching pattern {pattern.id} (score: {pattern.evaluation_score:.2f})")
            self.stats["patterns_applied"] += 1
            
            root_goal = Goal(
                id=str(uuid.uuid4())[:8],
                description=task.content,
                goal_type=GoalType.LINEAR
            )
            
            plan = self.planner.create_plan(task.content, root_goal)
            self.planner.apply_pattern(plan, pattern)
            
            plan_source = f"using proven pattern (score: {pattern.evaluation_score:.1%})"
        else:
            # Create new plan from scratch
            plan = await self._create_plan_from_scratch(task)
            plan_source = "new plan"
        
        # Estimate costs
        cost_summary = self._estimate_plan_costs(plan)
        
        # Check if approval needed
        if cost_summary["high_risk"]:
            # Store pending approval
            self.core.pending_approvals[plan.id] = {
                "plan": plan,
                "task_id": task.task_id,
                "terminal_id": task.source_terminal,
                "cost_summary": cost_summary
            }
            self.stats["approvals_requested"] += 1
            
            return f"I can help with that ({plan_source}). The plan involves:\n" \
                   f"{self._format_plan_summary(plan)}\n\n" \
                   f"Estimated: {cost_summary['summary']}\n" \
                   f"Reply 'yes' to proceed or 'no' to cancel."
        
        # Execute immediately
        self.core.active_plans[task.task_id] = plan.id
        
        # Execute plan
        success = await self.execute_plan(plan)
        
        if success:
            # Build detailed response with results from each step
            result_lines = [f"✅ Completed: {plan.description}"]
            
            if plan.evaluation_score:
                result_lines.append(f"Evaluation score: {plan.evaluation_score:.1%}")
            
            # DEBUG: Check what we have
            self.core._log("DEBUG", f"Plan ID: {plan.id}")
            self.core._log("DEBUG", f"Plan has {len(plan.goals)} goals")
            
            result_lines.append("")  # Blank line
            result_lines.append("Here's what I found:")
            result_lines.append("")
            
            # Collect results from each executed goal
            root_goal = plan.get_root_goal()
            self.core._log("DEBUG", f"Root goal exists: {root_goal is not None}")
            if root_goal:
                self.core._log("DEBUG", f"Root goal ID: {root_goal.id}")
                self.core._log("DEBUG", f"Root goal has children: {hasattr(root_goal, 'children')}")
                if hasattr(root_goal, 'children'):
                    self.core._log("DEBUG", f"Root goal children count: {len(root_goal.children)}")
                    self.core._log("DEBUG", f"Root goal children: {root_goal.children}")
            
            if root_goal and root_goal.children:
                for i, child_id in enumerate(root_goal.children, 1):
                    child = plan.get_goal(child_id)
                    self.core._log("DEBUG", f"Child {i} ID: {child_id}")
                    self.core._log("DEBUG", f"Child {i} exists: {child is not None}")
                    
                    if child:
                        self.core._log("DEBUG", f"Child {i} description: {child.description}")
                        self.core._log("DEBUG", f"Child {i} has actual_outcome: {hasattr(child, 'actual_outcome')}")
                        if hasattr(child, 'actual_outcome'):
                            self.core._log("DEBUG", f"Child {i} actual_outcome value: {child.actual_outcome}")
                    
                    if child and child.actual_outcome:
                        result_lines.append(f"{i}. **{child.description}**")
                        
                        # Get the result from the outcome
                        if hasattr(child.actual_outcome, 'result_data') and child.actual_outcome.result_data:
                            result_data = child.actual_outcome.result_data
                            
                            # Try to get the 'result' field first
                            outcome_result = result_data.get('result', '')
                            
                            # If result is a dict/JSON, format it nicely
                            if isinstance(outcome_result, dict):
                                result_lines.append(f"   {self._format_structured_result(outcome_result)}")
                            elif isinstance(outcome_result, str) and outcome_result:
                                # Clean text result
                                result_lines.append(f"   {outcome_result}")
                            else:
                                # Fallback to action field
                                action = result_data.get('action', '')
                                if action:
                                    result_lines.append(f"   {action}")
                        
                        result_lines.append("")  # Blank line between steps
            else:
                self.core._log("DEBUG", "Root goal or children check failed!")
            
            self.core._log("DEBUG", f"Total result lines: {len(result_lines)}")
            return "\n".join(result_lines)
        else:
            return f"❌ Could not complete: {plan.description}"
    
    async def _create_plan_structure(self, task) -> Plan:
        """Create plan structure for pattern matching"""
        root_goal = Goal(
            id="root",
            description=task.content,
            goal_type=GoalType.LINEAR
        )
        
        plan = self.planner.create_plan(task.content, root_goal)
        return plan
    
    async def _create_plan_from_scratch(self, task) -> Plan:
        """Create a new plan from scratch using LLM decomposition"""
        
        # Build context about available capabilities
        capabilities = self._get_system_capabilities()
        
        # Get decomposition prompt (boot or runtime override)
        prompt_template = self._get_decompose_prompt_template()
        
        # Fill in template variables
        decompose_prompt = prompt_template.format(
            user_request=task.content,
            capabilities=capabilities
        )
        
        result = await self.core.prompt_manager.execute_prompt(
            decompose_prompt,
            prompt_id="decompose_task",
            use_smart_model=True,
            max_tokens=1000
        )
        
        if not result.success or not result.parsed_json:
            self.core._log("PLANNING", f"Decomposition failed: {result.error}")
            # Fallback to one-shot
            root = Goal(
                id=str(uuid.uuid4())[:8],
                description=task.content,
                goal_type=GoalType.ONE_SHOT,
                prompt_template=task.content
            )
            return self.planner.create_plan(task.content, root)
        
        # Build plan from LLM response
        plan_data = result.parsed_json
        self.core._log("PLANNING", f"Plan type: {plan_data.get('goal_type', 'linear')}")
        self.core._log("PLANNING", f"Reasoning: {plan_data.get('reasoning', 'N/A')}")
        
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
            self.core._log("PLANNING", f"Missing info: {', '.join(plan_data['missing_info'])}")
        
        return plan
    
    def _get_system_capabilities(self) -> str:
        """Get description of system capabilities"""
        capabilities = []
        
        if self.core.memory_store:
            capabilities.append("- Memory: Store and retrieve contacts, notes, calendar events")
        
        if self.core.prompt_manager:
            capabilities.append("- LLM: Generate responses, analyze data, make decisions")
        
        capabilities.append("- Planning: Break down complex tasks into steps")
        capabilities.append("- Execution: Execute multi-step plans with error handling")
        
        return "\n".join(capabilities)
    
    def _get_decompose_prompt_template(self) -> str:
        """Get decomposition prompt template (runtime override or boot default)"""
        
        # Check for runtime override first
        if "decompose_task" in self.core.runtime_prompts:
            self.core._log("PLANNING", "Using runtime override for decompose_task prompt")
            return self.core.runtime_prompts["decompose_task"]["template"]
        
        # Fall back to boot prompt
        if "decompose_task" in self.core.boot_prompts:
            return self.core.boot_prompts["decompose_task"]["template"]
        
        # Ultimate fallback (should never happen)
        self.core._log("PLANNING", "WARNING: No decompose_task prompt found, using minimal fallback")
        return """Break down this task: "{user_request}"

Available capabilities:
{capabilities}

Return JSON with: goal_type, steps, reasoning"""
    
    # ==================== PLAN EXECUTION ====================
    
    async def execute_plan(self, plan: Plan) -> bool:
        """
        Execute plan asynchronously
        
        Args:
            plan: Plan to execute
            
        Returns:
            True if successful, False otherwise
        """
        
        self.core._log("PLANNING", f"Executing plan {plan.id}: {plan.description}")
        self.stats["plans_executed"] += 1
        
        plan.status = GoalStatus.IN_PROGRESS
        plan.started_at = datetime.now().isoformat()
        
        success = await self._execute_goal_tree(plan, plan.root_goal_id)
        
        plan.status = GoalStatus.COMPLETED if success else GoalStatus.FAILED
        plan.completed_at = datetime.now().isoformat()
        plan.success = success
        
        # Update stats
        if success:
            self.stats["plans_succeeded"] += 1
        else:
            self.stats["plans_failed"] += 1
        
        # Evaluate
        score = plan.evaluate_performance()
        self.core._log("PLANNING", f"Plan {plan.id} completed: {success}, score: {score:.2f}")
        
        # Save pattern if successful
        if success and score >= 0.7:
            self.planner.save_as_pattern(plan)
        
        return success
    
    async def _execute_goal_tree(self, plan: Plan, goal_id: str) -> bool:
        """
        Recursively execute goal tree
        
        Args:
            plan: Plan being executed
            goal_id: Current goal ID
            
        Returns:
            True if goal succeeded
        """
        
        goal = plan.get_goal(goal_id)
        if not goal:
            return False
        
        # Terminal nodes
        if goal.goal_type == GoalType.STOP:
            return True
        if goal.goal_type == GoalType.ABORT:
            return False
        
        # One-shot goals - execute via prompt
        if goal.goal_type == GoalType.ONE_SHOT:
            outcome = await self._execute_single_goal(plan, goal_id)
            return outcome.success
        
        # Linear - sequential execution
        if goal.goal_type == GoalType.LINEAR:
            for child_id in goal.children:
                if not await self._execute_goal_tree(plan, child_id):
                    return False
            return True
        
        # Branching - try until one succeeds
        if goal.goal_type == GoalType.BRANCHING:
            for child_id in goal.children:
                if await self._execute_goal_tree(plan, child_id):
                    return True
            return False
        
        # Parallel - all must succeed (for now, sequential)
        if goal.goal_type == GoalType.PARALLEL:
            results = []
            for child_id in goal.children:
                results.append(await self._execute_goal_tree(plan, child_id))
            return all(results)
        
        return False
    
    async def _execute_single_goal(self, plan: Plan, goal_id: str) -> Outcome:
        """
        Execute a single goal using available tools (search, memory, LLM)
        
        Args:
            plan: Plan being executed
            goal_id: Goal to execute
            
        Returns:
            Outcome object with success/failure and details
        """
        
        goal = plan.get_goal(goal_id)
        if not goal:
            return Outcome(success=False, error="Goal not found")
        
        goal.status = GoalStatus.IN_PROGRESS
        goal.started_at = datetime.now().isoformat()
        
        self.core._log("PLANNING", f"  Executing: {goal.description}")
        
        # Check if goal needs web search
        search_keywords = ["research", "find", "search", "look up", "investigate", 
                          "compare", "what are", "get information", "discover", "explore"]
        needs_search = any(keyword in goal.description.lower() for keyword in search_keywords)
        
        search_results_text = ""
        
        # Perform web search if needed and available
        if needs_search and self.core.search_provider:
            self.core._log("PLANNING", f"  → Triggering web search for goal")
            
            try:
                # Extract search query from goal description
                search_query = self._extract_search_query(goal.description)
                
                # Perform search
                results = self.core.search_provider.search(search_query, num_results=5)
                
                if results:
                    self.core._log("PLANNING", f"  → Found {len(results)} search results")
                    
                    # Format results for LLM
                    search_results_text = "\n\nWEB SEARCH RESULTS:\n"
                    for i, result in enumerate(results[:5], 1):
                        search_results_text += f"\n{i}. {result.title}\n"
                        search_results_text += f"   {result.url}\n"
                        search_results_text += f"   {result.snippet}\n"
                
            except Exception as e:
                self.core._log("ERROR", f"Search failed during planning: {e}")
        
        # Build execution prompt with context
        root_goal = plan.get_root_goal()
        parent_goal = plan.get_goal(goal.parent_id) if goal.parent_id else None
        
        execution_prompt = f"""You are JARVIS executing a planned goal.

ORIGINAL REQUEST: "{root_goal.description if root_goal else 'Unknown'}"

CURRENT GOAL: "{goal.description}"

YOUR AVAILABLE CAPABILITIES:
{self._get_system_capabilities()}

CONTEXT:
- This is part of a larger plan to: {plan.description}
- Parent goal: {parent_goal.description if parent_goal else 'This is the root goal'}
{search_results_text}

TASK: Execute this specific goal using the information available above.

What to do:
1. If web search results are provided above, USE THEM to answer this goal
2. If this goal uses memory (contacts, calendar, notes), use the information you have
3. If this goal requires analysis or generation, provide your best reasoning
4. Be SPECIFIC and cite information from search results when available

IMPORTANT: 
- If you have search results, synthesize them into a useful answer
- If you successfully provide information (from search or analysis), return success: true
- Only return success: false if the goal is impossible or makes no sense

Respond with JSON:
{{
  "action_taken": "What you did (searched web, analyzed, etc.)",
  "result": "The specific outcome with details from search results",
  "success": true,
  "data_sources": ["web search", "memory", "analysis"],
  "next_steps": "What should happen next, if anything"
}}

Execute: "{goal.description}"
"""
        
        result = await self.core.prompt_manager.execute_prompt(
            execution_prompt,
            prompt_id=f"execute_goal",
            use_smart_model=True,
            max_tokens=500
        )
        
        # Create outcome
        if result.success and result.parsed_json:
            execution_data = result.parsed_json
            
            outcome = Outcome(
                success=execution_data.get("success", True),
                result_data={
                    "action": execution_data.get("action_taken", ""),
                    "result": execution_data.get("result", ""),
                    "next_steps": execution_data.get("next_steps", "")
                },
                confidence=0.8 if not execution_data.get("requires_external") else 0.5,
                observations=[
                    f"Requires external: {execution_data.get('requires_external', False)}"
                ]
            )
            
            # Log what was done
            self.core._log("PLANNING", f"    → {execution_data.get('action_taken', 'No action')}")
            
        else:
            # Fallback - just use the raw LLM response
            outcome = Outcome(
                success=True,
                result_data={"response": result.response or "Executed"},
                confidence=0.6
            )
        
        goal.actual_outcome = outcome
        goal.status = GoalStatus.COMPLETED if outcome.success else GoalStatus.FAILED
        goal.completed_at = datetime.now().isoformat()
        
        # Record actual costs
        if result.elapsed_ms:
            goal.actual_cost = {"time_ms": result.elapsed_ms}
        
        return outcome
    
    def _extract_search_query(self, goal_description: str) -> str:
        """
        Extract a good search query from a goal description
        
        Args:
            goal_description: The goal description
            
        Returns:
            Clean search query
        """
        
        # Remove action words from start
        query = goal_description.lower()
        
        action_words = ["research", "find", "search for", "look up", "investigate", 
                       "compare", "get information about", "discover", "explore",
                       "research and compare", "identify"]
        
        for action in action_words:
            if query.startswith(action):
                query = query[len(action):].strip()
                break
        
        # Remove "and" at the end if present
        if query.endswith(" and"):
            query = query[:-4]
        
        # Clean up
        query = query.strip(" .,!?")
        
        return query
    
    def _format_structured_result(self, data: dict, indent: int = 3) -> str:
        """
        Format a structured dict/JSON result for readable display
        
        Args:
            data: Dictionary to format
            indent: Indentation level
            
        Returns:
            Formatted string
        """
        
        lines = []
        prefix = " " * indent
        
        for key, value in data.items():
            # Format key nicely (convert snake_case to Title Case)
            display_key = key.replace('_', ' ').title()
            
            if isinstance(value, dict):
                # Nested dict
                lines.append(f"{prefix}**{display_key}:**")
                for subkey, subvalue in value.items():
                    subdisplay_key = subkey.replace('_', ' ').title()
                    if isinstance(subvalue, list):
                        lines.append(f"{prefix}  • {subdisplay_key}: {', '.join(map(str, subvalue))}")
                    else:
                        lines.append(f"{prefix}  • {subdisplay_key}: {subvalue}")
            
            elif isinstance(value, list):
                # List of items
                lines.append(f"{prefix}**{display_key}:**")
                for item in value:
                    if isinstance(item, dict):
                        # List of dicts (like hotels)
                        name = item.get('name', item.get('title', 'Item'))
                        lines.append(f"{prefix}  • {name}")
                        if 'link' in item:
                            lines.append(f"{prefix}    {item['link']}")
                        if 'description' in item:
                            desc = item['description'][:100] + "..." if len(item['description']) > 100 else item['description']
                            lines.append(f"{prefix}    {desc}")
                    else:
                        lines.append(f"{prefix}  • {item}")
            
            else:
                # Simple value
                lines.append(f"{prefix}• {display_key}: {value}")
        
        return "\n".join(lines)
    
    # ==================== HELPER METHODS ====================
    
    def _format_plan_summary(self, plan: Plan) -> str:
        """Format plan summary for user display"""
        
        lines = []
        root_goal = plan.get_goal(plan.root_goal_id)
        
        if root_goal:
            for i, child_id in enumerate(root_goal.children, 1):
                child = plan.get_goal(child_id)
                if child:
                    lines.append(f"  {i}. {child.description}")
        
        return "\n".join(lines) if lines else "  (No steps defined)"
    
    def _estimate_plan_costs(self, plan: Plan) -> Dict:
        """
        Estimate costs and risks for a plan
        
        Returns:
            Dict with cost summary and risk assessment
        """
        
        # Count goals
        all_goals = list(plan.goals.values())
        one_shot_count = sum(1 for g in all_goals if g.goal_type == GoalType.ONE_SHOT)
        
        # Estimate API calls
        estimated_api_calls = one_shot_count
        estimated_tokens = estimated_api_calls * 500  # Rough estimate
        
        # Risk assessment
        high_risk = (
            one_shot_count > 5 or  # Many steps
            estimated_tokens > 5000  # High token usage
        )
        
        return {
            "estimated_api_calls": estimated_api_calls,
            "estimated_tokens": estimated_tokens,
            "steps": one_shot_count,
            "high_risk": high_risk,
            "summary": f"{one_shot_count} steps, ~{estimated_api_calls} API calls"
        }
    
    def get_stats(self) -> Dict:
        """Get execution statistics"""
        
        total_plans = self.stats["plans_executed"]
        success_rate = (
            self.stats["plans_succeeded"] / total_plans 
            if total_plans > 0 else 0
        )
        
        return {
            **self.stats,
            "success_rate": success_rate,
            "pattern_reuse_rate": (
                self.stats["patterns_applied"] / self.stats["plans_created"]
                if self.stats["plans_created"] > 0 else 0
            )
        }