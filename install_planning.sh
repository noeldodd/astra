#!/bin/bash
# install_planning.sh
# Quick installation script for JARVIS Planning System

set -e  # Exit on error

echo ""
echo "=========================================================="
echo "  JARVIS Planning System - Installation"
echo "=========================================================="
echo ""

# Check if running from correct directory
if [ ! -f "jarvis_core.py" ]; then
    echo "❌ Error: Must run from JARVIS directory containing jarvis_core.py"
    exit 1
fi

# Backup existing files
echo "📦 Backing up existing files..."
BACKUP_DIR="backup_$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

if [ -f "jarvis_core.py" ]; then
    cp jarvis_core.py "$BACKUP_DIR/"
    echo "  ✅ Backed up jarvis_core.py"
fi

# Check if new files are present
echo ""
echo "📋 Checking for new files..."

if [ ! -f "jarvis_planner.py" ]; then
    echo "❌ Error: jarvis_planner.py not found"
    echo "   Please place jarvis_planner.py in this directory first"
    exit 1
fi
echo "  ✅ Found jarvis_planner.py"

if [ ! -f "example_patterns.py" ]; then
    echo "❌ Error: example_patterns.py not found"
    echo "   Please place example_patterns.py in this directory first"
    exit 1
fi
echo "  ✅ Found example_patterns.py"

# Create directories
echo ""
echo "📁 Creating directories..."
mkdir -p ~/jarvis/state/planner/plans
mkdir -p ~/jarvis/state/planner/patterns
echo "  ✅ Directories created"

# Install new core (if you have the updated file)
echo ""
echo "📝 Installing updated files..."
# Note: User should manually update jarvis_core.py from the artifact
echo "  ⚠️  Remember to update jarvis_core.py with the new version!"
echo "  (Copy from the artifact provided)"

# Load example patterns
echo ""
echo "🎯 Loading example patterns..."
python3 example_patterns.py

if [ $? -eq 0 ]; then
    echo "  ✅ Patterns loaded successfully"
else
    echo "  ❌ Pattern loading failed"
    exit 1
fi

# Test imports
echo ""
echo "🧪 Testing imports..."
python3 -c "from jarvis_planner import GoalPlanner, Goal, Plan" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "  ✅ jarvis_planner imports successfully"
else
    echo "  ❌ jarvis_planner import failed"
    exit 1
fi

# Summary
echo ""
echo "=========================================================="
echo "  ✅ Installation Complete!"
echo "=========================================================="
echo ""
echo "📦 Backup saved to: $BACKUP_DIR/"
echo "🎯 Patterns loaded: ~/jarvis/state/planner/patterns/"
echo ""
echo "Next steps:"
echo "  1. Review and update jarvis_core.py with new version"
echo "  2. Start JARVIS: python jarvis_core.py"
echo "  3. Connect terminal: python jarvis_terminal.py"
echo "  4. Test planning: 'Help me plan tomorrow'"
echo "  5. View patterns: 'Analysis' → 'patterns'"
echo ""
echo "See Planning_Test_Guide for detailed testing instructions"
echo "=========================================================="
echo ""