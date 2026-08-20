from typing import AsyncGenerator, Optional
import json
import asyncio
from .events import StreamEvent

class SSEStream:
    """Server-Sent Events stream handler"""
    
    def __init__(self):
        self.retry_timeout = 3000  # milliseconds
        self.heartbeat_interval = 15  # seconds
    
    async def format_event(self, event: StreamEvent) -> str:
        """Format a stream event as SSE"""
        data = json.dumps(event.to_dict())
        return f"data: {data}\n\n"
    
    async def format_heartbeat(self) -> str:
        """Format heartbeat event"""
        return f": heartbeat\n\n"
    
    async def stream_events(self, events: AsyncGenerator[StreamEvent, None]) -> AsyncGenerator[str, None]:
        """Stream events as SSE with heartbeat"""
        async for event in events:
            yield await self.format_event(event)
    
    def create_sse_response(self):
        """Create SSE response headers"""
        return {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable proxy buffering
        }

class SSEManager:
    """Manager for SSE connections"""
    
    def __init__(self):
        self.active_streams = {}
        self.max_streams_per_user = 5
    
    def register_stream(self, stream_id: str, user_id: str):
        """Register a new stream"""
        if user_id not in self.active_streams:
            self.active_streams[user_id] = set()
        
        if len(self.active_streams[user_id]) >= self.max_streams_per_user:
            raise Exception("Too many active streams")
        
        self.active_streams[user_id].add(stream_id)
    
    def unregister_stream(self, stream_id: str, user_id: str):
        """Unregister a stream"""
        if user_id in self.active_streams:
            self.active_streams[user_id].discard(stream_id)
            if not self.active_streams[user_id]:
                del self.active_streams[user_id]
    
    def get_active_streams(self, user_id: str):
        """Get active streams for user"""
        return self.active_streams.get(user_id, set())

# Global SSE manager
sse_manager = SSEManager()
