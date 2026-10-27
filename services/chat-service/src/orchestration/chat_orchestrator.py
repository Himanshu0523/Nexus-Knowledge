from typing import Dict, Any, Optional, List, AsyncGenerator
import asyncio
import logging
import json
import uuid
import time
from datetime import datetime

from services.conversation_service import ConversationService
from services.context_builder import ContextBuilder
from services.llm_service import LLMService
from llm.stream_client import LLMStreamClient
from rag.context_builder import RAGContextBuilder
from rag.retriever import Retriever
from streaming.events import (
    StreamEvent, StatusEvent, TokenEvent, SourceEvent,
    ToolStartEvent, ToolResultEvent, ErrorEvent, DoneEvent,
    MetadataEvent, StreamStatus
)
from streaming.stream_manager import StreamManager
from security.prompt_guard import prompt_guard
from security.output_guard import output_guard


from shared.governance import governance_engine

# Kafka producer — imported with graceful fallback
try:
    from kafka.producer import kafka_producer
    from shared.events.chat import (
        message_created_event, response_completed_event, response_failed_event, budget_alert_event
    )
    _KAFKA_EVENTS_AVAILABLE = True
except ImportError:
    kafka_producer = None
    _KAFKA_EVENTS_AVAILABLE = False

try:
    from agent_runtime.mesh_router import EnterpriseMeshRouter, AgentDomain
except ImportError:
    from src.agent_runtime.mesh_router import EnterpriseMeshRouter, AgentDomain

logger = logging.getLogger(__name__)

class ChatOrchestrator:
    """Orchestrate chat with memory, RAG, streaming, security, and AI Governance support"""
    
    def __init__(self, db_session):
        self.db = db_session
        self.conversation_service = ConversationService(db_session)
        self.context_builder = ContextBuilder(self.conversation_service)
        self.llm_service = LLMService()
        self.llm_stream_client = LLMStreamClient()
        self.rag_context_builder = RAGContextBuilder()
        self.retriever = Retriever()
        self.stream_manager = StreamManager()
        self.mesh_router = EnterpriseMeshRouter(db_session)
        self.max_agent_iterations = 5
    
    async def process_message(self, request: Dict[str, Any], tenant_id: str = "default") -> Dict[str, Any]:
        """Process a chat message synchronously with optional RAG and AI Governance"""
        conversation_id = request["conversation_id"]
        message = request["message"]
        knowledge_base_id = request.get("knowledge_base_id")
        requested_model = request.get("model")
        requested_tools = request.get("tools")

        # ── Phase 17: AI Gateway Governance Evaluation ──
        gov_result = governance_engine.evaluate_request(
            tenant_id=tenant_id,
            prompt=message,
            model=requested_model,
            requested_tools=requested_tools,
            knowledge_base_id=knowledge_base_id,
        )

        if not gov_result.allowed:
            logger.warning(f"[Governance] Request denied for tenant '{tenant_id}': {gov_result.denial_reason}")
            return {
                "conversation_id": conversation_id,
                "message_id": f"msg_{uuid.uuid4().hex[:10]}",
                "response": f"Governance Policy Denied: {gov_result.denial_reason}",
                "sources": [],
                "usage": {"input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
                "model": "governance-guard",
                "error_code": gov_result.error_code,
            }

        effective_message = gov_result.sanitized_prompt

        # ── Phase 9: Prompt Injection Protection ──
        is_safe, reason = prompt_guard.inspect(effective_message)
        if not is_safe:
            logger.warning(f"[Security] Blocked unsafe message in conv '{conversation_id}': {reason}")
            return {
                "conversation_id": conversation_id,
                "message_id": f"msg_{uuid.uuid4().hex[:10]}",
                "response": f"Security Alert: Your input was blocked by safety policy ({reason}).",
                "sources": [],
                "usage": {"input_tokens": 0, "output_tokens": 0},
                "model": "security-guard"
            }

        sanitized_message = prompt_guard.sanitize(effective_message)

        # ── Multi-Agent Collaborative Mesh Intent Routing ──
        domain = self.mesh_router.classify_intent(sanitized_message)
        if domain == AgentDomain.SQL_ANALYTICS:
            analytics_res = await self.mesh_router.sql_agent.execute_metrics_query(sanitized_message, tenant_id)
            return {
                "conversation_id": conversation_id,
                "message_id": f"msg_{uuid.uuid4().hex[:10]}",
                "response": analytics_res.response,
                "sources": [],
                "usage": {"input_tokens": len(sanitized_message) // 4, "output_tokens": len(analytics_res.response) // 4, "cost_usd": 0.0},
                "model": "sql-analytics-agent",
                "analytics_data": analytics_res.data,
                "rag_used": False
            }

        use_rag = bool(knowledge_base_id) or self._should_use_rag(sanitized_message)

        conversation_context = self.context_builder.build_context(
            conversation_id,
            sanitized_message
        )
        
        if use_rag:
            rag_context = await self.rag_context_builder.build_context(
                sanitized_message,
                tenant_id,
                knowledge_base_id
            )
            
            final_messages = self._combine_contexts(
                conversation_context,
                rag_context["messages"]
            )
            
            llm_response = await self.llm_service.generate_response(final_messages)
            llm_response["sources"] = rag_context.get("sources", [])
            llm_response["rag_used"] = True
            llm_response["graph_rag"] = rag_context.get("graph_rag", {})
            llm_response["crag"] = rag_context.get("crag")
        else:
            llm_response = await self.llm_service.generate_response(conversation_context)
            llm_response["sources"] = []
            llm_response["rag_used"] = False
        
        # ── Phase 9: Output Security Sanitization ──
        if "response" in llm_response:
            llm_response["response"] = output_guard.sanitize(llm_response["response"])

        # ── Phase 17: Record Usage & Enforce Data Retention ──
        usage = llm_response.get("usage", {})
        inp_toks = usage.get("input_tokens", len(sanitized_message) // 4)
        out_toks = usage.get("output_tokens", len(llm_response.get("response", "")) // 4)
        used_model = llm_response.get("model", "qwen")

        cost = governance_engine.record_usage(tenant_id, used_model, inp_toks, out_toks)
        if "usage" not in llm_response or not isinstance(llm_response["usage"], dict):
            llm_response["usage"] = {}
        llm_response["usage"]["cost_usd"] = cost

        if not gov_result.zero_retention_mode:
            self.conversation_service.add_message(
                conversation_id=conversation_id,
                role="user",
                content=sanitized_message,
                model=used_model
            )
            
            self.conversation_service.add_message(
                conversation_id=conversation_id,
                role="assistant",
                content=llm_response["response"],
                model=used_model
            )
        else:
            logger.info(f"[Governance] Zero data retention active for tenant '{tenant_id}'. Skipping conversation log persistence.")

        # Publish Kafka events asynchronously (fire-and-forget)
        self._publish_chat_events(
            conversation_id=conversation_id,
            message=sanitized_message,
            llm_response=llm_response,
            tenant_id=tenant_id
        )
        
        return llm_response

    def _publish_chat_events(
        self,
        conversation_id: str,
        message: str,
        llm_response: Dict[str, Any],
        tenant_id: str,
        correlation_id: Optional[str] = None,
    ):
        """Publish Kafka events after a successful chat response (fire-and-forget)."""
        if not _KAFKA_EVENTS_AVAILABLE or not kafka_producer:
            return

        message_id = llm_response.get("message_id", f"msg_{uuid.uuid4().hex[:10]}")
        usage      = llm_response.get("usage", {})
        model      = llm_response.get("model", "unknown")

        # 1. chat.message.created
        evt_created = message_created_event(
            conversation_id=conversation_id,
            message_id=message_id,
            user_message=message,
            tenant_id=tenant_id,
            correlation_id=correlation_id,
        )
        kafka_producer.publish(
            topic=evt_created.event_type,
            event_dict=evt_created.to_dict(),
            key=conversation_id,
        )

        # 2. chat.response.completed
        evt_completed = response_completed_event(
            conversation_id=conversation_id,
            message_id=message_id,
            model=model,
            input_tokens=usage.get("input_tokens", 0),
            output_tokens=usage.get("output_tokens", 0),
            latency_ms=0.0,
            rag_used=llm_response.get("rag_used", False),
            tenant_id=tenant_id,
            correlation_id=correlation_id,
        )
        kafka_producer.publish(
            topic=evt_completed.event_type,
            event_dict=evt_completed.to_dict(),
            key=conversation_id,
        )

        # 3. analytics.budget.alert (if threshold reached)
        try:
            from shared.governance.models import SpendLimitPolicy
            policy = SpendLimitPolicy()
            alert_level = governance_engine.spend_tracker.check_budget_threshold(tenant_id, policy)
            if alert_level:
                usage_rec = governance_engine.get_tenant_usage(tenant_id)
                evt_alert = budget_alert_event(
                    tenant_id=tenant_id,
                    alert_level=alert_level,
                    used_tokens=usage_rec.get("total_tokens", 0),
                    max_tokens=policy.max_tokens_per_period,
                    used_cost_usd=usage_rec.get("total_cost_usd", 0.0),
                    max_cost_usd=policy.max_cost_per_period,
                    correlation_id=correlation_id,
                )
                kafka_producer.publish(
                    topic=evt_alert.event_type,
                    event_dict=evt_alert.to_dict(),
                    key=tenant_id,
                )
                logger.warning(f"[Governance Kafka] Published budget alert ({alert_level}) for tenant '{tenant_id}'")
        except Exception as e:
            logger.warning(f"[Governance Kafka] Error emitting budget alert: {e}")

    async def process_message_stream(
        self,
        request: Dict[str, Any],
        tenant_id: str = "default",
        user_context: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[StreamEvent, None]:
        """Process chat message with streaming response and AI Governance evaluation"""
        conversation_id = request["conversation_id"]
        message = request["message"]
        knowledge_base_id = request.get("knowledge_base_id")
        stream_id = f"stream_{uuid.uuid4().hex[:10]}"
        
        full_response = ""
        tool_results_history = []
        message_id = f"msg_{uuid.uuid4().hex[:10]}"

        # ── Phase 17: Governance Evaluation for Streaming ──
        gov_result = governance_engine.evaluate_request(
            tenant_id=tenant_id,
            prompt=message,
            model=request.get("model"),
            requested_tools=request.get("tools"),
            knowledge_base_id=knowledge_base_id,
        )

        if not gov_result.allowed:
            logger.warning(f"[Governance Stream] Request denied for tenant '{tenant_id}': {gov_result.denial_reason}")
            yield ErrorEvent(
                code=gov_result.error_code,
                message=f"Governance Policy Denied: {gov_result.denial_reason}"
            )
            yield DoneEvent(status=StreamStatus.FAILED)
            return

        effective_message = gov_result.sanitized_prompt
        
        try:
            yield StatusEvent(
                status=StreamStatus.PROCESSING,
                message="Processing request..."
            )
            
            messages = self.context_builder.build_context(conversation_id, effective_message)
            
            if self._should_use_rag(effective_message) or knowledge_base_id:
                yield StatusEvent(
                    status=StreamStatus.RETRIEVING,
                    message="Traversing Knowledge Graph & Hybrid RRF..."
                )
                
                rag_context = await self.rag_context_builder.build_context(
                    effective_message,
                    tenant_id,
                    knowledge_base_id
                )

                # CRAG self-correction streaming notice
                crag_data = rag_context.get("crag") or {}
                if crag_data.get("reformulated_query"):
                    yield StatusEvent(
                        status=StreamStatus.PROCESSING,
                        message=f"CRAG Self-Correction: Query reformulated to '{crag_data['reformulated_query']}'"
                    )

                for source in rag_context.get("sources", []):
                    yield SourceEvent(**source)

                if rag_context.get("graph_rag") or rag_context.get("crag"):
                    yield MetadataEvent(metadata={
                        "graph_rag": rag_context.get("graph_rag"),
                        "crag": rag_context.get("crag")
                    })
                
                messages = self._combine_contexts(messages, rag_context.get("messages", []))
            
            yield StatusEvent(
                status=StreamStatus.GENERATING,
                message="Generating response..."
            )
            
            async for token in self.llm_stream_client.stream_response(messages):
                if token.startswith("__TOOL_CALL__:"):
                    # Handle tool call markers if present
                    tool_data = json.loads(token.replace("__TOOL_CALL__:", ""))
                    tool_name = tool_data.get("name", "tool")
                    yield ToolStartEvent(tool_name=tool_name, arguments=tool_data.get("arguments", {}))
                    continue
                
                full_response += token
                yield TokenEvent(content=token)
            
            inp_toks = len(str(messages)) // 4
            out_toks = len(full_response) // 4
            cost = governance_engine.record_usage(tenant_id, self.llm_service.model, inp_toks, out_toks)

            if not gov_result.zero_retention_mode:
                self._save_conversation(
                    conversation_id,
                    effective_message,
                    full_response,
                    self.llm_service.model,
                    tool_results_history
                )
            else:
                logger.info(f"[Governance Stream] Zero data retention enabled for tenant '{tenant_id}'. Skipping conversation save.")
            
            yield DoneEvent(
                message_id=message_id,
                conversation_id=conversation_id,
                status=StreamStatus.COMPLETED,
                usage={
                    "input_tokens": inp_toks,
                    "output_tokens": out_toks,
                    "cost_usd": cost,
                },
                model=self.llm_service.model
            )
            
        except asyncio.CancelledError:
            logger.info(f"Stream {stream_id} cancelled by client")
            yield StatusEvent(
                status=StreamStatus.CANCELLED,
                message="Stream cancelled"
            )
            raise
            
        except Exception as e:
            logger.error(f"Error in stream {stream_id}: {e}")
            yield ErrorEvent(
                code="STREAM_ERROR",
                message=str(e)
            )
            yield DoneEvent(
                status=StreamStatus.FAILED
            )
    
    def _should_use_rag(self, message: str) -> bool:
        """Determine if RAG should be used based on message content"""
        rag_indicators = [
            "document",
            "according to",
            "in the pdf",
            "in the doc",
            "what does the document say",
            "knowledge base"
        ]
        
        message_lower = message.lower()
        return any(indicator in message_lower for indicator in rag_indicators)
    
    def _combine_contexts(self, conversation_context: List[Dict[str, str]], rag_context: List[Dict[str, str]]) -> List[Dict[str, str]]:
        """Combine conversation and RAG contexts"""
        combined = []
        
        if conversation_context and conversation_context[0]["role"] == "system":
            system_msg = conversation_context[0].copy()
            system_msg["content"] += "\n\nYou have access to a knowledge base. Use the provided context to answer questions accurately."
            combined.append(system_msg)
        
        for msg in conversation_context[1:]:
            if msg["role"] != "system":
                combined.append(msg)
        
        combined.extend(rag_context)
        return combined

    def _save_conversation(
        self,
        conversation_id: str,
        user_message: str,
        assistant_response: str,
        model: str,
        tools_used: List[Dict[str, Any]]
    ):
        """Save conversation to database"""
        try:
            self.conversation_service.add_message(
                conversation_id=conversation_id,
                role="user",
                content=user_message,
                model=model
            )
            
            if assistant_response:
                self.conversation_service.add_message(
                    conversation_id=conversation_id,
                    role="assistant",
                    content=assistant_response,
                    model=model
                )
            
        except Exception as e:
            logger.error(f"Error saving conversation: {e}")
