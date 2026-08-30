from typing import List, Dict, Any, Optional
import logging
from .models import LLMRequest, TenantPolicy
from .adapters.base import BaseLLMAdapter
from .circuit_breaker import CircuitBreaker

logger = logging.getLogger(__name__)

class LLMRouter:
    """
    LLM Router Engine.
    Resolves request targets into an ordered list of candidate backend adapters based on:
    1. Tenant tier & primary backend policies
    2. Logical model to physical backend mappings
    3. Health status from CircuitBreaker
    """

    def __init__(self):
        # Maps logical model name (e.g. "llama-3-8b") to list of physical backend names
        self.model_routes: Dict[str, List[str]] = {}
        # Default priority order for backends
        self.default_priority: List[str] = []

    def register_model_route(self, model_alias: str, backend_names: List[str]):
        """Map a model alias or name to candidate physical backends."""
        self.model_routes[model_alias.lower()] = backend_names

    def set_default_priority(self, backend_names: List[str]):
        """Set fallback priority order."""
        self.default_priority = backend_names

    def resolve_candidate_backends(
        self,
        request: LLMRequest,
        adapters: Dict[str, BaseLLMAdapter],
        circuit_breaker: CircuitBreaker,
        policy: Optional[TenantPolicy] = None
    ) -> List[BaseLLMAdapter]:
        """
        Produce an ordered candidate list of adapters for the request.
        Healthy backends are prioritized first; unhealthy ones can be placed at end or skipped.
        """
        candidate_names: List[str] = []

        # 1. Check if Tenant policy specifies a primary backend
        if policy and policy.primary_backend and policy.primary_backend in adapters:
            candidate_names.append(policy.primary_backend)

        # 2. Check if request model matches a registered route mapping
        requested_model = request.model.lower()
        if requested_model in self.model_routes:
            for b_name in self.model_routes[requested_model]:
                if b_name not in candidate_names:
                    candidate_names.append(b_name)

        # 3. Check if requested model matches a direct backend name
        if request.model in adapters and request.model not in candidate_names:
            candidate_names.append(request.model)

        # 4. Append default priority list
        for b_name in self.default_priority:
            if b_name not in candidate_names:
                candidate_names.append(b_name)

        # 5. Append any other registered adapters as absolute last resorts
        for b_name in adapters:
            if b_name not in candidate_names:
                candidate_names.append(b_name)

        # Build candidate adapters list with healthy ones first
        healthy_candidates: List[BaseLLMAdapter] = []
        unhealthy_candidates: List[BaseLLMAdapter] = []

        for b_name in candidate_names:
            if b_name in adapters:
                adapter = adapters[b_name]
                if circuit_breaker.is_available(b_name):
                    healthy_candidates.append(adapter)
                else:
                    unhealthy_candidates.append(adapter)

        # Return healthy ones first, then unhealthy as desperate attempt
        final_list = healthy_candidates + unhealthy_candidates

        # Ensure MockAdapter is appended if present so requests never crash hard
        mock_adapter = next((a for a in adapters.values() if a.backend_type == "mock"), None)
        if mock_adapter and mock_adapter not in final_list:
            final_list.append(mock_adapter)

        return final_list
