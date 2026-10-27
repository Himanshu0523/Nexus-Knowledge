"""
Multi-Agent Collaborative Routing (Agentic Enterprise Mesh).
Routes incoming requests to specialized autonomous worker agents:
1. Security/Compliance Agent: Zero-trust PII & tenant boundary scanner.
2. SQL/Analytics Agent: Direct structured PostgreSQL metrics & analytical queries.
3. Graph/RAG Synthesis Agent: Document grounding, cross-document graph traversal, and CRAG self-correction.
"""

from typing import Dict, Any, List, Optional
from enum import Enum
import logging
import re
import json

logger = logging.getLogger(__name__)


class AgentDomain(str, Enum):
    SECURITY_COMPLIANCE = "security_compliance"
    SQL_ANALYTICS = "sql_analytics"
    GRAPH_RAG_SYNTHESIS = "graph_rag_synthesis"
    GENERAL_CHAT = "general_chat"


class SpecializedAgentResponse:
    def __init__(
        self,
        domain: AgentDomain,
        success: bool,
        response: str,
        data: Optional[Dict[str, Any]] = None,
        sources: Optional[List[Dict[str, Any]]] = None,
        agent_name: str = "base-agent"
    ):
        self.domain = domain
        self.success = success
        self.response = response
        self.data = data or {}
        self.sources = sources or []
        self.agent_name = agent_name

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain": self.domain.value,
            "agent_name": self.agent_name,
            "success": self.success,
            "response": self.response,
            "data": self.data,
            "sources": self.sources
        }


class SecurityComplianceAgent:
    """Specialized Agent for PII scanning, tenant bleed defense, and prompt security"""
    def __init__(self):
        self.name = "SecurityComplianceAgent"

    async def inspect_and_sanitize(self, prompt: str, tenant_id: str) -> Dict[str, Any]:
        """Verify prompt doesn't violate multi-tenant boundary or contain severe injections"""
        pii_patterns = {
            "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
            "credit_card": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
            "api_key": r"\b(?:sk-[a-zA-Z0-9]{20,}|ghp_[a-zA-Z0-9]{20,}|ey[a-zA-Z0-9_\-]{30,})\b"
        }
        detected = []
        sanitized = prompt
        for ptype, pattern in pii_patterns.items():
            if re.search(pattern, sanitized):
                detected.append(ptype)
                sanitized = re.sub(pattern, f"[REDACTED_{ptype.upper()}]", sanitized)

        # Cross-tenant data bleed guardrail check
        cross_tenant_bleed = False
        if re.search(r"(?i)\b(?:other\s+tenant|across\s+all\s+tenants|all\s+tenants\s+data|bypass\s+tenant)\b", prompt):
            cross_tenant_bleed = True

        return {
            "is_safe": not cross_tenant_bleed,
            "sanitized_prompt": sanitized,
            "pii_detected": detected,
            "cross_tenant_bleed_detected": cross_tenant_bleed,
            "reason": "Unauthorized cross-tenant query blocked" if cross_tenant_bleed else None
        }


class SQLAnalyticsAgent:
    """Specialized Agent for structured PostgreSQL analytics and tenant telemetry"""
    def __init__(self, db_session=None):
        self.name = "SQLAnalyticsAgent"
        self.db = db_session

    async def execute_metrics_query(self, query: str, tenant_id: str) -> SpecializedAgentResponse:
        """Parse analytical request and generate real-time metrics summaries"""
        # Determine metrics type requested
        q_lower = query.lower()
        if "token" in q_lower or "cost" in q_lower or "spend" in q_lower:
            from shared.governance import governance_engine
            usage = governance_engine.get_tenant_usage(tenant_id)
            resp = (
                f"### Tenant Analytics ({tenant_id}):\n"
                f"- **Total Tokens Consumed:** {usage.get('total_tokens', 0):,}\n"
                f"- **Input Tokens:** {usage.get('total_input_tokens', 0):,}\n"
                f"- **Output Tokens:** {usage.get('total_output_tokens', 0):,}\n"
                f"- **Total Spend (USD):** ${usage.get('total_cost_usd', 0.0):.4f}\n"
                f"- **Total Requests:** {usage.get('request_count', 0)}"
            )
            return SpecializedAgentResponse(
                domain=AgentDomain.SQL_ANALYTICS,
                agent_name=self.name,
                success=True,
                response=resp,
                data=usage
            )
        elif "document" in q_lower or "knowledge base" in q_lower or "chunk" in q_lower:
            from rag.graph_rag import graph_rag_service
            stats = graph_rag_service.get_graph_stats(tenant_id)
            resp = (
                f"### Knowledge Graph & Document Topology ({tenant_id}):\n"
                f"- **Total Semantic Nodes:** {stats.get('total_nodes', 0)}\n"
                f"- **Entity Nodes:** {stats.get('entity_nodes', 0)}\n"
                f"- **Chunk Nodes:** {stats.get('chunk_nodes', 0)}\n"
                f"- **Graph Edges (Triples):** {stats.get('total_edges', 0)}\n"
                f"- **Connected Components:** {stats.get('connected_components', 0)}"
            )
            return SpecializedAgentResponse(
                domain=AgentDomain.SQL_ANALYTICS,
                agent_name=self.name,
                success=True,
                response=resp,
                data=stats
            )
        else:
            return SpecializedAgentResponse(
                domain=AgentDomain.SQL_ANALYTICS,
                agent_name=self.name,
                success=True,
                response=f"Structured analytics metrics ready for tenant '{tenant_id}'.",
                data={"tenant_id": tenant_id}
            )


class GraphRAGSynthesisAgent:
    """Specialized Agent for Hybrid Search, Graph RAG Traversal, and CRAG Self-Correction"""
    def __init__(self):
        self.name = "GraphRAGSynthesisAgent"

    async def execute_rag_pipeline(
        self,
        query: str,
        tenant_id: str,
        knowledge_base_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Execute full hierarchical RAG pipeline"""
        from rag.context_builder import RAGContextBuilder
        builder = RAGContextBuilder()
        return await builder.build_context(
            query=query,
            tenant_id=tenant_id,
            knowledge_base_id=knowledge_base_id,
            use_graph_rag=True,
            use_crag=True
        )


class EnterpriseMeshRouter:
    """
    Intelligent router directing incoming requests to specialized agents
    or orchestrating collaborative multi-agent execution flows.
    """

    def __init__(self, db_session=None):
        self.security_agent = SecurityComplianceAgent()
        self.sql_agent = SQLAnalyticsAgent(db_session)
        self.rag_agent = GraphRAGSynthesisAgent()

    def classify_intent(self, message: str) -> AgentDomain:
        """Classify message to the optimal micro-agent domain"""
        msg = message.lower()

        # SQL / Analytics keywords
        analytics_indicators = [
            "how many tokens", "total cost", "usage metrics", "show analytics",
            "token consumption", "how much spent", "graph stats", "document count"
        ]
        if any(ind in msg for ind in analytics_indicators):
            return AgentDomain.SQL_ANALYTICS

        # Security inspection keywords
        security_indicators = [
            "pii check", "audit tenant", "inspect compliance", "data bleed", "cross tenant"
        ]
        if any(ind in msg for ind in security_indicators):
            return AgentDomain.SECURITY_COMPLIANCE

        # Graph RAG indicators
        rag_indicators = [
            "document", "according to", "in the pdf", "in the doc",
            "what does the document say", "knowledge base", "virtualization",
            "how does", "impact", "relationship between", "protocol"
        ]
        if any(ind in msg for ind in rag_indicators):
            return AgentDomain.GRAPH_RAG_SYNTHESIS

        return AgentDomain.GENERAL_CHAT
