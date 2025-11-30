# test_jarvis.py
import asyncio
import json
from pathlib import Path

async def send_test_task():
    """Simulate a terminal sending a task by directly modifying queue"""
    
    # Wait for Jarvis to boot
    await asyncio.sleep(2)
    
    # Read current queue
    queue_file = Path.home() / "jarvis" / "state" / "queue.json"
    
    with open(queue_file) as f:
        queue = json.load(f)
    
    # Add a test task
    test_task = {
        "task_id": "test_123",
        "content": "Analysis",
        "source_terminal": 2,
        "priority": 1,  # USER priority
        "context": {"terminal_type": "test"},
        "deadline": None,
        "created_at": "2025-01-15T14:35:00",
        "attempts": 0
    }
    
    queue.append(test_task)
    
    # Write back
    with open(queue_file, 'w') as f:
        json.dump(queue, f, indent=2)
    
    print("✅ Test task added to queue: 'Analysis'")

if __name__ == "__main__":
    asyncio.run(send_test_task())