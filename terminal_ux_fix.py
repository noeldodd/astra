# terminal_ux_fix.py
"""
UX Improvements for JARVIS Terminal

Fixes:
1. Shows spinner/working indicator while processing
2. Only shows next prompt after response is complete
3. Better visual feedback for user

INTEGRATION:
Replace the input handling in jarvis_terminal.py
"""

import asyncio
import sys
import threading
from typing import Optional


class WorkingIndicator:
    """
    Shows animated spinner while JARVIS is processing
    
    Features:
    - Non-blocking animation
    - Clean removal when done
    - Multiple spinner styles
    """
    
    def __init__(self, message: str = "Thinking", style: str = "dots"):
        self.message = message
        self.style = style
        self.running = False
        self.thread: Optional[threading.Thread] = None
        
        # Spinner styles
        self.styles = {
            "dots": ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"],
            "line": ["-", "\\", "|", "/"],
            "arrow": ["←", "↖", "↑", "↗", "→", "↘", "↓", "↙"],
            "dots_simple": [".", "..", "...", ""],
            "pulse": ["●", "○", "●", "○"],
            "thinking": ["🤔", "💭", "🤔", "💭"]
        }
        
        self.frames = self.styles.get(style, self.styles["dots"])
    
    def start(self):
        """Start the spinner animation"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._animate, daemon=True)
        self.thread.start()
    
    def stop(self):
        """Stop the spinner and clear the line"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=0.5)
        
        # Clear the spinner line
        sys.stdout.write('\r' + ' ' * (len(self.message) + 5) + '\r')
        sys.stdout.flush()
    
    def _animate(self):
        """Animation loop (runs in separate thread)"""
        idx = 0
        while self.running:
            frame = self.frames[idx % len(self.frames)]
            sys.stdout.write(f'\r{frame} {self.message}...')
            sys.stdout.flush()
            idx += 1
            threading.Event().wait(0.1)  # 100ms per frame


# ==================== IMPROVED INPUT HANDLER ====================

async def get_user_input_with_feedback(prompt_text: str = "You: ") -> str:
    """
    Get user input with better UX
    
    Shows prompt, waits for input, then shows working indicator
    while processing happens.
    
    Args:
        prompt_text: The prompt to show (default: "You: ")
        
    Returns:
        User's input text
    """
    
    # Show prompt and get input
    print(prompt_text, end='', flush=True)
    user_input = await asyncio.get_event_loop().run_in_executor(
        None, sys.stdin.readline
    )
    
    return user_input.strip()


def show_working(message: str = "Thinking", style: str = "dots") -> WorkingIndicator:
    """
    Create and start a working indicator
    
    Usage:
        spinner = show_working("Processing")
        # ... do work ...
        spinner.stop()
    
    Args:
        message: Message to show (default: "Thinking")
        style: Spinner style (default: "dots")
        
    Returns:
        WorkingIndicator instance (already started)
    """
    
    indicator = WorkingIndicator(message, style)
    indicator.start()
    return indicator


# ==================== EXAMPLE USAGE ====================

"""
EXAMPLE: How to integrate into jarvis_terminal.py

OLD CODE:
    while True:
        user_input = input("You: ").strip()
        if not user_input:
            continue
        
        response = await jarvis.process_user_input(user_input)
        print(f"\nJARVIS: {response}\n")


NEW CODE:
    while True:
        # Get input (no spinner yet)
        user_input = await get_user_input_with_feedback("You: ")
        if not user_input:
            continue
        
        # Show working indicator while processing
        spinner = show_working("Thinking", style="dots")
        
        try:
            response = await jarvis.process_user_input(user_input)
        finally:
            # Always stop spinner, even if there's an error
            spinner.stop()
        
        # Now show response
        print(f"JARVIS: {response}\n")


ALTERNATIVE: Context manager style

    while True:
        user_input = await get_user_input_with_feedback("You: ")
        if not user_input:
            continue
        
        with WorkingIndicatorContext("Thinking"):
            response = await jarvis.process_user_input(user_input)
        
        print(f"JARVIS: {response}\n")
"""


class WorkingIndicatorContext:
    """
    Context manager for working indicator
    
    Usage:
        with WorkingIndicatorContext("Processing"):
            # do work
            pass
        # spinner automatically stops
    """
    
    def __init__(self, message: str = "Working", style: str = "dots"):
        self.indicator = WorkingIndicator(message, style)
    
    def __enter__(self):
        self.indicator.start()
        return self.indicator
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.indicator.stop()
        return False  # Don't suppress exceptions


# ==================== INTEGRATION HELPER ====================

def get_terminal_improvements_patch():
    """
    Returns the code changes needed for jarvis_terminal.py
    
    Returns:
        Dict with old code and new code snippets
    """
    
    return {
        "imports": {
            "old": "import sys",
            "new": """import sys
from terminal_ux_fix import get_user_input_with_feedback, WorkingIndicatorContext"""
        },
        
        "main_loop": {
            "old": """        user_input = input("You: ").strip()
        if not user_input:
            continue
        
        response = await jarvis.process_user_input(user_input)
        print(f"\\nJARVIS: {response}\\n")""",
            
            "new": """        user_input = await get_user_input_with_feedback("You: ")
        if not user_input:
            continue
        
        # Show working indicator while processing
        with WorkingIndicatorContext("Thinking"):
            response = await jarvis.process_user_input(user_input)
        
        print(f"JARVIS: {response}\\n")"""
        }
    }


# ==================== VISUAL STYLES DEMO ====================

def demo_all_styles():
    """Demo all available spinner styles"""
    
    import time
    
    styles = ["dots", "line", "arrow", "dots_simple", "pulse", "thinking"]
    
    print("\nSpinner Styles Demo:\n")
    
    for style in styles:
        print(f"Style: {style}")
        spinner = show_working(f"Testing {style}", style=style)
        time.sleep(2)
        spinner.stop()
        print()  # New line after each demo
    
    print("Demo complete!\n")


if __name__ == "__main__":
    # Run demo if executed directly
    demo_all_styles()