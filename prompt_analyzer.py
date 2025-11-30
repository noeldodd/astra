# prompt_analyzer.py
"""
JARVIS Prompt Analyzer

LLM-assisted prompt improvement system.
Implements 3 phases:
- Phase 1: Analysis & suggestions
- Phase 2: Interactive refinement
- Phase 3: A/B testing framework
"""

import json
from datetime import datetime
from typing import Optional, Dict, List, Any
from pathlib import Path


class PromptAnalyzer:
    """
    Analyzes prompts and suggests improvements using LLM.
    
    Features:
    - Performance data analysis
    - Failure pattern detection
    - LLM-assisted suggestion generation
    - Interactive refinement
    - Version tracking and rollback
    """
    
    def __init__(self, jarvis_core):
        """
        Initialize with reference to JarvisCore
        
        Args:
            jarvis_core: Main JARVIS instance for accessing state
        """
        self.core = jarvis_core
        self.analysis_history = []
        self.version_history = {}
    
    # ==================== PHASE 1: ANALYSIS & SUGGESTIONS ====================
    
    async def analyze_and_improve(
        self,
        prompt_id: str,
        user_feedback: Optional[str] = None
    ) -> str:
        """
        Phase 1: Analyze a prompt and suggest improvements
        
        Args:
            prompt_id: ID of prompt to analyze
            user_feedback: Optional user description of issues
            
        Returns:
            Formatted analysis and suggestions
        """
        
        # Get current prompt
        current_prompt = self._get_current_prompt(prompt_id)
        if not current_prompt:
            return f"❌ Prompt '{prompt_id}' not found"
        
        # Check if prompt can be modified
        if current_prompt.get("immutable", True):
            return f"❌ Prompt '{prompt_id}' is immutable and cannot be modified"
        
        # Gather performance data
        perf_data = self._gather_performance_data(prompt_id)
        
        # Gather failure examples
        failures = self._gather_recent_failures(prompt_id)
        
        # Generate analysis using LLM
        self.core._log("ANALYSIS", f"Analyzing prompt '{prompt_id}' with LLM...")
        
        analysis = await self._llm_analyze_prompt(
            prompt_id=prompt_id,
            current_text=current_prompt.get("template", ""),
            performance=perf_data,
            failures=failures,
            user_feedback=user_feedback
        )
        
        if not analysis:
            return "❌ Failed to generate analysis"
        
        # Format and present results
        return self._format_analysis_results(prompt_id, analysis)
    
    async def _llm_analyze_prompt(
        self,
        prompt_id: str,
        current_text: str,
        performance: Dict,
        failures: List[Dict],
        user_feedback: Optional[str]
    ) -> Optional[Dict]:
        """
        Use LLM to analyze prompt and suggest improvements
        
        Returns:
            Dict with analysis, issues, proposed_changes, etc.
        """
        
        meta_prompt = f"""You are a prompt engineering assistant for JARVIS.

CURRENT PROMPT: {prompt_id}
Version: {performance.get('version', 'N/A')}
Type: {self._get_prompt_type(prompt_id)}

CURRENT TEXT:
────────────────
{current_text[:500]}...
────────────────

PERFORMANCE DATA:
- Total executions: {performance.get('total_calls', 0)}
- Success rate: {performance.get('success_rate', 0):.1%}
- Average tokens: {performance.get('avg_tokens', 0):.0f}
- Average time: {performance.get('avg_time_ms', 0):.0f}ms

RECENT ISSUES:
{self._format_failures(failures)}

USER FEEDBACK:
{user_feedback or 'No specific feedback provided'}

TASK: Analyze this prompt and suggest specific improvements.

Consider:
1. Are instructions clear and unambiguous?
2. Does it handle edge cases well?
3. Are examples representative and helpful?
4. Is the JSON schema enforced properly?
5. Are there patterns in the failures?
6. Can the prompt be more concise without losing effectiveness?

Respond with JSON:
{{
  "analysis": "What's working and what's not (2-3 sentences)",
  "issues_identified": [
    {{"issue": "description", "severity": "high|medium|low", "frequency": "often|sometimes|rare"}}
  ],
  "proposed_changes": [
    {{
      "section": "instructions|examples|schema|other",
      "change_type": "add|remove|modify",
      "original": "text to replace (if modify, first 50 chars)",
      "new": "new text to add/replace",
      "reasoning": "why this helps (1 sentence)",
      "impact": "what should improve"
    }}
  ],
  "expected_improvement": "Overall expected outcome",
  "risks": ["potential downsides"],
  "confidence": 0.0-1.0
}}
"""
        
        result = await self.core.prompt_manager.execute_prompt(
            prompt_text=meta_prompt,
            prompt_id="analyze_prompt_meta",
            use_smart_model=True,
            max_tokens=1000
        )
        
        if result.success and result.parsed_json:
            # Store in history
            self.analysis_history.append({
                "prompt_id": prompt_id,
                "timestamp": datetime.now().isoformat(),
                "user_feedback": user_feedback,
                "analysis": result.parsed_json
            })
            
            return result.parsed_json
        
        return None
    
    def _format_analysis_results(self, prompt_id: str, analysis: Dict) -> str:
        """Format analysis results for display"""
        
        lines = [
            f"📊 PROMPT ANALYSIS: {prompt_id}",
            "═" * 60,
            "",
            "🔍 Analysis:",
            analysis.get("analysis", "No analysis provided"),
            "",
            f"⚠️  Issues Identified ({len(analysis.get('issues_identified', []))}):"
        ]
        
        for i, issue in enumerate(analysis.get("issues_identified", []), 1):
            severity = issue.get("severity", "unknown")
            freq = issue.get("frequency", "unknown")
            emoji = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(severity, "⚪")
            lines.append(f"  {i}. {emoji} [{freq}] {issue.get('issue', 'Unknown')}")
        
        lines.append("")
        lines.append(f"💡 Proposed Changes ({len(analysis.get('proposed_changes', []))}):")
        
        for i, change in enumerate(analysis.get("proposed_changes", []), 1):
            change_type = change.get("change_type", "unknown")
            section = change.get("section", "unknown")
            lines.append(f"\n  Change {i}: [{change_type.upper()}] in {section}")
            lines.append(f"  Reasoning: {change.get('reasoning', 'N/A')}")
            lines.append(f"  Impact: {change.get('impact', 'N/A')}")
            
            if change.get("original"):
                lines.append(f"  Original: {change['original'][:80]}...")
            if change.get("new"):
                lines.append(f"  New: {change['new'][:80]}...")
        
        lines.extend([
            "",
            f"✨ Expected Improvement:",
            analysis.get("expected_improvement", "N/A"),
            "",
            f"📈 Confidence: {analysis.get('confidence', 0):.0%}",
            ""
        ])
        
        if analysis.get("risks"):
            lines.append("⚠️  Risks:")
            for risk in analysis["risks"]:
                lines.append(f"  - {risk}")
            lines.append("")
        
        lines.extend([
            "─" * 60,
            "Next Steps:",
            f"  refine prompt {prompt_id}     - Interactive refinement (Phase 2)",
            f"  apply {prompt_id}            - Apply all suggested changes",
            f"  prompt {prompt_id}           - View current prompt",
            ""
        ])
        
        return "\n".join(lines)
    
    # ==================== PHASE 2: INTERACTIVE REFINEMENT ====================
    
    async def interactive_refinement(
        self,
        prompt_id: str,
        terminal_id: int
    ) -> str:
        """
        Phase 2: Interactive conversational refinement
        
        This would be called from Analysis mode when user types:
        refine prompt <id>
        
        Returns initial message to start conversation
        """
        
        # Get latest analysis
        latest_analysis = self._get_latest_analysis(prompt_id)
        
        if not latest_analysis:
            return f"No analysis found for '{prompt_id}'. Run 'analyze prompt {prompt_id}' first."
        
        # Start refinement session
        session = {
            "prompt_id": prompt_id,
            "terminal_id": terminal_id,
            "started_at": datetime.now().isoformat(),
            "analysis": latest_analysis,
            "changes_made": [],
            "state": "intro"
        }
        
        # Store session (would need session management in core)
        # For now, return intro message
        
        issues = latest_analysis.get("issues_identified", [])
        changes = latest_analysis.get("proposed_changes", [])
        
        intro = f"""
🔧 INTERACTIVE PROMPT REFINEMENT: {prompt_id}
═══════════════════════════════════════════════════════

I've analyzed the '{prompt_id}' prompt and found {len(issues)} issues
with {len(changes)} suggested improvements.

What would you like to focus on?

1. Address specific issues ({len([i for i in issues if i.get('severity') == 'high'])} high priority)
2. Apply all suggested changes at once
3. Make custom changes (guided)
4. Cancel

Reply with a number (1-4)
"""
        
        return intro
    
    # ==================== PHASE 3: A/B TESTING ====================
    
    def track_performance(self, prompt_id: str, execution_data: Dict):
        """
        Phase 3: Track prompt performance for A/B testing
        
        Args:
            prompt_id: Prompt being tracked
            execution_data: Result of execution (success, time, tokens, etc.)
        """
        
        # Initialize tracking if needed
        if prompt_id not in self.version_history:
            self.version_history[prompt_id] = {
                "current_version": self._get_prompt_version(prompt_id),
                "executions": [],
                "metrics": {
                    "success_count": 0,
                    "failure_count": 0,
                    "total_time_ms": 0,
                    "total_tokens": 0
                }
            }
        
        # Record execution
        history = self.version_history[prompt_id]
        history["executions"].append({
            "timestamp": datetime.now().isoformat(),
            "success": execution_data.get("success", False),
            "time_ms": execution_data.get("elapsed_ms", 0),
            "tokens": execution_data.get("tokens", 0),
            "error": execution_data.get("error")
        })
        
        # Update metrics
        if execution_data.get("success"):
            history["metrics"]["success_count"] += 1
        else:
            history["metrics"]["failure_count"] += 1
        
        history["metrics"]["total_time_ms"] += execution_data.get("elapsed_ms", 0)
        history["metrics"]["total_tokens"] += execution_data.get("tokens", 0)
        
        # Check if performance has degraded
        self._check_performance_degradation(prompt_id)
    
    def _check_performance_degradation(self, prompt_id: str):
        """Check if recent performance has degraded compared to baseline"""
        
        history = self.version_history.get(prompt_id)
        if not history or len(history["executions"]) < 20:
            return  # Need more data
        
        # Compare recent 10 vs previous 10
        recent = history["executions"][-10:]
        previous = history["executions"][-20:-10]
        
        recent_success = sum(1 for e in recent if e.get("success", False)) / 10
        previous_success = sum(1 for e in previous if e.get("success", False)) / 10
        
        if recent_success < previous_success - 0.15:  # 15% drop
            self.core._log("ANALYSIS", f"⚠️  Performance degradation detected for prompt '{prompt_id}'")
            self.core._log("ANALYSIS", f"   Success rate: {previous_success:.1%} → {recent_success:.1%}")
            
            # Could auto-rollback here in Phase 3
            # For now, just log the warning
    
    # ==================== HELPER METHODS ====================
    
    def _get_current_prompt(self, prompt_id: str) -> Optional[Dict]:
        """Get current prompt (runtime override or boot)"""
        if prompt_id in self.core.runtime_prompts:
            return self.core.runtime_prompts[prompt_id]
        elif prompt_id in self.core.boot_prompts:
            return self.core.boot_prompts[prompt_id]
        return None
    
    def _get_prompt_version(self, prompt_id: str) -> int:
        """Get current version number of prompt"""
        prompt = self._get_current_prompt(prompt_id)
        return prompt.get("version", 1) if prompt else 1
    
    def _get_prompt_type(self, prompt_id: str) -> str:
        """Get description of what the prompt does"""
        type_map = {
            "classify_intent": "Intent classification",
            "decompose_task": "Goal decomposition",
            "generate_self_task": "Self-task generation"
        }
        return type_map.get(prompt_id, "Unknown")
    
    def _gather_performance_data(self, prompt_id: str) -> Dict:
        """Gather performance statistics for a prompt"""
        
        if not self.core.prompt_manager:
            return {"total_calls": 0}
        
        stats = self.core.prompt_manager.execution_stats
        prompt_stats = stats.get("by_prompt", {}).get(prompt_id, {})
        
        total_calls = prompt_stats.get("calls", 0)
        
        return {
            "version": self._get_prompt_version(prompt_id),
            "total_calls": total_calls,
            "success_rate": 1.0 - (prompt_stats.get("errors", 0) / max(total_calls, 1)),
            "avg_time_ms": prompt_stats.get("avg_ms", 0),
            "avg_tokens": prompt_stats.get("avg_tokens", 0),
        }
    
    def _gather_recent_failures(self, prompt_id: str) -> List[Dict]:
        """Get recent failures for this prompt"""
        
        # Would need to track failures in core
        # For now, return placeholder
        
        return [
            {
                "timestamp": "2025-11-26 12:00:00",
                "input": "Find the best restaurant",
                "error": "Created 8 steps when 4 would suffice",
                "type": "overcomplexity"
            }
        ]
    
    def _format_failures(self, failures: List[Dict]) -> str:
        """Format failure list for meta-prompt"""
        if not failures:
            return "No recent failures"
        
        lines = []
        for i, fail in enumerate(failures[:5], 1):  # Show max 5
            lines.append(f"{i}. [{fail.get('type', 'unknown')}] {fail.get('error', 'No description')}")
        
        return "\n".join(lines)
    
    def _get_latest_analysis(self, prompt_id: str) -> Optional[Dict]:
        """Get most recent analysis for a prompt"""
        for analysis in reversed(self.analysis_history):
            if analysis["prompt_id"] == prompt_id:
                return analysis["analysis"]
        return None
    
    # ==================== APPLY CHANGES ====================
    
    async def apply_changes(
        self,
        prompt_id: str,
        changes: List[Dict],
        create_backup: bool = True
    ) -> str:
        """
        Apply suggested changes to a prompt
        
        Args:
            prompt_id: Prompt to modify
            changes: List of changes to apply
            create_backup: Whether to backup current version
            
        Returns:
            Status message
        """
        
        current_prompt = self._get_current_prompt(prompt_id)
        if not current_prompt:
            return f"❌ Prompt '{prompt_id}' not found"
        
        current_text = current_prompt.get("template", "")
        
        # Backup current version
        if create_backup:
            self._backup_prompt(prompt_id, current_text)
        
        # Apply changes
        new_text = current_text
        for change in changes:
            if change.get("change_type") == "modify" and change.get("original"):
                new_text = new_text.replace(change["original"], change.get("new", ""))
            elif change.get("change_type") == "add":
                # Would need smarter insertion logic
                new_text += "\n" + change.get("new", "")
        
        # Create runtime override
        new_version = self._get_prompt_version(prompt_id) + 1
        
        self.core.runtime_prompts[prompt_id] = {
            "id": prompt_id,
            "version": new_version,
            "template": new_text,
            "immutable": False,
            "modified_at": datetime.now().isoformat(),
            "changes_applied": len(changes),
            "previous_version": current_prompt.get("version", 1)
        }
        
        self.core._save_runtime_prompts()
        
        return f"""
✅ Applied {len(changes)} changes to '{prompt_id}'

New version: {new_version}
Previous version backed up

Commands:
  prompt {prompt_id}           - View new version
  prompt {prompt_id} reset     - Rollback to previous
  test prompt {prompt_id}      - Test with sample query
"""
    
    def _backup_prompt(self, prompt_id: str, text: str):
        """Backup current prompt version"""
        from jarvis_core import STATE_DIR
        
        backup_dir = STATE_DIR / "prompts" / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"{prompt_id}_{timestamp}.txt"
        
        with open(backup_file, 'w') as f:
            f.write(text)
        
        self.core._log("ANALYSIS", f"Backed up '{prompt_id}' to {backup_file}")