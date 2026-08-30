from typing import Dict, List, Any, Optional
import copy
import logging
from .models import LLMRequest, TenantPolicy

logger = logging.getLogger(__name__)

class PolicyEngine:
    """
    Policy Engine for Tenant Control & Token Management.
    Enforces per-tenant context window limits, token caps, allowed models, and default parameters.
    """

    def __init__(self):
        self.tenant_policies: Dict[str, TenantPolicy] = {}
        self.default_policy = TenantPolicy(tenant_id="default")

    def register_tenant_policy(self, policy: TenantPolicy):
        """Register or update a tenant policy."""
        self.tenant_policies[policy.tenant_id] = policy

    def get_tenant_policy(self, tenant_id: str) -> TenantPolicy:
        """Retrieve policy for tenant or default policy."""
        return self.tenant_policies.get(tenant_id, self.default_policy)

    def apply_policy(self, request: LLMRequest) -> LLMRequest:
        """
        Applies tenant policy constraints to an LLMRequest:
        1. Fill in default temperature & top_p if unset
        2. Cap request max_tokens to policy max_tokens_per_request
        3. Enforce context window limit by truncating older messages
        """
        policy = self.get_tenant_policy(request.tenant_id)
        
        # Clone request to avoid mutating original object
        req = copy.deepcopy(request)

        # 1. Hyperparameters
        if req.temperature is None:
            req.temperature = policy.default_temperature
        if req.top_p is None:
            req.top_p = policy.default_top_p

        # 2. Token limits
        if req.max_tokens is None or req.max_tokens > policy.max_tokens_per_request:
            req.max_tokens = policy.max_tokens_per_request

        # 3. Context window enforcement (truncation)
        req.messages = self._truncate_messages(req.messages, policy.max_context_length)

        return req

    def _truncate_messages(self, messages: List[Dict[str, str]], max_tokens: int) -> List[Dict[str, str]]:
        """
        Truncate message history if total estimated token length exceeds max_tokens.
        Preserves system message(s) and the latest user message.
        """
        if not messages:
            return messages

        def estimate_tokens(msgs: List[Dict[str, str]]) -> int:
            return sum(len(m.get("content", "")) for m in msgs) // 4

        total_tokens = estimate_tokens(messages)
        if total_tokens <= max_tokens:
            return messages

        logger.info(f"Input prompt estimated tokens ({total_tokens}) exceeds context limit ({max_tokens}). Truncating older messages.")

        # Separate system messages, history, and last user message
        system_msgs = [m for m in messages if m.get("role") == "system"]
        other_msgs = [m for m in messages if m.get("role") != "system"]

        if not other_msgs:
            return system_msgs

        latest_msg = other_msgs[-1]
        history_msgs = other_msgs[:-1]

        result = copy.deepcopy(system_msgs)
        # Add from end of history towards start until limit is reached
        retained_history = []
        for msg in reversed(history_msgs):
            candidate = system_msgs + [msg] + retained_history + [latest_msg]
            if estimate_tokens(candidate) <= max_tokens:
                retained_history.insert(0, msg)
            else:
                break

        return system_msgs + retained_history + [latest_msg]
