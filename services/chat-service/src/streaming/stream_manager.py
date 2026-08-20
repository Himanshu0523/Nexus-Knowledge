from typing import AsyncGenerator, Optional, Dict, Any
import asyncio
import logging
from .events import (
    StreamEvent, StatusEvent, TokenEvent, SourceEvent,
    ToolStartEvent, ToolResultEvent, ErrorEvent, DoneEvent,
    MetadataEvent, StreamStatus
)

logger = logging.getLogger(__name__)

class StreamManager:
    """Manage streaming responses"""
    
    def __init__(self):
        self.active_streams = {}
        self.max_buffer_size = 100
        self.stream_timeout = 300  # 5 minutes
    
    async def create_stream(
        self,
        stream_id: str,
        content_generator: AsyncGenerator[StreamEvent, None]
    ) -> AsyncGenerator[StreamEvent, None]:
        """Create a managed stream with buffering and timeout"""
        buffer = []
        stream_started = False
        
        try:
            async for event in content_generator:
                if not stream_started:
                    # Send initial status
                    yield StatusEvent(
                        status=StreamStatus.STARTED,
                        message="Stream started"
                    )
                    stream_started = True
                
                yield event
                
                # Buffer for replay if needed
                buffer.append(event)
                if len(buffer) > self.max_buffer_size:
                    buffer.pop(0)
        
        except asyncio.CancelledError:
            logger.info(f"Stream {stream_id} cancelled")
            yield StatusEvent(
                status=StreamStatus.CANCELLED,
                message="Stream cancelled"
            )
            raise
        
        except Exception as e:
            logger.error(f"Stream {stream_id} error: {e}")
            yield ErrorEvent(
                code="STREAM_ERROR",
                message=str(e)
            )
            yield DoneEvent(
                status=StreamStatus.FAILED
            )
        
        finally:
            # Clean up
            self.active_streams.pop(stream_id, None)
    
    async def create_token_stream(
        self,
        stream_id: str,
        token_generator: AsyncGenerator[str, None],
        metadata: Dict[str, Any] = None
    ) -> AsyncGenerator[StreamEvent, None]:
        """Create a token stream from text chunks"""
        if metadata:
            yield MetadataEvent(metadata=metadata)
        
        token_index = 0
        async for token in token_generator:
            yield TokenEvent(
                content=token,
                token_index=token_index
            )
            token_index += 1
    
    async def create_tool_stream(
        self,
        stream_id: str,
        tool_executor,
        tool_name: str,
        arguments: Dict[str, Any]
    ) -> AsyncGenerator[StreamEvent, None]:
        """Create a tool execution stream"""
        # Send tool start event
        yield ToolStartEvent(
            tool_name=tool_name,
            arguments=arguments
        )
        
        # Execute tool
        try:
            result = await tool_executor.execute_tool(tool_name, arguments)
            
            yield ToolResultEvent(
                tool_name=tool_name,
                status=result.status,
                result=result.data,
                error=result.error.get("message") if result.error else None,
                execution_time=result.execution_time
            )
            
        except Exception as e:
            yield ErrorEvent(
                code="TOOL_EXECUTION_FAILED",
                message=str(e)
            )
    
    async def create_rag_stream(
        self,
        stream_id: str,
        rag_context_builder,
        query: str,
        tenant_id: str
    ) -> AsyncGenerator[StreamEvent, None]:
        """Create a RAG retrieval stream"""
        yield StatusEvent(
            status=StreamStatus.RETRIEVING,
            message="Retrieving relevant context..."
        )
        
        try:
            rag_context = await rag_context_builder.build_context(
                query,
                tenant_id
            )
            
            # Send source events
            for source in rag_context.get("sources", []):
                yield SourceEvent(**source)
            
            # Return context for LLM
            yield MetadataEvent(
                metadata={"rag_context": rag_context}
            )
            
        except Exception as e:
            yield ErrorEvent(
                code="RAG_RETRIEVAL_FAILED",
                message=str(e)
            )
