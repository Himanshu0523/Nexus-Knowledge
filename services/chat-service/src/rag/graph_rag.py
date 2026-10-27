"""
Hierarchical Graph RAG Engine for Nexus Knowledge.
Extracts entities and semantic relationships, constructs tenant-isolated Knowledge Graphs using NetworkX,
and performs multi-hop semantic traversal for complex cross-document queries.
"""

import re
import logging
from typing import Dict, Any, List, Set, Tuple, Optional
import networkx as nx

logger = logging.getLogger(__name__)


class EntityNode:
    """Represents an extracted entity in the Knowledge Graph"""
    def __init__(self, name: str, entity_type: str = "concept", metadata: Optional[Dict[str, Any]] = None):
        self.name = name.strip()
        self.entity_type = entity_type
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "entity_type": self.entity_type,
            "metadata": self.metadata
        }


class GraphRAGService:
    """
    Multi-tenant Hierarchical Graph RAG service.
    Constructs, queries, and traverses entity-relation knowledge graphs across tenant documents.
    """

    def __init__(self):
        # Tenant-isolated directed graphs: tenant_id -> nx.DiGraph
        self._tenant_graphs: Dict[str, nx.DiGraph] = {}
        # Known relationship patterns for semantic triple extraction
        self._relation_patterns = [
            (r"(?i)\b([A-Za-z0-9_\-\s]+?)\s+(?:is|are|defined as|refers to)\s+([A-Za-z0-9_\-\s]+)", "DEFINED_AS"),
            (r"(?i)\b([A-Za-z0-9_\-\s]+?)\s+(?:depends on|relies upon|requires)\s+([A-Za-z0-9_\-\s]+)", "DEPENDS_ON"),
            (r"(?i)\b([A-Za-z0-9_\-\s]+?)\s+(?:impacts|affects|regulates|enforces)\s+([A-Za-z0-9_\-\s]+)", "REGULATES"),
            (r"(?i)\b([A-Za-z0-9_\-\s]+?)\s+(?:provides|implements|supports)\s+([A-Za-z0-9_\-\s]+)", "PROVIDES"),
            (r"(?i)\b([A-Za-z0-9_\-\s]+?)\s+(?:consists of|contains|includes)\s+([A-Za-z0-9_\-\s]+)", "CONTAINS"),
            (r"(?i)\b([A-Za-z0-9_\-\s]+?)\s+(?:connects to|communicates with|calls)\s+([A-Za-z0-9_\-\s]+)", "CONNECTS_TO"),
        ]

    def _get_graph(self, tenant_id: str) -> nx.DiGraph:
        """Retrieve or initialize tenant-isolated graph."""
        if tenant_id not in self._tenant_graphs:
            self._tenant_graphs[tenant_id] = nx.DiGraph()
        return self._tenant_graphs[tenant_id]

    def extract_entities(self, text: str) -> List[Tuple[str, str]]:
        """
        Extract named entities, concepts, technical terms, and system components.
        Returns list of (entity_name, entity_type).
        """
        entities: Set[Tuple[str, str]] = set()

        # 1. Capitalized Multi-word Phrases (e.g. "Cloud Computing", "API Gateway", "Virtual Machine")
        phrase_matches = re.findall(r"\b([A-Z][a-zA-Z0-9_\-]+(?:\s+[A-Z][a-zA-Z0-9_\-]+)+)\b", text)
        for phrase in phrase_matches:
            if len(phrase.strip()) > 2:
                entities.add((phrase.strip(), "concept"))

        # 2. Acronyms & Code Identifiers (e.g. "IaaS", "PaaS", "SaaS", "JWT", "RAG", "RBAC")
        acronyms = re.findall(r"\b([A-Z]{2,8})\b", text)
        for acr in acronyms:
            entities.add((acr.strip(), "protocol_or_acronym"))

        # 3. CamelCase or snake_case technical identifiers (e.g. "tenant_id", "rate_limit", "KafkaProducer")
        tech_terms = re.findall(r"\b([a-z0-9]+_[a-z0-9_]+|[A-Z][a-z0-9]+[A-Z][a-zA-Z0-9]+)\b", text)
        for term in tech_terms:
            if len(term) > 3:
                entities.add((term.strip(), "technical_term"))

        # 4. Domain noun phrases & keywords
        domain_keywords = [
            "virtualization", "hypervisor", "cloud computing", "rate limits",
            "security protocols", "api gateway", "multi-tenancy", "qdrant",
            "kafka", "postgres", "redis", "encryption", "crag", "rag"
        ]
        text_lower = text.lower()
        for kw in domain_keywords:
            if kw in text_lower:
                entities.add((kw.title(), "domain_concept"))

        return list(entities)

    def extract_relations(self, text: str) -> List[Tuple[str, str, str]]:
        """
        Extract semantic (Subject, Predicate, Object) triples from text chunks.
        """
        triples: List[Tuple[str, str, str]] = []
        sentences = re.split(r"[.\n;]", text)

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) < 10:
                continue

            for pattern, relation in self._relation_patterns:
                matches = re.findall(pattern, sentence)
                for subj, obj in matches:
                    subj_clean = subj.strip().title()
                    obj_clean = obj.strip().title()
                    if len(subj_clean) > 2 and len(obj_clean) > 2 and len(subj_clean) < 50 and len(obj_clean) < 50:
                        triples.append((subj_clean, relation, obj_clean))

        return triples

    def ingest_chunk_to_graph(
        self,
        tenant_id: str,
        document_id: str,
        chunk_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Parse and ingest a document chunk into the tenant's knowledge graph.
        """
        graph = self._get_graph(tenant_id)
        meta = metadata or {}

        # Add Chunk Node
        chunk_node_id = f"chunk:{chunk_id}"
        graph.add_node(
            chunk_node_id,
            node_type="chunk",
            document_id=document_id,
            chunk_id=chunk_id,
            source=meta.get("source", "unknown"),
            page=meta.get("page", 1),
            text_preview=text[:120]
        )

        # Extract and add entities
        extracted_entities = self.extract_entities(text)
        for entity_name, entity_type in extracted_entities:
            entity_id = f"entity:{entity_name.lower()}"
            if not graph.has_node(entity_id):
                graph.add_node(
                    entity_id,
                    node_type="entity",
                    name=entity_name,
                    entity_type=entity_type,
                    frequency=1,
                    documents={document_id}
                )
            else:
                graph.nodes[entity_id]["frequency"] = graph.nodes[entity_id].get("frequency", 1) + 1
                if "documents" in graph.nodes[entity_id] and isinstance(graph.nodes[entity_id]["documents"], set):
                    graph.nodes[entity_id]["documents"].add(document_id)

            # Edge: Chunk -> Entity
            graph.add_edge(chunk_node_id, entity_id, relation="MENTIONS", weight=1.0)

        # Extract and add semantic triples
        triples = self.extract_relations(text)
        for subj, relation, obj in triples:
            subj_id = f"entity:{subj.lower()}"
            obj_id = f"entity:{obj.lower()}"

            if not graph.has_node(subj_id):
                graph.add_node(subj_id, node_type="entity", name=subj, entity_type="concept", frequency=1)
            if not graph.has_node(obj_id):
                graph.add_node(obj_id, node_type="entity", name=obj, entity_type="concept", frequency=1)

            # Edge between entities: Subj -> Obj
            graph.add_edge(
                subj_id,
                obj_id,
                relation=relation,
                provenance=chunk_id,
                document_id=document_id
            )

        return {
            "entities_found": len(extracted_entities),
            "triples_found": len(triples),
            "total_graph_nodes": graph.number_of_nodes(),
            "total_graph_edges": graph.number_of_edges()
        }

    def query_graph_context(
        self,
        tenant_id: str,
        query: str,
        max_hops: int = 2,
        max_triples: int = 10
    ) -> Dict[str, Any]:
        """
        Traverse the tenant's knowledge graph given a user query.
        Returns extracted query entities, discovered relation triples, and synthesized graph context.
        """
        graph = self._get_graph(tenant_id)
        if graph.number_of_nodes() == 0:
            return {
                "entities": [],
                "triples": [],
                "subgraph_summary": "",
                "connected_documents": []
            }

        query_entities = self.extract_entities(query)
        matched_entity_ids = []

        # Find matching nodes in the knowledge graph
        for entity_name, _ in query_entities:
            entity_id = f"entity:{entity_name.lower()}"
            if graph.has_node(entity_id):
                matched_entity_ids.append(entity_id)

        # Fallback substring matching on graph nodes
        if not matched_entity_ids:
            query_lower = query.lower()
            for node, data in graph.nodes(data=True):
                if data.get("node_type") == "entity":
                    name = data.get("name", "").lower()
                    if name and (name in query_lower or query_lower in name):
                        matched_entity_ids.append(node)

        discovered_triples = []
        connected_docs = set()
        visited_nodes = set()

        for start_node in matched_entity_ids:
            visited_nodes.add(start_node)
            # Traverse outgoing and incoming edges up to max_hops
            try:
                subgraph = nx.ego_graph(graph, start_node, radius=max_hops)
                for u, v, edge_data in subgraph.edges(data=True):
                    u_data = graph.nodes.get(u, {})
                    v_data = graph.nodes.get(v, {})
                    relation = edge_data.get("relation", "RELATES_TO")

                    u_label = u_data.get("name", u.replace("entity:", "").replace("chunk:", "Chunk "))
                    v_label = v_data.get("name", v.replace("entity:", "").replace("chunk:", "Chunk "))

                    if relation != "MENTIONS":
                        discovered_triples.append({
                            "subject": u_label,
                            "predicate": relation,
                            "object": v_label,
                            "document_id": edge_data.get("document_id")
                        })
                    if "document_id" in edge_data and edge_data["document_id"]:
                        connected_docs.add(edge_data["document_id"])
            except Exception as e:
                logger.warning(f"[GraphRAG] Error traversing ego graph for {start_node}: {e}")

        # Deduplicate triples
        unique_triples = []
        seen = set()
        for t in discovered_triples[:max_triples]:
            key = (t["subject"], t["predicate"], t["object"])
            if key not in seen:
                seen.add(key)
                unique_triples.append(t)

        # Build formatted graph summary
        summary_lines = []
        if unique_triples:
            summary_lines.append("### Discovered Knowledge Graph Relationships:")
            for t in unique_triples:
                summary_lines.append(f"- ({t['subject']}) --[{t['predicate']}]--> ({t['object']})")

        return {
            "entities": [graph.nodes[nid].get("name", nid) for nid in matched_entity_ids if nid in graph.nodes],
            "triples": unique_triples,
            "subgraph_summary": "\n".join(summary_lines),
            "connected_documents": list(connected_docs)
        }

    def find_entity_paths(
        self,
        tenant_id: str,
        source_concept: str,
        target_concept: str
    ) -> List[List[str]]:
        """
        Find shortest semantic paths between two concepts across documents.
        Answers relational questions like 'How does A impact B?'.
        """
        graph = self._get_graph(tenant_id)
        src_id = f"entity:{source_concept.lower().strip()}"
        tgt_id = f"entity:{target_concept.lower().strip()}"

        if not graph.has_node(src_id) or not graph.has_node(tgt_id):
            return []

        try:
            # Convert to undirected view for path exploration
            undirected = graph.to_undirected()
            paths = list(nx.all_shortest_paths(undirected, source=src_id, target=tgt_id))
            formatted_paths = []
            for path in paths[:3]:
                path_labels = [graph.nodes[n].get("name", n) for n in path]
                formatted_paths.append(path_labels)
            return formatted_paths
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []

    def get_graph_stats(self, tenant_id: str) -> Dict[str, Any]:
        """Return knowledge graph metrics for a tenant."""
        graph = self._get_graph(tenant_id)
        entity_count = sum(1 for _, d in graph.nodes(data=True) if d.get("node_type") == "entity")
        chunk_count = sum(1 for _, d in graph.nodes(data=True) if d.get("node_type") == "chunk")
        
        return {
            "tenant_id": tenant_id,
            "total_nodes": graph.number_of_nodes(),
            "total_edges": graph.number_of_edges(),
            "entity_nodes": entity_count,
            "chunk_nodes": chunk_count,
            "connected_components": nx.number_weakly_connected_components(graph) if graph.number_of_nodes() > 0 else 0
        }


# Global singleton instance
graph_rag_service = GraphRAGService()
