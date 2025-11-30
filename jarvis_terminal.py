# jarvis_terminal.py
"""
JARVIS Terminal Manager - WITH UX IMPROVEMENTS

Changes from original:
1. Added working indicator (spinner) while waiting for responses
2. Fixed phantom prompt issue
3. Better visual feedback
4. Cleaner response handling
"""

import asyncio
import websockets
import json
from datetime import datetime
from typing import Optional, Dict, Set
from pathlib import Path
import sys
import threading

JARVIS_PORT = 8766

# Import from jarvis_core
from jarvis_core import JarvisCore, Priority, PrivilegeLevel, Task


class TerminalConnection:
    """Represents a connected terminal"""
    
    def __init__(
        self,
        terminal_id: int,
        websocket: websockets.WebSocketServerProtocol,
        terminal_type: str,
        name: str,
        privilege: PrivilegeLevel
    ):
        self.terminal_id = terminal_id
        self.websocket = websocket
        self.terminal_type = terminal_type
        self.name = name
        self.privilege = privilege
        self.connected_at = datetime.now()
        self.last_activity = datetime.now()
    
    async def send(self, message: str):
        """Send message to terminal"""
        try:
            await self.websocket.send(json.dumps({
                "type": "response",
                "content": message,
                "timestamp": datetime.now().isoformat()
            }))
            self.last_activity = datetime.now()
        except Exception as e:
            print(f"Error sending to terminal {self.terminal_id}: {e}")
    
    async def receive(self) -> Optional[Dict]:
        """Receive message from terminal"""
        try:
            message = await self.websocket.recv()
            self.last_activity = datetime.now()
            return json.loads(message)
        except websockets.exceptions.ConnectionClosed:
            return None
        except Exception as e:
            print(f"Error receiving from terminal {self.terminal_id}: {e}")
            return None


class TerminalManager:
    """Manages all terminal connections to Jarvis"""
    
    def __init__(self, jarvis_core: JarvisCore):
        self.jarvis = jarvis_core
        self.connections: Dict[int, TerminalConnection] = {}
        self.next_terminal_id = 2  # 0=system, 1=scheduler, 2+=external
        self.websocket_server = None
        self.system_terminal = None  # Add this
        
    async def start_websocket_server(self, host: str = "0.0.0.0", port: int = 8765):
        """Start WebSocket server for terminal connections"""
        print(f"\n🔌 Starting WebSocket server on {host}:{port}")
        
        async def handler(websocket):  # Remove 'path' parameter
            await self._handle_websocket_connection(websocket)
        
        self.websocket_server = await websockets.serve(handler, host, port)
        print(f"✅ WebSocket server running on ws://{host}:{port}")
            
    async def _handle_websocket_connection(
        self,
        websocket: websockets.WebSocketServerProtocol
    ):
        """Handle a new WebSocket connection"""
        
        terminal_id = None
        connection = None
        
        print(f"🔍 DEBUG: New connection from {websocket.remote_address}")
        
        try:
            # Wait for authentication/registration message
            print(f"🔍 DEBUG: Waiting for auth message...")
            auth_msg = await websocket.recv()
            auth_data = json.loads(auth_msg)
            
            if auth_data.get("type") != "register":
                await websocket.send(json.dumps({
                    "error": "First message must be registration"
                }))
                return
            
            # Register the terminal
            terminal_type = auth_data.get("terminal_type", "unknown")
            name = auth_data.get("name", f"Terminal {self.next_terminal_id}")
            privilege = PrivilegeLevel(auth_data.get("privilege", PrivilegeLevel.USER))
            
            # Assign terminal ID
            terminal_id = self.next_terminal_id
            self.next_terminal_id += 1
            
            # Create connection
            connection = TerminalConnection(
                terminal_id=terminal_id,
                websocket=websocket,
                terminal_type=terminal_type,
                name=name,
                privilege=privilege
            )
            
            self.connections[terminal_id] = connection
            
            # Register with Jarvis core
            self.jarvis.register_terminal(
                terminal_id=terminal_id,
                terminal_type=terminal_type,
                name=name,
                privilege=privilege
            )
            
            # Send registration confirmation
            await websocket.send(json.dumps({
                "type": "registered",
                "terminal_id": terminal_id,
                "message": f"Registered as Terminal {terminal_id}: {name}"
            }))
            
            print(f"📡 Terminal {terminal_id} ({name}) connected [{privilege.name}]")
            
            # Handle messages from this terminal
            async for message in websocket:
                try:
                    data = json.loads(message)
                    await self._handle_terminal_message(terminal_id, data)
                except json.JSONDecodeError:
                    await websocket.send(json.dumps({
                        "error": "Invalid JSON"
                    }))
        
        except websockets.exceptions.ConnectionClosed:
            pass
        except Exception as e:
            print(f"❌ WebSocket error: {e}")
        
        finally:
            # Clean up on disconnect
            if terminal_id and terminal_id in self.connections:
                print(f"📡 Terminal {terminal_id} disconnected")
                self.jarvis.disconnect_terminal(terminal_id)
                del self.connections[terminal_id]
    
    async def _handle_terminal_message(self, terminal_id: int, data: Dict):
        """Handle a message from a terminal"""
        
        msg_type = data.get("type")
        
        if msg_type == "task":
            # Terminal is sending a task
            content = data.get("content", "")
            priority = Priority(data.get("priority", Priority.USER))
            
            await self.jarvis.receive_from_terminal(
                terminal_id=terminal_id,
                content=content,
                priority=priority
            )
        
        elif msg_type == "ping":
            # Heartbeat
            connection = self.connections.get(terminal_id)
            if connection:
                await connection.send("pong")
        
        else:
            print(f"⚠️  Unknown message type from Terminal {terminal_id}: {msg_type}")
    
    async def send_to_terminal(self, terminal_id: int, content: str):
        """Send response to a specific terminal"""
        connection = self.connections.get(terminal_id)
        
        if connection:
            await connection.send(content)
        else:
            print(f"⚠️  Cannot send to disconnected Terminal {terminal_id}")
    
    async def broadcast(self, content: str, exclude: Optional[Set[int]] = None):
        """Broadcast message to all connected terminals"""
        exclude = exclude or set()
        
        for tid, conn in self.connections.items():
            if tid not in exclude:
                await conn.send(content)


# ==================== SPINNER FOR UX ====================

class WorkingSpinner:
    """Non-blocking spinner for terminal feedback"""
    
    def __init__(self, message: str = "Thinking"):
        self.message = message
        self.running = False
        self.thread = None
        self.frames = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    
    def start(self):
        """Start spinner in background thread"""
        if self.running:
            return
        
        self.running = True
        self.thread = threading.Thread(target=self._animate, daemon=True)
        self.thread.start()
    
    def stop(self):
        """Stop spinner and clear line"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=0.5)
        
        # Clear the spinner line
        sys.stdout.write('\r' + ' ' * (len(self.message) + 5) + '\r')
        sys.stdout.flush()
    
    def _animate(self):
        """Animation loop (runs in thread)"""
        idx = 0
        while self.running:
            frame = self.frames[idx % len(self.frames)]
            sys.stdout.write(f'\r{frame} {self.message}...')
            sys.stdout.flush()
            idx += 1
            threading.Event().wait(0.1)


# ==================== TEXT TERMINAL FOR TESTING (IMPROVED) ====================

class TextTerminal:
    """Simple text-based terminal for testing Jarvis - WITH UX IMPROVEMENTS"""
    
    def __init__(self, host: str = "localhost", port: int = JARVIS_PORT):
        self.host = host
        self.port = port
        self.ws = None
        self.terminal_id = None
        self.running = False
        self.spinner = None
        self.waiting_for_response = False
        self.response_received = asyncio.Event()
        
    async def connect(
        self,
        name: str = "Text Terminal",
        privilege: int = PrivilegeLevel.ADMIN
    ):
        """Connect to Jarvis WebSocket server"""
        
        try:
            self.ws = await websockets.connect(f"ws://{self.host}:{self.port}")
            
            # Register
            await self.ws.send(json.dumps({
                "type": "register",
                "terminal_type": "text",
                "name": name,
                "privilege": privilege
            }))
            
            # Wait for registration confirmation
            response = await self.ws.recv()
            data = json.loads(response)
            
            if data.get("type") == "registered":
                self.terminal_id = data.get("terminal_id")
                print(f"\n✅ {data.get('message')}")
                print(f"🔐 Privilege Level: {PrivilegeLevel(privilege).name}")
                return True
            else:
                print(f"❌ Registration failed: {data}")
                return False
        
        except Exception as e:
            print(f"❌ Connection failed: {e}")
            return False
    
    async def send_task(self, content: str, priority: int = Priority.USER):
        if not self.ws:
            print("❌ Not connected")
            return
        
        try:
            # Clear the event (we're waiting for a new response)
            self.response_received.clear()  # ← ADD THIS
            
            # Start spinner to show we're waiting
            self.waiting_for_response = True
            self.spinner = WorkingSpinner("Thinking")
            self.spinner.start()
            
            await self.ws.send(json.dumps({
                "type": "task",
                "content": content,
                "priority": priority
            }))
            
            # WAIT for response before continuing
            await self.response_received.wait()  # ← ADD THIS (CRITICAL!)
            
        except Exception as e:
            if self.spinner:
                self.spinner.stop()
            self.waiting_for_response = False
            self.response_received.set()  # ← ADD THIS (unblock on error)
            print(f"❌ Error sending task: {e}")  
    
    async def receive_responses(self):
        """Listen for responses from Jarvis - IMPROVED VERSION"""
        
        try:
            async for message in self.ws:
                data = json.loads(message)
                
                if data.get("type") == "response":
                    # Stop spinner before showing response
                    if self.spinner and self.waiting_for_response:
                        self.spinner.stop()
                        self.waiting_for_response = False
                    
                    content = data.get("content", "")
                    timestamp = data.get("timestamp", "")
                    
                    # Show response
                    print(f"🤖 Jarvis [{timestamp}]:")
                    print(content)
                    print()  # Blank line for readability
                
                    # Signal that response is complete (unblock send_task)
                    self.response_received.set()
                    
                    # DON'T print prompt here - let interactive_loop handle it
        
        except websockets.exceptions.ConnectionClosed:
            print("\n\n❌ Connection closed")
            self.running = False
            if self.spinner:
                self.spinner.stop()
            self.response_received.set()
                
        except Exception as e:
            print(f"\n\n❌ Error: {e}")
            self.running = False
            if self.spinner:
                self.spinner.stop()
            self.response_received.set()
            
    async def interactive_loop(self):
        """Interactive input loop - IMPROVED VERSION"""
        
        self.running = True
        
        # Start response listener in background
        asyncio.create_task(self.receive_responses())
        
        print("\n" + "=" * 60)
        print("  TEXT TERMINAL - Connected to Jarvis")
        print("=" * 60)
        print("  Commands:")
        print("    /quit     - Disconnect and exit")
        print("    /status   - Request system status")
        print("    /help     - Show this help")
        print("    Analysis  - Enter analysis mode")
        print("=" * 60)
        print()
        
        # Run input loop in executor to not block asyncio
        loop = asyncio.get_event_loop()
        
        while self.running:
            try:
                # Show prompt (only here, not in receive_responses)
                print("🎤 You: ", end="", flush=True)
                
                # Read input in non-blocking way
                user_input = await loop.run_in_executor(None, sys.stdin.readline)
                user_input = user_input.strip()
                
                if not user_input:
                    continue
                
                # Handle commands
                if user_input == "/quit":
                    print("\n👋 Disconnecting...")
                    self.running = False
                    break
                
                elif user_input == "/status":
                    await self.send_task("status")
                
                elif user_input == "/help":
                    print("\n📖 Available commands:")
                    print("  /quit     - Exit")
                    print("  /status   - System status")
                    print("  Analysis  - Enter analysis mode")
                    print("  Or just type naturally to Jarvis\n")
                
                else:
                    # Send as task to Jarvis (this starts the spinner)
                    await self.send_task(user_input)
            
            except KeyboardInterrupt:
                print("\n\n👋 Interrupted, disconnecting...")
                self.running = False
                if self.spinner:
                    self.spinner.stop()
                break
            except Exception as e:
                print(f"\n❌ Error: {e}")
                if self.spinner:
                    self.spinner.stop()
                break
        
        # Close connection
        if self.ws:
            await self.ws.close()
            print("✅ Disconnected")
    
    async def run(self):
        """Main entry point"""
        
        print("\n" + "═" * 60)
        print("       JARVIS TEXT TERMINAL")
        print("═" * 60)
        print(f"  Connecting to ws://{self.host}:{self.port}...")
        print("═" * 60)
        
        connected = await self.connect()
        
        if connected:
            await self.interactive_loop()
        else:
            print("\n❌ Failed to connect. Is Jarvis running?")


# ==================== INTEGRATION WITH JARVIS CORE ====================

async def start_terminal_manager(jarvis_core: JarvisCore, port: int = JARVIS_PORT):
    """Start the terminal manager as part of Jarvis"""
    
    manager = TerminalManager(jarvis_core)
    
    # Patch Jarvis core to use terminal manager for responses
    original_send = jarvis_core.send_to_terminal
    
    async def patched_send(terminal_id: int, content: str):
        # Terminal 0 just logs, doesn't actually send
        if terminal_id == 0:
            print(f"[Terminal 0 thought]: {content[:100]}...")
            return
        
        await manager.send_to_terminal(terminal_id, content)
    
    jarvis_core.send_to_terminal = patched_send
    
    # Start WebSocket server
    await manager.start_websocket_server(port=port)
    
    return manager


# ==================== STANDALONE TESTING ====================

async def test_text_terminal():
    """Test the text terminal standalone"""
    
    terminal = TextTerminal()
    await terminal.run()


if __name__ == "__main__":
    """
    Run this to test the text terminal.
    
    Make sure jarvis_core.py is running first in another terminal:
        python jarvis_core.py
    
    Then run this:
        python jarvis_terminal.py
    """
    
    print("\n🧪 Running Text Terminal Test")
    print("Make sure jarvis_core.py is running!\n")
    
    asyncio.run(test_text_terminal())