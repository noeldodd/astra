# analysis_commands.py
"""
JARVIS Analysis Mode Commands

Extracted from jarvis_core.py for modularity.
Handles all Analysis mode command processing.
"""

from datetime import datetime as dt
from typing import Optional, Dict, Any
from pathlib import Path


class AnalysisCommands:
    """Handles all Analysis mode commands"""
    
    def __init__(self, jarvis_core):
        """
        Initialize with reference to JarvisCore instance
        
        Args:
            jarvis_core: The main JarvisCore instance for accessing state
        """
        self.core = jarvis_core
    
    async def handle_command(self, command: str) -> str:
        """
        Route and execute analysis commands
        
        Args:
            command: The analysis command to execute
            
        Returns:
            Response string to display to user
        """
        cmd = command.lower().strip()
        
        # Route to appropriate handler
        if cmd == "continue":
            return await self._cmd_continue()
        elif cmd == "status":
            return await self._cmd_status()
        elif cmd == "queue":
            return await self._cmd_queue()
        elif cmd == "plans":
            return await self._cmd_plans()
        elif cmd.startswith("plan "):
            return await self._cmd_plan(cmd)
        elif cmd.startswith("export "):
            return await self._cmd_export(cmd)
        elif cmd == "patterns":
            return await self._cmd_patterns()
        elif cmd == "prompts":
            return await self._cmd_prompts()
        elif cmd.startswith("prompt "):
            return await self._cmd_prompt(cmd)
        elif cmd.startswith("analyze prompt "):
            return await self._cmd_analyze_prompt(cmd)
        elif cmd.startswith("memory"):
            return await self._cmd_memory(cmd)
        elif cmd.startswith("llm"):
            return await self._cmd_llm(cmd)
        elif cmd.startswith("config"):
            return await self._cmd_config(cmd)
        elif cmd == "help":
            return await self._cmd_help()
        elif cmd == "terminals":
            return await self._cmd_terminals()
        elif cmd == "boundaries":
            return await self._cmd_boundaries()
        elif cmd == "memory cleanup" or cmd == "cleanup memory":
            return await self._cmd_memory_cleanup()
        elif cmd == "search" or cmd == "search stats":
            if not self.core.search_provider:
                return "Search not available"
            
            stats = self.core.search_provider.get_stats()
            
            lines = ["🔍 Search Statistics\n"]
            lines.append(f"Total searches: {stats['total_searches']}")
            lines.append(f"Cache hits: {stats['cache_hits']}")
            lines.append(f"Cache hit rate: {stats['cache_hit_rate']:.1%}")
            lines.append(f"Success rate: {stats['success_rate']:.1%}")
            lines.append(f"Average results: {stats['avg_results']:.1f}")
            lines.append(f"Failed searches: {stats['failures']}")
            
            return "\n".join(lines)

        elif cmd.startswith("cleanup duplicates"):
            if "confirm" in cmd:
                return await self._cmd_cleanup_duplicates_confirm()
            else:
                return await self._cmd_cleanup_duplicates()
    
        else:
            return f"Unknown command: {cmd}\nType 'help' for available commands."
    
    # ==================== CORE COMMANDS ====================
    
    async def _cmd_continue(self) -> str:
        """Exit analysis mode"""
        self.core.state = self.core.JarvisState.RUNNING
        self.core.analysis_terminal = None
        self.core._log("ANALYSIS", "Analysis mode deactivated")
        return "▶️ Resuming normal operation..."
    
    async def _cmd_status(self) -> str:
        """Show system status"""
        uptime = dt.now() - self.core.start_time if self.core.start_time else "Unknown"
        active_plan_count = len(self.core.active_plans)
        pattern_count = len(self.core.planner.pattern_library) if self.core.planner else 0
        
        return f"""      
📊 SYSTEM STATUS
════════════════════════════════
State: {self.core.state.name}
Uptime: {uptime}
Tasks Processed: {self.core.tasks_processed}
Queue Depth: {len(self.core.queue)}
Active Terminals: {len([t for t in self.core.terminals.values() if t.get('connected')])}
Active Plans: {active_plan_count}
Pattern Library: {pattern_count}
Boot Prompts: {len(self.core.boot_prompts)}
Runtime Prompts: {len(self.core.runtime_prompts)}
"""
    
    async def _cmd_queue(self) -> str:
        """Show task queue"""
        if not self.core.queue:
            return "📭 Queue is empty"
        
        from jarvis_core import Priority
        
        lines = ["📋 TASK QUEUE", "═" * 40]
        for i, task in enumerate(self.core.queue[:10]):
            pri = Priority(task.priority).name
            lines.append(f"{i+1}. [{pri}] T{task.source_terminal}: {task.content[:50]}...")
        
        if len(self.core.queue) > 10:
            lines.append(f"... and {len(self.core.queue) - 10} more")
        
        return "\n".join(lines)
    
    async def _cmd_help(self) -> str:
        """Show help"""
        return """
🔬 ANALYSIS MODE COMMANDS
═══════════════════════════════════════════════════════
status          - Show system status
queue           - View task queue
plans           - List active plans
plan <id>       - Show plan details
export <id>     - Export plan to visualizer JSON
patterns        - List pattern library
prompts         - List all prompts (boot + runtime)
prompt <id>     - View prompt template
analyze prompt  - LLM-assisted prompt improvement
memory          - Memory operations
llm             - LLM configuration
config          - Configuration
terminals       - Show connected terminals
boundaries      - Show action permissions
help            - Show this help
continue        - Exit analysis mode
═══════════════════════════════════════════════════════
"""
    
    # ==================== PLANNING COMMANDS ====================
    
    async def _cmd_plans(self) -> str:
        """List active plans"""
        if not self.core.active_plans:
            return "📋 No active plans"
        
        lines = ["📋 ACTIVE PLANS", "═" * 40]
        for task_id, plan_id in self.core.active_plans.items():
            plan = self.core.planner.active_plans.get(plan_id)
            if plan:
                status = plan.status.name
                lines.append(f"  {plan_id}: {plan.description[:50]} [{status}]")
        
        return "\n".join(lines)
    
    async def _cmd_plan(self, cmd: str) -> str:
        """Show plan details"""
        plan_id = cmd.split(maxsplit=1)[1]
        plan = None
        
        if self.core.planner:
            plan = self.core.planner.active_plans.get(plan_id)
        
        if not plan:
            return f"Plan {plan_id} not found"
        
        lines = [f"📋 PLAN: {plan.description}", "═" * 40]
        lines.append(f"ID: {plan.id}")
        lines.append(f"Status: {plan.status.name}")
        lines.append(f"Goals: {len(plan.goals)}")
        lines.append(f"Score: {plan.evaluation_score:.2%}" if plan.evaluation_score else "Score: N/A")
        
        # Goal tree
        lines.append("\nGoal Tree:")
        root = plan.get_root_goal()
        if root:
            lines.extend(self.core._format_goal_tree_analysis(plan, root.id, indent=0))
        
        # Add export option
        lines.append("\nCommands:")
        lines.append(f"  export {plan_id}  - Export to visualizer JSON")
        
        return "\n".join(lines)
    
    async def _cmd_export(self, cmd: str) -> str:
        """Export plan to visualizer format"""
        from jarvis_core import STATE_DIR
        
        plan_id = cmd.split(maxsplit=1)[1]
        plan = None
        
        if self.core.planner:
            plan = self.core.planner.active_plans.get(plan_id)
        
        if not plan:
            return f"Plan {plan_id} not found"
        
        # Export to visualizer format
        export_dir = STATE_DIR / "visualizer"
        export_dir.mkdir(exist_ok=True)
        
        export_file = export_dir / f"plan_{plan_id}.json"
        plan.export_visualizer_json(export_file)
        
        return f"""
✅ Exported plan to visualizer format

File: {export_file}
Steps: {len(plan.goals)}

To visualize:
1. Open the 3D Request Fingerprint Visualizer
2. Load: {export_file}
3. Explore the plan structure in 3D
"""
    
    async def _cmd_patterns(self) -> str:
        """List pattern library"""
        if not self.core.planner or not self.core.planner.pattern_library:
            return "🎯 No patterns in library yet"
        
        lines = ["🎯 PATTERN LIBRARY", "═" * 40]
        for pattern_id, pattern in self.core.planner.pattern_library.items():
            score = pattern.evaluation_score or 0
            goals = len(pattern.goals)
            lines.append(f"  {pattern_id[:8]}: {pattern.description[:40]} ({goals} goals, score: {score:.2f})")
        
        return "\n".join(lines)
    
    # ==================== PROMPT COMMANDS ====================
    
    async def _cmd_prompts(self) -> str:
        """List all prompts"""
        lines = ["📝 PROMPTS", "═" * 40, "", "BOOT (immutable):"]
        for pid, prompt in self.core.boot_prompts.items():
            immutable = "🔒" if prompt.get("immutable", True) else "🔓"
            lines.append(f"  {immutable} {pid}")
        
        lines.append("")
        lines.append("RUNTIME (learned/overridden):")
        if self.core.runtime_prompts:
            for pid in self.core.runtime_prompts:
                lines.append(f"  📝 {pid}")
        else:
            lines.append("  (none yet)")
        
        lines.append("")
        lines.append("Commands:")
        lines.append("  prompt <id>              - View prompt template")
        lines.append("  prompt <id> reset        - Reset to boot version")
        lines.append("  analyze prompt <id>      - LLM-assisted improvement")
        
        return "\n".join(lines)
    
    async def _cmd_prompt(self, cmd: str) -> str:
        """View or modify prompt"""
        parts = cmd.split(maxsplit=2)
        
        if len(parts) < 2:
            return "Usage: prompt <id> [reset]"
        
        prompt_id = parts[1]
        
        # View prompt
        if len(parts) == 2:
            # Check runtime first
            if prompt_id in self.core.runtime_prompts:
                prompt = self.core.runtime_prompts[prompt_id]
                source = "RUNTIME OVERRIDE"
            elif prompt_id in self.core.boot_prompts:
                prompt = self.core.boot_prompts[prompt_id]
                source = "BOOT" + (" (IMMUTABLE)" if prompt.get("immutable", True) else " (can override)")
            else:
                return f"Prompt '{prompt_id}' not found"
            
            lines = [
                f"📝 PROMPT: {prompt_id}",
                "═" * 60,
                f"Source: {source}",
                f"Version: {prompt.get('version', 'N/A')}",
                "",
                "Template:",
                "─" * 60
            ]
            
            # Show template (truncated if too long)
            template = prompt.get("template", "")
            if len(template) > 1000:
                lines.append(template[:1000] + "\n... (truncated, use 'analyze prompt' to work with full text)")
            else:
                lines.append(template)
            
            lines.append("─" * 60)
            
            if not prompt.get("immutable", True):
                lines.append("")
                lines.append("Commands:")
                lines.append(f"  analyze prompt {prompt_id}     - Improve with LLM assistance")
                if prompt_id in self.core.runtime_prompts:
                    lines.append(f"  prompt {prompt_id} reset       - Reset to boot version")
            
            return "\n".join(lines)
        
        # Reset prompt
        elif parts[2] == "reset":
            if prompt_id in self.core.runtime_prompts:
                del self.core.runtime_prompts[prompt_id]
                self.core._save_runtime_prompts()
                return f"✅ Reset '{prompt_id}' to boot version"
            else:
                return f"'{prompt_id}' has no runtime override"
        
        else:
            return "Usage: prompt <id> [reset]"
    
    async def _cmd_analyze_prompt(self, cmd: str) -> str:
        """LLM-assisted prompt analysis (placeholder for now)"""
        parts = cmd.split(maxsplit=2)
        
        if len(parts) < 3:
            return "Usage: analyze prompt <id> [feedback]"
        
        prompt_id = parts[2]
        feedback = parts[3] if len(parts) > 3 else None
        
        # Import the analyzer
        from prompt_analyzer import PromptAnalyzer
        
        analyzer = PromptAnalyzer(self.core)
        result = await analyzer.analyze_and_improve(prompt_id, feedback)
        
        return result
    
    # ==================== MEMORY COMMANDS ====================
    
    async def _cmd_memory(self, cmd: str) -> str:
        """Memory operations"""
        if not self.core.memory_store:
            return "Memory system not initialized."
        
        parts = cmd.split(maxsplit=1)
        
        if len(parts) == 1 or parts[1] == "stats":
            stats = self.core.memory_store.get_stats()
            return f"""
📚 MEMORY STATISTICS
════════════════════════════════
Contacts: {stats['contacts']}
Calendar Events: {stats['calendar_events']}
Notes: {stats['notes']}
Preferences: {stats['preferences']}

Usage:
memory stats           - Show statistics
memory contacts        - List contacts
memory events          - List upcoming events
memory notes           - List recent notes
memory search <query>  - Search all memory
"""
        
        # Add other memory sub-commands as needed
        return "Memory command not fully implemented yet"
    
    # ==================== LLM COMMANDS ====================
    
    async def _cmd_llm(self, cmd: str) -> str:
        """LLM configuration"""
        parts = cmd.split(maxsplit=2)
        
        if len(parts) == 1:
            return f"""
🤖 LLM CONFIGURATION
════════════════════════════════
Provider: {self.core.config.get('llm_provider', 'ollama')}
Fast model: {self.core.config.get('ollama_model_fast', 'llama3.2:3b')}
Smart model: {self.core.config.get('ollama_model_smart', 'llama3.1:8b')}
OpenAI model: {self.core.config.get('openai_model', 'gpt-4o-mini')}

Usage: 
  llm provider ollama|openai
  llm fast <model>
  llm smart <model>
  llm stats  - Show execution statistics
"""
        
        elif parts[1] == "stats":
            if self.core.prompt_manager:
                return self.core.prompt_manager.get_stats_summary()
            else:
                return "Prompt manager not initialized"
        
        # Add model switching logic
        return "LLM configuration commands partially implemented"
    
    # ==================== CONFIG COMMANDS ====================
    
    async def _cmd_config(self, cmd: str) -> str:
        """Configuration management"""
        parts = cmd.split()
        
        if len(parts) == 1:
            return f"""
⚙️  CONFIGURATION
════════════════════════════════
idle_delay: {self.core.config['idle_delay']}s
persist_interval: {self.core.config['persist_interval']}

Usage: config <key> <value>
"""
        
        elif len(parts) == 3:
            key = parts[1]
            try:
                value = float(parts[2])
                if key in self.core.config:
                    self.core.config[key] = value
                    self.core._save_config()
                    return f"✅ {key} set to {value} (saved to disk)"
                else:
                    return f"❌ Unknown config: {key}"
            except ValueError:
                return f"❌ Invalid value: {parts[2]}"
        else:
            return "Usage: config <key> <value>"
    
    # ==================== SYSTEM COMMANDS ====================
    
    async def _cmd_terminals(self) -> str:
        """Show connected terminals"""
        from jarvis_core import PrivilegeLevel
        
        lines = ["📡 TERMINALS", "═" * 40]
        for tid, tinfo in self.core.terminals.items():
            status = "🟢" if tinfo.get("connected") else "🔴"
            priv = PrivilegeLevel(tinfo.get("privilege", 3)).name
            lines.append(f"  {status} T{tid}: {tinfo.get('name', 'Unknown')} [{priv}]")
        return "\n".join(lines)
    
    async def _cmd_boundaries(self) -> str:
        """Show action boundaries"""
        lines = ["🚧 ACTION BOUNDARIES", "═" * 40]
        for action, config in self.core.boundaries.items():
            status = "✅" if config.get("allowed") else "❌"
            restrictions = ", ".join(config.get("restrictions", [])) or "none"
            lines.append(f"  {status} {action}: {restrictions}")
        return "\n".join(lines)

    async def _cmd_cleanup_duplicates(self) -> str:
        """Clean up duplicate contacts"""
        if not self.core.memory_store:
            return "Memory not available"
        
        # Get all contacts
        all_contacts = self.core.memory_store.find_contacts("")
        
        if not all_contacts:
            return "No contacts found"
        
        # Group by name (case-insensitive)
        by_name = {}
        for contact in all_contacts:
            name_key = contact.get('name', '').lower()
            if name_key not in by_name:
                by_name[name_key] = []
            by_name[name_key].append(contact)
        
        # Find duplicates
        duplicates = {name: contacts for name, contacts in by_name.items() if len(contacts) > 1}
        
        if not duplicates:
            return "No duplicate contacts found ✓"
        
        # Show duplicates
        lines = ["📋 Duplicate Contacts Found:\n"]
        total_dupes = 0
        
        for name, contacts in duplicates.items():
            lines.append(f"{name.title()}: {len(contacts)} entries")
            total_dupes += len(contacts) - 1  # Count extras
            
            for i, c in enumerate(contacts, 1):
                cid = c.get('id', 'unknown')
                phone = c.get('phone_mobile', c.get('phone_home', 'no phone'))
                email = c.get('email_personal', 'no email')
                lines.append(f"  {i}. ID:{cid} | Phone:{phone} | Email:{email}")
            lines.append("")
        
        lines.append(f"Total duplicates to remove: {total_dupes}")
        lines.append("\nTo remove duplicates, use: cleanup duplicates confirm")
        
        return "\n".join(lines)

    async def _cmd_cleanup_duplicates_confirm(self) -> str:
        """Actually remove duplicates, keeping the first of each"""
        if not self.core.memory_store:
            return "Memory not available"
        
        all_contacts = self.core.memory_store.find_contacts("")
        
        # Group by name
        by_name = {}
        for contact in all_contacts:
            name_key = contact.get('name', '').lower()
            if name_key not in by_name:
                by_name[name_key] = []
            by_name[name_key].append(contact)
        
        # Find duplicates
        removed = 0
        for name, contacts in by_name.items():
            if len(contacts) > 1:
                # Keep first, delete rest
                for contact in contacts[1:]:
                    cid = contact.get('id')
                    if cid:
                        try:
                            # Delete from memory store
                            self.core.memory_store.delete_contact(cid)
                            removed += 1
                            self.core._log("CLEANUP", f"Removed duplicate: {name} (ID:{cid})")
                        except Exception as e:
                            self.core._log("ERROR", f"Failed to delete {name} ID:{cid}: {e}")
        
        return f"✓ Removed {removed} duplicate contacts"
    
    async def _cmd_memory_cleanup(self) -> str:
        """Clean up duplicate contacts"""
        if not self.core.memory_store:
            return "Memory not available"
        
        # Get all contacts
        all_contacts = self.core.memory_store.contacts  # Adjust based on your API
        
        # Group by name
        by_name = {}
        for contact in all_contacts:
            name = contact.get('name', '').lower()
            if name not in by_name:
                by_name[name] = []
            by_name[name].append(contact)
        
        # Find duplicates
        duplicates = {name: contacts for name, contacts in by_name.items() if len(contacts) > 1}
        
        if not duplicates:
            return "No duplicate contacts found"
        
        lines = ["Duplicate contacts found:"]
        for name, contacts in duplicates.items():
            lines.append(f"\n{name}: {len(contacts)} entries")
            for c in contacts:
                lines.append(f"  - ID: {c.get('id', 'unknown')}, Phone: {c.get('phone_mobile', 'none')}")
        
        return "\n".join(lines)