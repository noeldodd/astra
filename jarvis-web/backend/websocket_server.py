# websocket_server.py
"""
JARVIS WebSocket Server

FastAPI-based WebSocket server for real-time communication with JARVIS.

Features:
- Multi-user WebSocket connections
- JWT authentication
- In-band (chat) and Out-of-band (events) messaging
- Auth-gated information delivery
- Connection management and auto-reconnect
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, Set, Optional, Any
import asyncio
import json
import logging
import os
from datetime import datetime
from pydantic import BaseModel
from dotenv import load_dotenv

from auth_manager import AuthManager, User
from event_broadcaster import EventBroadcaster, Event, EventType

# Load environment variables
load_dotenv()

# Configuration from environment
WEBSOCKET_PORT = int(os.getenv('WEBSOCKET_PORT', 8000))
HOST = os.getenv('HOST', '0.0.0.0')
JWT_SECRET = os.getenv('JWT_SECRET', 'your-secret-key-change-this-in-production')
CORS_ORIGINS = os.getenv('CORS_ORIGINS', 'http://localhost:3000,http://localhost:5173').split(',')

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(title="JARVIS WebSocket Server", version="1.0.0")

# CORS middleware (allow frontend to connect)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,  # From environment variable
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# Initialize managers
auth_manager = AuthManager()
event_broadcaster = EventBroadcaster()

# Active WebSocket connections
class ConnectionManager:
    """Manage active WebSocket connections"""
    
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}  # user_id -> websocket
        self.user_sessions: Dict[str, dict] = {}  # user_id -> session_data
    
    async def connect(self, websocket: WebSocket, user: User):
        """Register new WebSocket connection"""
        await websocket.accept()
        
        # Disconnect existing session if any
        if user.id in self.active_connections:
            old_ws = self.active_connections[user.id]
            try:
                await old_ws.close()
            except:
                pass
        
        self.active_connections[user.id] = websocket
        self.user_sessions[user.id] = {
            "user": user,
            "connected_at": datetime.now().isoformat(),
            "messages_sent": 0,
            "messages_received": 0
        }
        
        logger.info(f"User {user.username} connected (auth level: {user.auth_level})")
        
        # Send connection success message
        await self.send_to_user(user.id, {
            "type": "connection_established",
            "user": {
                "id": user.id,
                "username": user.username,
                "auth_level": user.auth_level
            },
            "timestamp": datetime.now().isoformat()
        })
    
    def disconnect(self, user_id: str):
        """Remove WebSocket connection"""
        if user_id in self.active_connections:
            del self.active_connections[user_id]
        if user_id in self.user_sessions:
            session = self.user_sessions[user_id]
            logger.info(f"User {session['user'].username} disconnected")
            del self.user_sessions[user_id]
    
    async def send_to_user(self, user_id: str, message: dict):
        """Send message to specific user"""
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_json(message)
                if user_id in self.user_sessions:
                    self.user_sessions[user_id]["messages_sent"] += 1
            except Exception as e:
                logger.error(f"Error sending to user {user_id}: {e}")
                self.disconnect(user_id)
    
    async def broadcast(self, message: dict, min_auth_level: int = 0):
        """Broadcast message to all users with sufficient auth level"""
        disconnected = []
        
        for user_id, websocket in self.active_connections.items():
            session = self.user_sessions.get(user_id)
            if not session:
                continue
            
            user = session["user"]
            if user.auth_level >= min_auth_level:
                try:
                    await websocket.send_json(message)
                    session["messages_sent"] += 1
                except Exception as e:
                    logger.error(f"Error broadcasting to {user_id}: {e}")
                    disconnected.append(user_id)
        
        # Clean up disconnected users
        for user_id in disconnected:
            self.disconnect(user_id)
    
    def get_user(self, user_id: str) -> Optional[User]:
        """Get user from active session"""
        session = self.user_sessions.get(user_id)
        return session["user"] if session else None

connection_manager = ConnectionManager()

# ==================== API ENDPOINTS ====================

class LoginRequest(BaseModel):
    username: str
    password: str

class RegisterRequest(BaseModel):
    username: str
    password: str
    email: Optional[str] = None

@app.post("/api/auth/login")
async def login(request: LoginRequest):
    """Login and get JWT token"""
    user = auth_manager.authenticate(request.username, request.password)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password"
        )
    
    token = auth_manager.create_token(user)
    
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": {
            "id": user.id,
            "username": user.username,
            "auth_level": user.auth_level
        }
    }

@app.post("/api/auth/register")
async def register(request: RegisterRequest):
    """Register new user"""
    try:
        user = auth_manager.create_user(
            username=request.username,
            password=request.password,
            email=request.email
        )
        
        token = auth_manager.create_token(user)
        
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "username": user.username,
                "auth_level": user.auth_level
            }
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@app.get("/api/auth/verify")
async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Verify JWT token"""
    user = auth_manager.verify_token(credentials.credentials)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    return {
        "valid": True,
        "user": {
            "id": user.id,
            "username": user.username,
            "auth_level": user.auth_level
        }
    }

@app.get("/api/status")
async def get_status():
    """Get server status"""
    return {
        "status": "online",
        "active_connections": len(connection_manager.active_connections),
        "timestamp": datetime.now().isoformat()
    }

# ==================== WEBSOCKET ENDPOINT ====================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    Main WebSocket endpoint
    
    Expected first message from client:
    {
        "type": "auth",
        "token": "jwt_token_here"
    }
    """
    
    user = None
    user_id = None
    
    try:
        # Wait for authentication message
        await websocket.accept()
        
        # Wait for auth with timeout
        auth_message = await asyncio.wait_for(
            websocket.receive_json(),
            timeout=10.0
        )
        
        if auth_message.get("type") != "auth":
            await websocket.send_json({
                "type": "error",
                "error": "First message must be auth"
            })
            await websocket.close()
            return
        
        # Verify token
        token = auth_message.get("token")
        user = auth_manager.verify_token(token)
        
        if not user:
            await websocket.send_json({
                "type": "error",
                "error": "Invalid or expired token"
            })
            await websocket.close()
            return
        
        user_id = user.id
        
        # Register connection
        await connection_manager.connect(websocket, user)
        
        # Subscribe to events based on auth level
        event_broadcaster.subscribe(user_id, user.auth_level, connection_manager.send_to_user)
        
        # Handle messages
        while True:
            message = await websocket.receive_json()
            
            # Track received message
            if user_id in connection_manager.user_sessions:
                connection_manager.user_sessions[user_id]["messages_received"] += 1
            
            # Route message based on type
            await handle_client_message(user, message)
    
    except WebSocketDisconnect:
        logger.info(f"Client disconnected: {user.username if user else 'unknown'}")
    
    except asyncio.TimeoutError:
        logger.warning("Authentication timeout")
        try:
            await websocket.send_json({
                "type": "error",
                "error": "Authentication timeout"
            })
            await websocket.close()
        except:
            pass
    
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    
    finally:
        # Clean up
        if user_id:
            connection_manager.disconnect(user_id)
            event_broadcaster.unsubscribe(user_id)

# ==================== MESSAGE HANDLERS ====================

async def handle_client_message(user: User, message: dict):
    """
    Handle incoming client messages
    
    Message types:
    - user_message: Chat message to JARVIS
    - plan_approval: Approve/reject plan
    - system_command: System commands (admin only)
    """
    
    msg_type = message.get("type")
    
    if msg_type == "user_message":
        await handle_user_message(user, message)
    
    elif msg_type == "plan_approval":
        await handle_plan_approval(user, message)
    
    elif msg_type == "system_command":
        if user.auth_level >= 3:  # Admin only
            await handle_system_command(user, message)
        else:
            await connection_manager.send_to_user(user.id, {
                "type": "error",
                "error": "Insufficient permissions"
            })
    
    else:
        logger.warning(f"Unknown message type: {msg_type}")

async def handle_user_message(user: User, message: dict):
    """Handle chat message from user"""
    content = message.get("content", "").strip()
    
    if not content:
        return
    
    logger.info(f"User message from {user.username}: {content[:50]}...")
    
    # TODO: Send to JARVIS core for processing
    # For now, echo back
    await connection_manager.send_to_user(user.id, {
        "type": "assistant_message",
        "content": f"Received: {content}",
        "timestamp": datetime.now().isoformat()
    })
    
    # Broadcast user activity (auth level 2+)
    await event_broadcaster.broadcast(Event(
        event_type=EventType.SYSTEM_STATUS,
        data={
            "user": user.username,
            "action": "sent_message",
            "preview": content[:30] + "..." if len(content) > 30 else content
        },
        min_auth_level=2
    ))

async def handle_plan_approval(user: User, message: dict):
    """Handle plan approval/rejection"""
    plan_id = message.get("plan_id")
    approved = message.get("approved", False)
    
    action = "approved" if approved else "rejected"
    logger.info(f"Plan {plan_id} {action} by {user.username}")

    # TODO: Send to JARVIS core
    
    await connection_manager.send_to_user(user.id, {
        "type": "plan_approval_received",
        "plan_id": plan_id,
        "approved": approved
    })

async def handle_system_command(user: User, message: dict):
    """Handle system commands (admin only)"""
    command = message.get("command")
    
    logger.info(f"System command from {user.username}: {command}")
    
    # TODO: Implement system commands
    
    await connection_manager.send_to_user(user.id, {
        "type": "system_response",
        "command": command,
        "result": "Command received"
    })

# ==================== STARTUP/SHUTDOWN ====================

@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    logger.info("JARVIS WebSocket Server starting...")
    
    # Create default admin user if none exists
    if not auth_manager.get_user_by_username("admin"):
        admin = auth_manager.create_user(
            username="admin",
            password="admin123",  # Change this!
            auth_level=4
        )
        logger.info("Created default admin user (username: admin, password: admin123)")
        logger.warning("⚠️  CHANGE THE DEFAULT ADMIN PASSWORD!")
    
    logger.info("WebSocket server ready!")

@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("JARVIS WebSocket Server shutting down...")
    
    # Disconnect all clients
    for user_id in list(connection_manager.active_connections.keys()):
        try:
            await connection_manager.active_connections[user_id].close()
        except:
            pass
        connection_manager.disconnect(user_id)
    
    logger.info("Server shutdown complete")

# ==================== MAIN ====================

if __name__ == "__main__":
    import uvicorn
    
    print(f"Starting JARVIS WebSocket Server on {HOST}:{WEBSOCKET_PORT}")
    
    uvicorn.run(
        "websocket_server:app",
        host=HOST,
        port=WEBSOCKET_PORT,
        reload=True,
        log_level="info"
    )