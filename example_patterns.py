# example_patterns.py
"""
Example Patterns for JARVIS Planning System

This file contains pre-built successful patterns for common tasks.
These can be loaded into the pattern library to bootstrap learning.
"""

import json
from pathlib import Path
from jarvis_planner import Goal, Plan, GoalType, GoalStatus, CostType, CostAnalysis, Outcome


def create_scheduling_pattern() -> Plan:
    """
    Pattern: Schedule Planning
    
    Use case: "Plan tomorrow's schedule", "Organize my week"
    Structure: Linear sequence with calendar integration
    """
    
    # Root goal
    root = Goal(
        id="sched_root",
        description="Plan schedule for time period",
        goal_type=GoalType.LINEAR,
        target_outcome="Optimized schedule created"
    )
    
    plan = Plan(
        id="pattern_scheduling",
        root_goal_id=root.id,
        description="Schedule planning pattern",
        tags=["schedule", "calendar", "planning"]
    )
    
    plan.add_goal(root)
    
    # Step 1: Check existing commitments
    step1 = Goal(
        id="sched_step1",
        description="Check calendar for existing events",
        goal_type=GoalType.ONE_SHOT,
        prompt_template="List all calendar events for the specified time period",
        parent_id=root.id,
        plan_id=plan.id
    )
    step1.estimate_cost(CostType.TIME, 2.0)
    root.add_child(step1)
    plan.add_goal(step1)
    
    # Step 2: Identify available blocks
    step2 = Goal(
        id="sched_step2",
        description="Identify available time blocks",
        goal_type=GoalType.ONE_SHOT,
        prompt_template="Analyze calendar and identify free time blocks of at least 30 minutes",
        parent_id=root.id,
        plan_id=plan.id
    )
    step2.estimate_cost(CostType.TIME, 3.0)
    root.add_child(step2)
    plan.add_goal(step2)
    
    # Step 3: Review pending tasks
    step3 = Goal(
        id="sched_step3",
        description="Review pending tasks and priorities",
        goal_type=GoalType.ONE_SHOT,
        prompt_template="List pending tasks from notes and memory, ranked by priority",
        parent_id=root.id,
        plan_id=plan.id
    )
    step3.estimate_cost(CostType.TIME, 3.0)
    root.add_child(step3)
    plan.add_goal(step3)
    
    # Step 4: Allocate tasks to blocks
    step4 = Goal(
        id="sched_step4",
        description="Allocate tasks to available time blocks",
        goal_type=GoalType.ONE_SHOT,
        prompt_template="Match high-priority tasks to best-suited time blocks considering energy levels and context",
        parent_id=root.id,
        plan_id=plan.id
    )
    step4.estimate_cost(CostType.TIME, 5.0)
    root.add_child(step4)
    plan.add_goal(step4)
    
    # Step 5: Present and confirm
    step5 = Goal(
        id="sched_step5",
        description="Present schedule for approval",
        goal_type=GoalType.ONE_SHOT,
        prompt_template="Format schedule as clear time blocks with tasks and present to user",
        parent_id=root.id,
        plan_id=plan.id
    )
    step5.estimate_cost(CostType.TIME, 2.0)
    root.add_child(step5)
    plan.add_goal(step5)
    
    # Set overall estimates
    root.estimate_cost(CostType.TIME, 15.0)
    root.cost_analysis.estimated_benefits["productivity"] = 1.0
    root.cost_analysis.estimated_benefits["clarity"] = 1.0
    
    # Mark as successful pattern
    plan.success = True
    plan.status = GoalStatus.COMPLETED
    plan.evaluation_score = 0.92
    plan.compute_signature()
    
    return plan


def create_research_pattern() -> Plan:
    """
    Pattern: Research and Compare
    
    Use case: "Find the best restaurant", "Compare options for X"
    Structure: Branching with multiple research paths
    """
    
    root = Goal(
        id="research_root",
        description="Research topic and provide recommendation",
        goal_type=GoalType.LINEAR,
        target_outcome="Well-researched recommendation with rationale"
    )
    
    plan = Plan(
        id="pattern_research",
        root_goal_id=root.id,
        description="Research and comparison pattern",
        tags=["research", "comparison", "recommendation"]
    )
    
    plan.add_goal(root)
    
    # Step 1: Understand requirements
    step1 = Goal(
        id="research_step1",
        description="Clarify requirements and constraints",
        goal_type=GoalType.ONE_SHOT,
        prompt_template="Extract key requirements: budget, preferences, constraints, priorities",
        parent_id=root.id,
        plan_id=plan.id
    )
    step1.estimate_cost(CostType.TIME, 2.0)
    root.add_child(step1)
    plan.add_goal(step1)
    
    # Step 2: Gather options (branching)
    step2 = Goal(
        id="research_step2",
        description="Gather options from multiple sources",
        goal_type=GoalType.PARALLEL,
        parent_id=root.id,
        plan_id=plan.id
    )
    step2.estimate_cost(CostType.TIME, 10.0)
    root.add_child(step2)
    plan.add_goal(step2)
    
    # Sub-steps for gathering
    source1 = Goal(
        id="research_source1",
        description="Search primary source",
        goal_type=GoalType.ONE_SHOT,
        prompt_template="Search for options matching requirements",
        parent_id=step2.id,
        plan_id=plan.id
    )
    step2.add_child(source1)
    plan.add_goal(source1)
    
    source2 = Goal(
        id="research_source2",
        description="Check user preferences and history",
        goal_type=GoalType.ONE_SHOT,
        prompt_template="Review user's past choices and stated preferences",
        parent_id=step2.id,
        plan_id=plan.id
    )
    step2.add_child(source2)
    plan.add_goal(source2)
    
    # Step 3: Filter and rank
    step3 = Goal(
        id="research_step3",
        description="Filter options and rank by fit",
        goal_type=GoalType.ONE_SHOT,
        prompt_template="Filter options by hard requirements, then rank by preference match",
        parent_id=root.id,
        plan_id=plan.id
    )
    step3.estimate_cost(CostType.TIME, 5.0)
    root.add_child(step3)
    plan.add_goal(step3)
    
    # Step 4: Present top recommendations
    step4 = Goal(
        id="research_step4",
        description="Present top 3 recommendations with rationale",
        goal_type=GoalType.ONE_SHOT,
        prompt_template="Format top 3 options with pros/cons and recommendation",
        parent_id=root.id,
        plan_id=plan.id
    )
    step4.estimate_cost(CostType.TIME, 3.0)
    root.add_child(step4)
    plan.add_goal(step4)
    
    root.estimate_cost(CostType.TIME, 20.0)
    root.cost_analysis.estimated_benefits["informed_decision"] = 1.0
    
    plan.success = True
    plan.status = GoalStatus.COMPLETED
    plan.evaluation_score = 0.88
    plan.compute_signature()
    
    return plan


def create_meeting_prep_pattern() -> Plan:
    """
    Pattern: Meeting Preparation
    
    Use case: "Prepare for tomorrow's meeting", "Get ready for X"
    Structure: Parallel tasks with final synthesis
    """
    
    root = Goal(
        id="meeting_root",
        description="Prepare for meeting",
        goal_type=GoalType.LINEAR,
        target_outcome="Fully prepared for meeting with all materials"
    )
    
    plan = Plan(
        id="pattern_meeting_prep",
        root_goal_id=root.id,
        description="Meeting preparation pattern",
        tags=["meeting", "preparation", "organization"]
    )
    
    plan.add_goal(root)
    
    # Step 1: Get meeting details
    step1 = Goal(
        id="meeting_step1",
        description="Retrieve meeting details from calendar",
        goal_type=GoalType.ONE_SHOT,
        prompt_template="Find meeting in calendar and extract: time, location, attendees, agenda",
        parent_id=root.id,
        plan_id=plan.id
    )
    step1.estimate_cost(CostType.TIME, 2.0)
    root.add_child(step1)
    plan.add_goal(step1)
    
    # Step 2: Parallel preparation tasks
    step2 = Goal(
        id="meeting_step2",
        description="Execute preparation tasks",
        goal_type=GoalType.PARALLEL,
        parent_id=root.id,
        plan_id=plan.id
    )
    step2.estimate_cost(CostType.TIME, 15.0)
    root.add_child(step2)
    plan.add_goal(step2)
    
    # Sub-task: Gather documents
    task1 = Goal(
        id="meeting_task1",
        description="Gather relevant documents",
        goal_type=GoalType.ONE_SHOT,
        prompt_template="Search for documents related to meeting topic",
        parent_id=step2.id,
        plan_id=plan.id
    )
    step2.add_child(task1)
    plan.add_goal(task1)
    
    # Sub-task: Review attendees
    task2 = Goal(
        id="meeting_task2",
        description="Review attendee information",
        goal_type=GoalType.ONE_SHOT,
        prompt_template="Retrieve contact info and notes for each attendee",
        parent_id=step2.id,
        plan_id=plan.id
    )
    step2.add_child(task2)
    plan.add_goal(task2)
    
    # Sub-task: Prepare talking points
    task3 = Goal(
        id="meeting_task3",
        description="Prepare key talking points",
        goal_type=GoalType.ONE_SHOT,
        prompt_template="Draft 3-5 key points to cover based on agenda",
        parent_id=step2.id,
        plan_id=plan.id
    )
    step2.add_child(task3)
    plan.add_goal(task3)
    
    # Step 3: Compile prep package
    step3 = Goal(
        id="meeting_step3",
        description="Compile preparation package",
        goal_type=GoalType.ONE_SHOT,
        prompt_template="Organize all materials into structured prep document",
        parent_id=root.id,
        plan_id=plan.id
    )
    step3.estimate_cost(CostType.TIME, 3.0)
    root.add_child(step3)
    plan.add_goal(step3)
    
    root.estimate_cost(CostType.TIME, 20.0)
    root.cost_analysis.estimated_benefits["meeting_success"] = 1.0
    root.cost_analysis.estimated_benefits["confidence"] = 1.0
    
    plan.success = True
    plan.status = GoalStatus.COMPLETED
    plan.evaluation_score = 0.90
    plan.compute_signature()
    
    return plan


def create_decision_pattern() -> Plan:
    """
    Pattern: Decision Making
    
    Use case: "Should I X or Y?", "Help me decide"
    Structure: Branching with pros/cons analysis
    """
    
    root = Goal(
        id="decision_root",
        description="Analyze decision and provide recommendation",
        goal_type=GoalType.LINEAR,
        target_outcome="Clear recommendation with supporting rationale"
    )
    
    plan = Plan(
        id="pattern_decision",
        root_goal_id=root.id,
        description="Decision analysis pattern",
        tags=["decision", "analysis", "recommendation"]
    )
    
    plan.add_goal(root)
    
    # Step 1: Clarify options
    step1 = Goal(
        id="decision_step1",
        description="Clarify all available options",
        goal_type=GoalType.ONE_SHOT,
        prompt_template="List all distinct options under consideration",
        parent_id=root.id,
        plan_id=plan.id
    )
    step1.estimate_cost(CostType.TIME, 2.0)
    root.add_child(step1)
    plan.add_goal(step1)
    
    # Step 2: Define criteria
    step2 = Goal(
        id="decision_step2",
        description="Define decision criteria",
        goal_type=GoalType.ONE_SHOT,
        prompt_template="Extract what matters: priorities, constraints, values",
        parent_id=root.id,
        plan_id=plan.id
    )
    step2.estimate_cost(CostType.TIME, 3.0)
    root.add_child(step2)
    plan.add_goal(step2)
    
    # Step 3: Analyze each option
    step3 = Goal(
        id="decision_step3",
        description="Analyze pros and cons of each option",
        goal_type=GoalType.BRANCHING,
        parent_id=root.id,
        plan_id=plan.id
    )
    step3.estimate_cost(CostType.TIME, 10.0)
    root.add_child(step3)
    plan.add_goal(step3)
    
    # Branch for each option (template)
    analysis1 = Goal(
        id="decision_analysis",
        description="Analyze option against criteria",
        goal_type=GoalType.ONE_SHOT,
        prompt_template="List pros, cons, risks, and benefits for this option",
        parent_id=step3.id,
        plan_id=plan.id
    )
    step3.add_child(analysis1)
    plan.add_goal(analysis1)
    
    # Step 4: Score and compare
    step4 = Goal(
        id="decision_step4",
        description="Score options and compare",
        goal_type=GoalType.ONE_SHOT,
        prompt_template="Score each option on key criteria (0-10) and calculate weighted totals",
        parent_id=root.id,
        plan_id=plan.id
    )
    step4.estimate_cost(CostType.TIME, 5.0)
    root.add_child(step4)
    plan.add_goal(step4)
    
    # Step 5: Recommend
    step5 = Goal(
        id="decision_step5",
        description="Make recommendation",
        goal_type=GoalType.ONE_SHOT,
        prompt_template="Recommend best option with clear rationale and confidence level",
        parent_id=root.id,
        plan_id=plan.id
    )
    step5.estimate_cost(CostType.TIME, 3.0)
    root.add_child(step5)
    plan.add_goal(step5)
    
    root.estimate_cost(CostType.TIME, 23.0)
    root.cost_analysis.estimated_benefits["decision_quality"] = 1.0
    
    plan.success = True
    plan.status = GoalStatus.COMPLETED
    plan.evaluation_score = 0.85
    plan.compute_signature()
    
    return plan


def load_example_patterns(planner_dir: Path):
    """
    Load all example patterns into the planner's pattern library.
    
    Usage:
        from example_patterns import load_example_patterns
        load_example_patterns(STATE_DIR / "planner")
    """
    
    patterns = [
        create_scheduling_pattern(),
        create_research_pattern(),
        create_meeting_prep_pattern(),
        create_decision_pattern()
    ]
    
    patterns_dir = planner_dir / "patterns"
    patterns_dir.mkdir(parents=True, exist_ok=True)
    
    for pattern in patterns:
        pattern_file = patterns_dir / f"{pattern.pattern_signature or pattern.id}.json"
        with open(pattern_file, 'w') as f:
            json.dump(pattern.to_dict(), f, indent=2)
        
        print(f"✅ Loaded pattern: {pattern.description} (signature: {pattern.pattern_signature})")
    
    print(f"\n✅ Loaded {len(patterns)} example patterns into {patterns_dir}")


if __name__ == "__main__":
    """
    Run this to initialize pattern library:
    
        python example_patterns.py
    """
    
    from pathlib import Path
    import os
    
    JARVIS_ROOT = Path(os.path.expanduser("~/jarvis"))
    planner_dir = JARVIS_ROOT / "state" / "planner"
    
    print("\n" + "=" * 60)
    print("Loading Example Patterns into JARVIS")
    print("=" * 60 + "\n")
    
    load_example_patterns(planner_dir)
    
    print("\n" + "=" * 60)
    print("Patterns ready! Start JARVIS to use them.")
    print("=" * 60)