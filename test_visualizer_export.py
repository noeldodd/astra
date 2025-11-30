#!/usr/bin/env python3
"""
Test script to validate visualizer JSON export format
Creates a sample plan and exports it to visualizer format
"""

import json
from pathlib import Path
from jarvis_planner import GoalPlanner, Goal, Plan, GoalType, CostType

def create_sample_plan() -> Plan:
    """Create a sample plan for testing"""
    
    # Root goal
    root = Goal(
        id="root",
        description="Find the best Italian restaurant nearby",
        goal_type=GoalType.LINEAR,
        target_outcome="Top 3 restaurant recommendations"
    )
    
    plan = Plan(
        id="sample_plan",
        root_goal_id=root.id,
        description="Restaurant research plan"
    )
    
    plan.add_goal(root)
    
    # Step 1: Search
    step1 = Goal(
        id="step_1",
        description="Search for Italian restaurants in user's area",
        goal_type=GoalType.ONE_SHOT,
        parent_id=root.id,
        plan_id=plan.id
    )
    step1.estimate_cost(CostType.TIME, 5.0)
    root.add_child(step1)
    plan.add_goal(step1)
    
    # Step 2: Filter (branches)
    step2 = Goal(
        id="step_2",
        description="Filter restaurants by criteria",
        goal_type=GoalType.BRANCHING,
        parent_id=root.id,
        plan_id=plan.id
    )
    step2.estimate_cost(CostType.TIME, 8.0)
    root.add_child(step2)
    plan.add_goal(step2)
    
    # Step 2a: By rating
    step2a = Goal(
        id="step_2a",
        description="Filter by minimum 4-star rating",
        goal_type=GoalType.ONE_SHOT,
        parent_id=step2.id,
        plan_id=plan.id
    )
    step2.add_child(step2a)
    plan.add_goal(step2a)
    
    # Step 2b: By price
    step2b = Goal(
        id="step_2b",
        description="Filter by budget constraints",
        goal_type=GoalType.ONE_SHOT,
        parent_id=step2.id,
        plan_id=plan.id
    )
    step2.add_child(step2b)
    plan.add_goal(step2b)
    
    # Step 2c: By distance
    step2c = Goal(
        id="step_2c",
        description="Filter by proximity to user location",
        goal_type=GoalType.ONE_SHOT,
        parent_id=step2.id,
        plan_id=plan.id
    )
    step2.add_child(step2c)
    plan.add_goal(step2c)
    
    # Step 3: Rank
    step3 = Goal(
        id="step_3",
        description="Rank remaining options by user preferences",
        goal_type=GoalType.ONE_SHOT,
        parent_id=root.id,
        plan_id=plan.id
    )
    step3.estimate_cost(CostType.TIME, 3.0)
    root.add_child(step3)
    plan.add_goal(step3)
    
    # Step 4: Present
    step4 = Goal(
        id="step_4",
        description="Present top 3 recommendations with rationale",
        goal_type=GoalType.ONE_SHOT,
        parent_id=root.id,
        plan_id=plan.id
    )
    step4.estimate_cost(CostType.TIME, 2.0)
    root.add_child(step4)
    plan.add_goal(step4)
    
    return plan


def validate_json_format(data: dict) -> list[str]:
    """Validate exported JSON matches visualizer requirements"""
    
    errors = []
    
    # Check top-level structure
    if "steps" not in data:
        errors.append("Missing 'steps' array")
        return errors
    
    if not isinstance(data["steps"], list):
        errors.append("'steps' must be an array")
        return errors
    
    # Check each step
    required_fields = ["id", "prompt", "type", "children", "fingerprint"]
    required_fingerprint_dims = [
        "intent", "domain", "complexity", "outputType",
        "specificity", "timeHorizon", "interactivity"
    ]
    
    for i, step in enumerate(data["steps"]):
        # Check required fields
        for field in required_fields:
            if field not in step:
                errors.append(f"Step {i} missing required field: {field}")
        
        # Check type enum
        if "type" in step and step["type"] not in ["one-shot", "linear", "branching"]:
            errors.append(f"Step {i} has invalid type: {step['type']}")
        
        # Check children is array
        if "children" in step and not isinstance(step["children"], list):
            errors.append(f"Step {i} 'children' must be an array")
        
        # Check fingerprint dimensions
        if "fingerprint" in step:
            fp = step["fingerprint"]
            for dim in required_fingerprint_dims:
                if dim not in fp:
                    errors.append(f"Step {i} fingerprint missing dimension: {dim}")
                elif not isinstance(fp[dim], (int, float)):
                    errors.append(f"Step {i} fingerprint.{dim} must be numeric")
                elif not (0.0 <= fp[dim] <= 1.0):
                    errors.append(f"Step {i} fingerprint.{dim} must be 0.0-1.0, got {fp[dim]}")
        
        # Check type matches children count
        if "type" in step and "children" in step:
            num_children = len(step["children"])
            expected_type = (
                "one-shot" if num_children == 0 else
                "linear" if num_children == 1 else
                "branching"
            )
            if step["type"] != expected_type:
                errors.append(
                    f"Step {i} type '{step['type']}' doesn't match {num_children} children "
                    f"(expected '{expected_type}')"
                )
    
    return errors


def main():
    print("\n" + "=" * 60)
    print("Testing Visualizer JSON Export")
    print("=" * 60 + "\n")
    
    # Create sample plan
    print("1. Creating sample plan...")
    plan = create_sample_plan()
    print(f"   ✅ Created plan with {len(plan.goals)} goals")
    
    # Export to JSON
    print("\n2. Exporting to visualizer format...")
    data = plan.to_visualizer_json()
    print(f"   ✅ Exported {len(data['steps'])} steps")
    
    # Show structure
    print("\n3. Plan structure:")
    root = plan.get_root_goal()
    if root:
        def show_tree(goal_id: str, indent: int = 0):
            goal = plan.get_goal(goal_id)
            if not goal:
                return
            
            type_emoji = {
                GoalType.ONE_SHOT: "🔵",
                GoalType.LINEAR: "🟢",
                GoalType.BRANCHING: "🟠",
                GoalType.PARALLEL: "🟣"
            }
            
            print(f"   {'  ' * indent}{type_emoji.get(goal.goal_type, '⚪')} {goal.description}")
            for child_id in goal.children:
                show_tree(child_id, indent + 1)
        
        show_tree(root.id)
    
    # Validate format
    print("\n4. Validating JSON format...")
    errors = validate_json_format(data)
    
    if errors:
        print("   ❌ Validation errors:")
        for error in errors:
            print(f"      - {error}")
    else:
        print("   ✅ JSON format valid")
    
    # Show fingerprint dimensions
    print("\n5. Sample fingerprint (step_1):")
    if data["steps"]:
        fp = data["steps"][0]["fingerprint"]
        for dim, value in fp.items():
            bar = "█" * int(value * 20)
            print(f"   {dim:15s} {value:.2f} {bar}")
    
    # Save to file
    print("\n6. Saving to file...")
    output_file = Path("sample_plan_visualizer.json")
    with open(output_file, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"   ✅ Saved to: {output_file}")
    
    # Show file info
    file_size = output_file.stat().st_size
    print(f"   📊 File size: {file_size} bytes")
    
    print("\n" + "=" * 60)
    print("✅ Test Complete!")
    print("=" * 60)
    print(f"\nLoad {output_file} in the visualizer to see the 3D structure")
    print()


if __name__ == "__main__":
    main()