# websocket_log_handler.py
"""
WebSocket Log Handler

Broadcasts Python logging events to WebSocket clients
"""

import logging
import asyncio
from datetime import datetime


class WebSocketLogHandler(logging.Handler):
    """
    Custom logging handler that broadcasts logs via WebSocket
    """
    
    def __init__(self, event_broadcaster):
        """
        Initialize handler
        
        Args:
            event_broadcaster: EventBroadcaster instance
        """
        super().__init__()
        self.broadcaster = event_broadcaster
        self.loop = None
    
    def emit(self, record):
        """
        Emit a log record
        
        Args:
            record: LogRecord to emit
        """
        if not self.broadcaster:
            return
        
        try:
            # Get or create event loop
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # No running loop - create task for next loop
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
            
            # Schedule the async broadcast
            asyncio.create_task(self._emit_async(record))
            
        except Exception as e:
            # Don't let logging errors break the application
            print(f"Error in WebSocketLogHandler: {e}")
    
    async def _emit_async(self, record):
        """
        Async emit implementation
        
        Args:
            record: LogRecord to emit
        """
        try:
            from event_broadcaster import Event, EventType
            
            # Map log levels to event data
            level_map = {
                'DEBUG': 'DEBUG',
                'INFO': 'INFO',
                'WARNING': 'WARNING',
                'ERROR': 'ERROR',
                'CRITICAL': 'ERROR'
            }
            
            # Create event
            event = Event(
                event_type=EventType.LOG_EVENT,
                data={
                    "level": level_map.get(record.levelname, 'INFO'),
                    "category": record.name.upper().replace('.', '_'),
                    "message": self.format(record),
                    "timestamp": datetime.fromtimestamp(record.created).isoformat()
                },
                min_auth_level=1  # All authenticated users can see logs
            )
            
            # Broadcast
            await self.broadcaster.broadcast(event)
            
        except Exception as e:
            print(f"Error broadcasting log: {e}")


def setup_websocket_logging(event_broadcaster, logger_names=None):
    """
    Setup WebSocket logging for specified loggers
    
    Args:
        event_broadcaster: EventBroadcaster instance
        logger_names: List of logger names to add handler to.
                     If None, adds to root logger.
    
    Returns:
        WebSocketLogHandler instance
    """
    
    # Create handler
    ws_handler = WebSocketLogHandler(event_broadcaster)
    ws_handler.setLevel(logging.INFO)
    
    # Create formatter
    formatter = logging.Formatter(
        '%(name)s - %(levelname)s - %(message)s'
    )
    ws_handler.setFormatter(formatter)
    
    # Add to specified loggers or root
    if logger_names:
        for logger_name in logger_names:
            logger = logging.getLogger(logger_name)
            logger.addHandler(ws_handler)
    else:
        logging.getLogger().addHandler(ws_handler)
    
    return ws_handler