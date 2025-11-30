#!/usr/bin/env python3
"""
Debug tool to inspect and test pattern matching
"""

import json
from pathlib import Path
import os

JARVIS_ROOT = Path(os.path.expanduser("~/jarvis"))
PATTERNS_DIR = JARVIS_ROOT / "state" / "planner" / "patterns"

def inspect_patterns():
    """Show all patterns with details"""
    
    print("\n" + "=" * 60)
    print("JARVIS Pattern Library Inspector")
    print("=" * 60 + "\n")
    
    if not PATTERNS_DIR.exists():
        print("❌ Patterns directory not found:", PATTERNS_DIR)
        return
    
    pattern_files = list(PATTERNS_DIR.glob("*.json"))
    
    if not pattern_files:
        print("📋 No patterns found")
        print("Run: python example_patterns.py")
        return
    
    print(f"Found {len(pattern_files)} patterns:\n")
    
    for i, pattern_file in enumerate(pattern_files, 1):
        with open(pattern_file) as f:
            pattern = json.load(f)
        
        print(f"{i}. Pattern: {pattern.get('description', 'Unknown')}")
        print(f"   ID: {pattern.get('id', 'N/A')}")
        print(f"   Signature: {pattern.get('pattern_signature', 'N/A')}")
        print(f"   Tags: {', '.join(pattern.get('tags', []))}")
        print(f"   Score: {pattern.get('evaluation_score', 0):.2f}")
        print(f"   Goals: {len(pattern.get('goals', {}))}")
        
        # Show goal structure
        root_id = pattern.get('root_goal_id')
        if root_id:
            goals = pattern.get('goals', {})
            root = goals.get(root_id, {})
            
            print(f"   Structure:")
            print(f"     Root: {root.get('description', 'Unknown')} [{root.get('goal_type', 'unknown')}]")
            
            for child_id in root.get('children', []):
                child = goals.get(child_id, {})
                print(f"       → {child.get('description', 'Unknown')}")
        
        print()
    
    print("=" * 60)


def test_matching(query: str):
    """Test which pattern would match a query"""
    
    print("\n" + "=" * 60)
    print(f"Testing query: '{query}'")
    print("=" * 60 + "\n")
    
    if not PATTERNS_DIR.exists():
        print("❌ Patterns directory not found")
        return
    
    pattern_files = list(PATTERNS_DIR.glob("*.json"))
    
    if not pattern_files:
        print("📋 No patterns to match against")
        return
    
    query_lower = query.lower()
    matches = []
    
    for pattern_file in pattern_files:
        with open(pattern_file) as f:
            pattern = json.load(f)
        
        # Check tag matching
        tags = pattern.get('tags', [])
        matching_tags = [tag for tag in tags if tag in query_lower]
        
        if matching_tags:
            matches.append({
                'pattern': pattern,
                'matching_tags': matching_tags,
                'score': pattern.get('evaluation_score', 0)
            })
    
    if matches:
        print(f"Found {len(matches)} potential matches:\n")
        
        matches.sort(key=lambda x: x['score'], reverse=True)
        
        for i, match in enumerate(matches, 1):
            pattern = match['pattern']
            print(f"{i}. {pattern.get('description', 'Unknown')}")
            print(f"   Matched tags: {', '.join(match['matching_tags'])}")
            print(f"   Score: {match['score']:.2f}")
            print(f"   Signature: {pattern.get('pattern_signature', 'N/A')}")
            print()
    else:
        print("❌ No matching patterns found")
        print("\nPattern tags available:")
        
        all_tags = set()
        for pattern_file in pattern_files:
            with open(pattern_file) as f:
                pattern = json.load(f)
                all_tags.update(pattern.get('tags', []))
        
        for tag in sorted(all_tags):
            print(f"  - {tag}")
    
    print("=" * 60)


def clear_patterns():
    """Clear all patterns (use with caution!)"""
    
    print("\n⚠️  WARNING: This will delete all patterns!")
    confirm = input("Type 'yes' to confirm: ")
    
    if confirm.lower() != 'yes':
        print("Cancelled")
        return
    
    if not PATTERNS_DIR.exists():
        print("No patterns directory found")
        return
    
    pattern_files = list(PATTERNS_DIR.glob("*.json"))
    
    for pattern_file in pattern_files:
        pattern_file.unlink()
        print(f"  Deleted: {pattern_file.name}")
    
    print(f"\n✅ Cleared {len(pattern_files)} patterns")
    print("Run 'python example_patterns.py' to reload defaults")


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) == 1:
        # No arguments - show all patterns
        inspect_patterns()
    
    elif sys.argv[1] == "test":
        # Test pattern matching
        if len(sys.argv) < 3:
            print("Usage: python debug_patterns.py test 'your query here'")
            sys.exit(1)
        
        query = " ".join(sys.argv[2:])
        test_matching(query)
    
    elif sys.argv[1] == "clear":
        # Clear all patterns
        clear_patterns()
    
    else:
        print("Usage:")
        print("  python debug_patterns.py              # List all patterns")
        print("  python debug_patterns.py test 'query' # Test pattern matching")
        print("  python debug_patterns.py clear        # Clear all patterns")