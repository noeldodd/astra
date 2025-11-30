import asyncio
import websockets
import json
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get the WebSocket port from environment variables
# Use like: async with websockets.serve(echo_handler, "localhost", WEBSOCKET_PORT): ...
WEBSOCKET_PORT = int(os.getenv('WEBSOCKET_PORT', 8008))

async def test_websocket():
    # Connect
    async with websockets.connect(f"ws://localhost:{WEBSOCKET_PORT}/ws") as ws:
        # Authenticate
        await ws.send(json.dumps({
            "type": "auth",
            "token": "YOUR_TOKEN_HERE"
        }))
        
        # Receive confirmation
        response = await ws.recv()
        print(f"Auth response: {response}")
        
        # Send message
        await ws.send(json.dumps({
            "type": "user_message",
            "content": "Hello JARVIS!"
        }))
        
        # Receive messages
        async for message in ws:
            print(f"Received: {message}")

asyncio.run(test_websocket())