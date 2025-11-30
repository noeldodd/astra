# jarvis_prompts.py
"""
JARVIS Prompt Manager

Handles:
- Loading and managing prompts (boot + runtime)
- Executing prompts via LLM (Ollama or OpenAI)
- Prompt refinement and evolution
- Performance tracking
"""

import json
import requests
import time
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
import asyncio

# Ollama configuration
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")

# OpenAI configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
if (len(OPENAI_API_KEY) < 1):
    print(f"WARN: OPENAI_API_KEY unset???")

class PromptExecutionResult:
    """Result from executing a prompt"""
    
    def __init__(
        self,
        success: bool,
        response: str,
        parsed_json: Optional[Dict] = None,
        elapsed_ms: float = 0,
        model: str = "",
        prompt_id: str = "",
        error: Optional[str] = None
    ):
        self.success = success
        self.response = response
        self.parsed_json = parsed_json
        self.elapsed_ms = elapsed_ms
        self.model = model
        self.prompt_id = prompt_id
        self.error = error
        self.timestamp = datetime.now()
    
    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "response": self.response[:500] if self.response else None,
            "parsed_json": self.parsed_json,
            "elapsed_ms": self.elapsed_ms,
            "model": self.model,
            "prompt_id": self.prompt_id,
            "error": self.error,
            "timestamp": self.timestamp.isoformat()
        }


class PromptManager:
    """Manages prompt execution via Ollama or OpenAI"""
    
    def __init__(self, config: Dict):
        self.config = config
        
        # LLM configuration from config
        self.llm_provider = config.get("llm_provider", "ollama")  # "ollama" or "openai"
        self.ollama_model_fast = config.get("ollama_model_fast", "llama3.2:3b")
        self.ollama_model_smart = config.get("ollama_model_smart", "llama3.1:8b")
        self.openai_model = config.get("openai_model", "gpt-4o-mini")
        
        # Performance tracking
        self.execution_stats = {
            "total_calls": 0,
            "total_time_ms": 0,
            "by_provider": {},
            "by_model": {},
            "by_prompt": {}
        }
    
    def _log(self, message: str):
        """Simple logging"""
        print(f"[{datetime.now().strftime('%H:%M:%S')}] [PROMPT] {message}")
    
    # ==================== LLM EXECUTION ====================
    
    async def call_ollama(
        self,
        prompt: str,
        model: str,
        max_tokens: int = 200,
        temperature: float = 0.1
    ) -> PromptExecutionResult:
        """Call Ollama API"""
        
        self._log(f"Calling Ollama ({model})...")
        start = time.time()
        
        try:
            # Use asyncio to run blocking request
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(
                    OLLAMA_URL,
                    json={
                        "model": model,
                        "prompt": prompt,
                        "stream": False,
                        "options": {
                            "num_predict": max_tokens,
                            "temperature": temperature
                        }
                    },
                    timeout=30
                )
            )
            
            elapsed = (time.time() - start) * 1000
            
            if response.status_code != 200:
                return PromptExecutionResult(
                    success=False,
                    response="",
                    elapsed_ms=elapsed,
                    model=model,
                    error=f"HTTP {response.status_code}: {response.text}"
                )
            
            data = response.json()
            text = data.get("response", "")
            
            # Try to parse JSON from response
            parsed = self._extract_json(text)
            
            self._log(f"Ollama response: {elapsed:.0f}ms")
            
            return PromptExecutionResult(
                success=True,
                response=text,
                parsed_json=parsed,
                elapsed_ms=elapsed,
                model=model
            )
        
        except requests.exceptions.Timeout:
            return PromptExecutionResult(
                success=False,
                response="",
                elapsed_ms=(time.time() - start) * 1000,
                model=model,
                error="Request timeout (30s)"
            )
        except Exception as e:
            return PromptExecutionResult(
                success=False,
                response="",
                elapsed_ms=(time.time() - start) * 1000,
                model=model,
                error=str(e)
            )
    
    async def call_openai(
        self,
        prompt: str,
        model: str,
        max_tokens: int = 200,
        temperature: float = 0.1
    ) -> PromptExecutionResult:
        """Call OpenAI API"""
        
        if not OPENAI_API_KEY:
            return PromptExecutionResult(
                success=False,
                response="",
                model=model,
                error="OPENAI_API_KEY not set"
            )
        
        self._log(f"Calling OpenAI ({model})...")
        start = time.time()
        
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: requests.post(
                    OPENAI_URL,
                    headers={
                        "Authorization": f"Bearer {OPENAI_API_KEY}",
                        "Content-Type": "application/json"
                    },
                    json={
                        "model": model,
                        "messages": [
                            {"role": "user", "content": prompt}
                        ],
                        "max_tokens": max_tokens,
                        "temperature": temperature
                    },
                    timeout=30
                )
            )
            
            elapsed = (time.time() - start) * 1000
            
            if response.status_code != 200:
                return PromptExecutionResult(
                    success=False,
                    response="",
                    elapsed_ms=elapsed,
                    model=model,
                    error=f"HTTP {response.status_code}: {response.text}"
                )
            
            data = response.json()
            text = data["choices"][0]["message"]["content"]
            
            # Try to parse JSON from response
            parsed = self._extract_json(text)
            
            self._log(f"OpenAI response: {elapsed:.0f}ms")
            
            return PromptExecutionResult(
                success=True,
                response=text,
                parsed_json=parsed,
                elapsed_ms=elapsed,
                model=model
            )
        
        except requests.exceptions.Timeout:
            return PromptExecutionResult(
                success=False,
                response="",
                elapsed_ms=(time.time() - start) * 1000,
                model=model,
                error="Request timeout (30s)"
            )
        except Exception as e:
            return PromptExecutionResult(
                success=False,
                response="",
                elapsed_ms=(time.time() - start) * 1000,
                model=model,
                error=str(e)
            )
    
    async def execute_prompt(
        self,
        prompt_text: str,
        prompt_id: str = "",
        use_smart_model: bool = False,
        max_tokens: int = 200
    ) -> PromptExecutionResult:
        """
        Execute a prompt using configured LLM provider
        
        Args:
            prompt_text: The formatted prompt to send
            prompt_id: ID for tracking
            use_smart_model: True = use larger/smarter model, False = use fast model
            max_tokens: Maximum tokens to generate
        """
        
        # Determine which model to use
        if self.llm_provider == "ollama":
            model = self.ollama_model_smart if use_smart_model else self.ollama_model_fast
            result = await self.call_ollama(prompt_text, model, max_tokens)
        else:  # openai
            model = self.openai_model
            result = await self.call_openai(prompt_text, model, max_tokens)
        
        result.prompt_id = prompt_id
        
        # Update statistics
        self._update_stats(result)
        
        return result
    
    def _extract_json(self, text: str) -> Optional[Dict]:
        """Extract JSON object from LLM response"""
        try:
            # Try direct parse first
            return json.loads(text)
        except:
            pass
        
        try:
            # Try to find JSON in text
            start = text.find('{')
            end = text.rfind('}') + 1
            if start >= 0 and end > start:
                json_str = text[start:end]
                return json.loads(json_str)
        except:
            pass
        
        return None
    
    def _update_stats(self, result: PromptExecutionResult):
        """Update execution statistics"""
        self.execution_stats["total_calls"] += 1
        self.execution_stats["total_time_ms"] += result.elapsed_ms
        
        # By provider
        provider = self.llm_provider
        if provider not in self.execution_stats["by_provider"]:
            self.execution_stats["by_provider"][provider] = {
                "calls": 0,
                "total_ms": 0,
                "errors": 0
            }
        self.execution_stats["by_provider"][provider]["calls"] += 1
        self.execution_stats["by_provider"][provider]["total_ms"] += result.elapsed_ms
        if not result.success:
            self.execution_stats["by_provider"][provider]["errors"] += 1
        
        # By model
        model = result.model
        if model not in self.execution_stats["by_model"]:
            self.execution_stats["by_model"][model] = {
                "calls": 0,
                "total_ms": 0,
                "avg_ms": 0,
                "errors": 0
            }
        stats = self.execution_stats["by_model"][model]
        stats["calls"] += 1
        stats["total_ms"] += result.elapsed_ms
        stats["avg_ms"] = stats["total_ms"] / stats["calls"]
        if not result.success:
            stats["errors"] += 1
        
        # By prompt
        if result.prompt_id:
            if result.prompt_id not in self.execution_stats["by_prompt"]:
                self.execution_stats["by_prompt"][result.prompt_id] = {
                    "calls": 0,
                    "total_ms": 0,
                    "avg_ms": 0,
                    "errors": 0
                }
            stats = self.execution_stats["by_prompt"][result.prompt_id]
            stats["calls"] += 1
            stats["total_ms"] += result.elapsed_ms
            stats["avg_ms"] = stats["total_ms"] / stats["calls"]
            if not result.success:
                stats["errors"] += 1
    
    # ==================== PROMPT TEMPLATES ====================
    
    async def classify_intent(
        self,
        user_input: str,
        terminal_id: int,
        terminal_type: str,
        context: Dict
    ) -> PromptExecutionResult:
        """Execute intent classification prompt"""
        
        prompt = f"""Classify this input. Users often STATE information they want you to STORE without using words like "save" or "remember".

    Input: "{user_input}"

    CRITICAL RULES:
    - If user STATES a fact like "Bob's number is X" → crud_create (they want you to save it)
    - If user ASKS "What's Bob's number?" → crud_read (they want to retrieve it)
    - If user says "Change Bob's number to X" → crud_update
    - If user says "Delete Bob" or "Remove Bob's number" → crud_delete

    Examples:
    - "Bob's cell is 555-1212" → crud_create (implicit: save this)
    - "Sarah email sarah@test.com" → crud_create (implicit: save this)
    - "What's Bob's number?" → crud_read
    - "Show me Sarah's email" → crud_read
    - "Meeting tomorrow at 3pm" → crud_create (implicit: save this event)
    - "Change Bob's phone to 555-9999" → crud_update
    - "Turn on lights" → smarthome
    - "What's the weather?" → query
    - "Hello" → conversation

    Categories:
    - crud_create: User STATING information (name is X, phone is Y, event on Z)
    - crud_read: User ASKING for information (what's, show me, find)
    - crud_update: User wanting to CHANGE existing information
    - crud_delete: User wanting to REMOVE information
    - smarthome: Device or home control
    - query: External information request (weather, time, news)
    - conversation: Greetings, chat, unclear

    Return ONLY JSON:
    {{"intent": "category", "implicit": true/false, "confidence": 0.0-1.0, "reasoning": "brief explanation"}}"""
        
        return await self.execute_prompt(
            prompt_text=prompt,
            prompt_id="classify_intent",
            use_smart_model=False,
            max_tokens=150
        )
    
    async def generate_self_task(
        self,
        recent_summary: str,
        pending_questions: List[str],
        last_self_task: Optional[str]
    ) -> PromptExecutionResult:
        """Generate a self-task when idle"""
        
        prompt = f"""I am Jarvis. My queue is empty. What should I think about?

Current time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
Recent interactions summary: {recent_summary}
Pending questions: {json.dumps(pending_questions)}
Last self-task: {last_self_task or "None"}

Consider:
- Is there something I should research?
- Should I review recent interactions for patterns?
- Is there maintenance I should perform?
- Is there something I'm curious about?

Return ONLY JSON:
{{"task": "description of self-task", "priority": 4-5, "reasoning": "why this matters"}}"""
        
        return await self.execute_prompt(
            prompt_text=prompt,
            prompt_id="generate_self_task",
            use_smart_model=False,  # Fast model for routine tasks
            max_tokens=150
        )
    
    async def extract_entities(
        self,
        user_input: str,
        intent: str,
        context: Dict
    ) -> PromptExecutionResult:
        """Extract entities based on classified intent"""
    
        entity_prompts = {
            "crud_create": f"""Extract from: "{user_input}"

Look for:
- Name (person or event title)
- Phone (any format: 555-1212, (555) 123-4567, etc.)
- Email (any email address)
- Date/time (today, tomorrow, Friday, 2pm, etc.)
- Location (room names, addresses)

Examples:
- "Bob's cell is 555-1212" → {{"type":"contact","name":"Bob","phone":"555-1212"}}
- "Sarah email sarah@test.com" → {{"type":"contact","name":"Sarah","email":"sarah@test.com"}}
- "Meeting tomorrow 2pm" → {{"type":"calendar","title":"Meeting","date":"tomorrow","time":"2pm"}}
- "Remember garage code is 1234" → {{"type":"note","title":"garage code","content":"garage code is 1234"}}

Return ONLY JSON (if multiple phone types, use phone_mobile as default):
{{"type":"contact|calendar|note","name":"","phone":"","phone_mobile":"","phone_work":"","phone_home":"","email":"","email_personal":"","email_work":"","date":"","time":"","title":"","content":"","location":""}}
Only include fields that are clearly present.""",

        "crud_read": f"""Extract from: "{user_input}"

What is the user asking for?

Examples:
- "What's Bob's number?" → {{"type":"contact","identifier":"Bob","field":"phone"}}
- "Show me Sarah's email" → {{"type":"contact","identifier":"Sarah","field":"email"}}
- "Find Bob" → {{"type":"contact","identifier":"Bob","field":"all"}}
- "What's on my calendar?" → {{"type":"calendar","identifier":"","field":"all"}}

Return ONLY JSON:
{{"type":"contact|calendar|note","identifier":"name or search term","field":"phone|email|all"}}""",

        "crud_update": f"""Extract from: "{user_input}"

Examples:
- "Change Bob's number to 555-9999" → {{"type":"contact","identifier":"Bob","field":"phone_mobile","new_value":"555-9999"}}
- "Update Sarah's email to new@email.com" → {{"type":"contact","identifier":"Sarah","field":"email_personal","new_value":"new@email.com"}}

Return ONLY JSON:
{{"type":"contact|calendar|note","identifier":"","field":"","new_value":""}}""",

        "smarthome": f"""Extract from: "{user_input}"  

Examples:
- "Turn on kitchen lights" → {{"device":"lights","location":"kitchen","action":"on"}}
- "It's cold in here" → {{"device":"heat","action":"increase","implicit":true}}
- "Lock the doors" → {{"device":"doors","action":"lock"}}

Return ONLY JSON:
{{"device":"","location":"","action":"on|off|set|up|down|lock|unlock","value":"","implicit":true/false}}""",

        "query": f"""Extract from: "{user_input}"

Examples:
- "What's the weather?" → {{"topic":"weather"}}
- "What time is it?" → {{"topic":"time"}}

Return ONLY JSON:
{{"topic":"weather|time|news|search|info","subject":"","location":"","date":""}}""",

        "crud_delete": f"""Extract from: "{user_input}"

Examples:
- "Delete Bob" → {{"type":"contact","identifier":"Bob"}}
- "Remove meeting" → {{"type":"calendar","identifier":"meeting"}}

Return ONLY JSON:
{{"type":"contact|calendar|note","identifier":""}}"""
    }
    
        prompt = entity_prompts.get(intent, f"Extract key information from: {user_input}")
    
        return await self.execute_prompt(
            prompt_text=prompt,
            prompt_id=f"extract_{intent}",
            use_smart_model=False,
            max_tokens=150
        )
    
    async def generate_response(
        self,
        user_input: str,
        intent: str,
        entities: Dict,
        context: Dict
    ) -> PromptExecutionResult:
        """Generate conversational response"""
        
        prompt = f"""Respond briefly and helpfully.

User said: "{user_input}"
Intent: {intent}
Extracted info: {json.dumps(entities)}

Provide a natural, brief response (1-2 sentences) appropriate for voice assistant.

Return ONLY JSON:
{{"response": "your response text"}}"""
        
        return await self.execute_prompt(
            prompt_text=prompt,
            prompt_id="generate_response",
            use_smart_model=True,  # Use smart model for conversation
            max_tokens=100
        )
    
    # ==================== STATISTICS ====================
    
    def get_stats_summary(self) -> str:
        """Get formatted statistics summary"""
        stats = self.execution_stats
        
        if stats["total_calls"] == 0:
            return "No prompts executed yet."
        
        avg_time = stats["total_time_ms"] / stats["total_calls"]
        
        lines = [
            "📊 PROMPT EXECUTION STATISTICS",
            "═" * 40,
            f"Total calls: {stats['total_calls']}",
            f"Total time: {stats['total_time_ms']/1000:.1f}s",
            f"Average: {avg_time:.0f}ms per call",
            "",
            "By Provider:"
        ]
        
        for provider, pstats in stats["by_provider"].items():
            avg = pstats["total_ms"] / pstats["calls"] if pstats["calls"] > 0 else 0
            lines.append(f"  {provider}: {pstats['calls']} calls, {avg:.0f}ms avg, {pstats['errors']} errors")
        
        lines.append("\nBy Model:")
        for model, mstats in stats["by_model"].items():
            lines.append(f"  {model}: {mstats['calls']} calls, {mstats['avg_ms']:.0f}ms avg, {mstats['errors']} errors")
        
        if stats["by_prompt"]:
            lines.append("\nBy Prompt:")
            for prompt_id, pstats in sorted(
                stats["by_prompt"].items(),
                key=lambda x: x[1]["calls"],
                reverse=True
            )[:5]:  # Top 5
                lines.append(f"  {prompt_id}: {pstats['calls']} calls, {pstats['avg_ms']:.0f}ms avg")
        
        return "\n".join(lines)


# ==================== CONFIGURATION DEFAULTS ====================

def get_default_llm_config() -> Dict:
    """Get default LLM configuration"""
    return {
        "llm_provider": "ollama",  # "ollama" or "openai"
        "ollama_model_fast": "llama3.2:3b",
        "ollama_model_smart": "llama3.1:8b",
        "openai_model": "gpt-4o-mini",
        "ollama_url": "http://localhost:11434/api/generate"
    }


# ==================== TESTING ====================

async def test_prompt_manager():
    """Test the prompt manager"""
    
    config = get_default_llm_config()
    config["llm_provider"] = "ollama"  # or "openai"
    
    manager = PromptManager(config)
    
    print("\n" + "=" * 60)
    print("Testing Prompt Manager")
    print("=" * 60)
    
    # Test 1: Classify intent
    print("\n1. Testing intent classification...")
    result = await manager.classify_intent(
        user_input="Bob's cell number is 555-1212",
        terminal_id=2,
        terminal_type="test",
        context={}
    )
    
    print(f"Success: {result.success}")
    print(f"Time: {result.elapsed_ms:.0f}ms")
    print(f"Model: {result.model}")
    if result.parsed_json:
        print(f"Result: {json.dumps(result.parsed_json, indent=2)}")
    else:
        print(f"Raw: {result.response[:200]}")
    
    # Test 2: Generate self-task
    print("\n2. Testing self-task generation...")
    result = await manager.generate_self_task(
        recent_summary="User asked about contacts",
        pending_questions=[],
        last_self_task="Check system health"
    )
    
    print(f"Success: {result.success}")
    print(f"Time: {result.elapsed_ms:.0f}ms")
    if result.parsed_json:
        print(f"Result: {json.dumps(result.parsed_json, indent=2)}")
    
    # Show stats
    print("\n" + manager.get_stats_summary())


if __name__ == "__main__":
    """
    Test the prompt manager standalone
    
    Usage:
        python jarvis_prompts.py
    """
    asyncio.run(test_prompt_manager())