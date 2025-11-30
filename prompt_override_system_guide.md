# Prompt Override System - Guide

## ✅ What Changed

The decomposition prompt is now part of the **boot/runtime prompt system** instead of being hardcoded.

### Architecture:

```
Boot Prompts (~/jarvis/boot/core_prompts.json)
├── classify_intent       [immutable 🔒]
├── generate_self_task    [immutable 🔒]  
└── decompose_task        [can override 🔓]

Runtime Overrides (~/jarvis/state/prompts/runtime_prompts.json)
└── decompose_task        [if overridden]
    └── Takes precedence over boot version
```

### Key Features:

1. **Boot Prompt Template** - Default decomposition logic stored in `core_prompts.json`
2. **Runtime Override** - Can be modified without restart (in `runtime_prompts.json`)
3. **Dynamic Variables** - Template uses `{user_request}` and `{capabilities}`
4. **Immutability Flag** - `decompose_task` is NOT immutable (can be overridden)

---

## 🔍 Viewing Prompts

### List All Prompts

```
Analysis > prompts

📝 PROMPTS
════════════════════════════════

BOOT (immutable):
  🔒 classify_intent
  🔒 generate_self_task
  🔓 decompose_task

RUNTIME (learned/overridden):
  (none yet)

Commands:
  prompt <id>           - View prompt template
  prompt <id> override  - Override with custom version
  prompt <id> reset     - Reset to boot version
```

### View Specific Prompt

```
Analysis > prompt decompose_task

📝 PROMPT: decompose_task
════════════════════════════════
Source: BOOT (can override)
Version: 1

Template:
────────────────────────────────
You are JARVIS, an AI assistant with planning capabilities...
[Full template shown]
────────────────────────────────

Commands:
  prompt decompose_task override  - Create runtime override
```

---

## ✏️ Modifying the Decomposition Prompt

### Option 1: Edit Runtime Prompts File (Recommended)

```bash
# 1. Edit the runtime prompts file
nano ~/jarvis/state/prompts/runtime_prompts.json

# 2. Add your override:
{
  "decompose_task": {
    "id": "decompose_task",
    "version": 2,
    "template": "Your custom prompt here with {user_request} and {capabilities} variables...",
    "immutable": false,
    "notes": "Modified to emphasize X over Y"
  }
}

# 3. No restart needed! Next decomposition will use your version
```

### Option 2: Copy from Boot and Modify

```bash
# 1. View current boot version
Analysis > prompt decompose_task

# 2. Copy the template to a file
cat ~/jarvis/boot/core_prompts.json | jq '.decompose_task.template' > /tmp/decompose.txt

# 3. Edit the file
nano /tmp/decompose.txt

# 4. Create runtime override JSON
{
  "decompose_task": {
    "id": "decompose_task", 
    "version": 2,
    "template": "... your edited prompt ...",
    "immutable": false
  }
}

# 5. Add to runtime_prompts.json
```

---

## 🔄 Template Variables

The decomposition prompt MUST include these variables:

- **`{user_request}`** - The actual user query
- **`{capabilities}`** - Auto-generated list of available capabilities

Example:
```
User Request: "{user_request}"

YOUR AVAILABLE CAPABILITIES:
{capabilities}
```

When executed, becomes:
```
User Request: "Find the best restaurant"

YOUR AVAILABLE CAPABILITIES:
  - memory_read: Access 5 contacts, 2 events, 3 notes
  - memory_write: Store new contacts, events, notes
  - llm_analyze: Analyze information, compare options
  ...
```

---

## 🧪 Testing Your Override

### Before Override:

```
You: Find the best restaurant
Jarvis: [Uses boot template decomposition]
```

### After Adding Override:

```bash
# Edit ~/jarvis/state/prompts/runtime_prompts.json
# (No restart needed!)

You: Find the best restaurant
[PLANNING] Using runtime override for decompose_task prompt
[PLANNING] Plan type: linear
[PLANNING] Reasoning: [Your custom logic]
```

### Check Which Version Is Active:

```
Analysis > prompt decompose_task

Source: RUNTIME OVERRIDE  ← Shows it's using your version
```

---

## 🔙 Resetting to Default

### Via Analysis Mode:

```
Analysis > prompt decompose_task reset
✅ Reset 'decompose_task' to boot version
```

### Manually:

```bash
# Remove from runtime prompts
rm ~/jarvis/state/prompts/runtime_prompts.json
# OR edit and remove just the decompose_task entry
```

---

## 📊 Use Cases

### 1. Experiment with Different Decomposition Styles

**Original:** Emphasizes sequential steps
**Override:** Emphasizes parallel execution where possible

```json
{
  "decompose_task": {
    "template": "...prefer parallel over linear when steps are independent...",
    "notes": "Testing parallel-first decomposition"
  }
}
```

### 2. Add Domain-Specific Instructions

**Original:** General planning
**Override:** Specialized for research tasks

```json
{
  "decompose_task": {
    "template": "...for research tasks, always include verification and source citation steps...",
    "notes": "Research-focused decomposition"
  }
}
```

### 3. Adjust Complexity Thresholds

**Original:** Creates plans for most requests
**Override:** Only creates plans for truly complex tasks

```json
{
  "decompose_task": {
    "template": "...only decompose if task requires 5+ steps...",
    "notes": "Higher threshold for planning"
  }
}
```

### 4. Change Output Format

**Original:** Standard JSON structure
**Override:** Include confidence scores per step

```json
{
  "decompose_task": {
    "template": "...each step should include 'confidence': 0.0-1.0...",
    "notes": "Added confidence scoring"
  }
}
```

---

## 🎯 Best Practices

### ✅ Do:

1. **Keep variable names** - Always use `{user_request}` and `{capabilities}`
2. **Test incrementally** - Make small changes and test
3. **Document changes** - Use the `notes` field
4. **Version your overrides** - Increment version number
5. **Backup boot version** - Keep original template somewhere safe

### ❌ Don't:

1. **Remove required JSON fields** - `goal_type`, `steps`, etc.
2. **Change variable names** - They won't get filled in
3. **Make it too specific** - Keep it general enough for various tasks
4. **Forget about failures** - Test with queries that should fail gracefully

---

## 🔍 Monitoring Prompt Usage

### Check Logs:

```bash
# Watch for override notification
tail -f ~/jarvis/history/$(date +%Y-%m-%d).log | grep "runtime override"

# Should see:
[PLANNING] Using runtime override for decompose_task prompt
```

### Analysis Mode Stats:

```
Analysis > llm stats

Shows execution times for decompose_task prompt
Compare before/after override to see performance impact
```

---

## 🐛 Troubleshooting

### Override Not Working?

1. **Check file location:**
   ```bash
   ls -la ~/jarvis/state/prompts/runtime_prompts.json
   ```

2. **Validate JSON:**
   ```bash
   cat ~/jarvis/state/prompts/runtime_prompts.json | jq .
   ```

3. **Check logs:**
   ```bash
   tail ~/jarvis/history/$(date +%Y-%m-%d).log
   ```

4. **View active prompt:**
   ```
   Analysis > prompt decompose_task
   Source: should say "RUNTIME OVERRIDE"
   ```

### Template Variables Not Replaced?

- Make sure you used `{user_request}` not `$user_request` or other syntax
- Check that `{capabilities}` is present
- Verify the `.format()` call works (Python string formatting)

### Plans Look Wrong?

- Check LLM logs for decomposition response
- Verify JSON structure matches expected format
- Test with simple queries first ("turn on lights")
- Then gradually test more complex queries

---

## 📁 File Locations

```
~/jarvis/
├── boot/
│   └── core_prompts.json              # Boot templates (including decompose_task)
├── state/
│   └── prompts/
│       └── runtime_prompts.json       # Your overrides
└── history/
    └── YYYY-MM-DD.log                 # Execution logs
```

---

## 🚀 Example: Making Decomposition More Verbose

### Goal: Add detailed reasoning to each step

**Edit `runtime_prompts.json`:**

```json
{
  "decompose_task": {
    "id": "decompose_task",
    "version": 2,
    "template": "You are JARVIS...\n\nFor each step, include:\n- description\n- reasoning: why this step is necessary\n- dependencies: what must complete first\n- estimated_time_seconds\n\nFormat:\n{{\"steps\": [{{\"description\":\"...\", \"reasoning\":\"...\", \"dependencies\":[...], \"estimated_time_seconds\":5}}]}}",
    "notes": "Added reasoning and dependencies per step"
  }
}
```

**Result:**
```
[PLANNING] Using runtime override for decompose_task prompt
[PLANNING] Step 1: Search restaurants
            Reasoning: Need data before filtering
            Dependencies: []
```

---

## 🎓 Next Steps

1. **View current prompt:** `Analysis > prompt decompose_task`
2. **Create a test override** with minor changes
3. **Test with simple query** to verify it works
4. **Iterate and refine** based on results
5. **Share successful patterns** by saving them

The system is designed for experimentation - try different approaches and see what works best! 🧪