import logging
from typing import Dict, List, Optional, Any
from .models import (
    TenantGovernancePolicy,
    TenantPlanTier,
    GovernanceEvaluationResult,
    PIIAction,
    ModelPolicy,
    ToolPolicy,
    KBAccessPolicy,
    SpendLimitPolicy,
    DataRetentionPolicy,
)
from .pii_sanitizer import PIISanitizer
from .spend_tracker import SpendTracker

logger = logging.getLogger(__name__)


class GovernanceEngine:
    """
    Central AI Governance & Policy Enforcement Engine.
    Ensures model access, tool permissions, spend limits, PII protection, KB isolation,
    and data retention rules are enforced consistently across all platform services.
    """

    def __init__(self):
        self._policies: Dict[str, TenantGovernancePolicy] = {}
        self.pii_sanitizer = PIISanitizer()
        self.spend_tracker = SpendTracker()
        self._register_default_preset_policies()

    def _register_default_preset_policies(self):
        """Seed default tier governance policies."""
        # 1. Default / Starter Tier Policy
        self.register_policy(
            TenantGovernancePolicy(
                tenant_id="default",
                tier=TenantPlanTier.STARTER,
                model_policy=ModelPolicy(
                    allowed_models=["gpt-3.5-turbo", "llama-3-8b", "mock-model"],
                    default_model="gpt-3.5-turbo",
                    max_tokens_per_request=2048,
                ),
                tool_policy=ToolPolicy(
                    allowed_tools=["calculator", "weather"],
                    blocked_tools=["delete_database", "execute_command", "db_query"],
                ),
                spend_policy=SpendLimitPolicy(
                    max_cost_per_period=20.0,
                    max_tokens_per_period=200_000,
                ),
                data_retention_policy=DataRetentionPolicy(
                    retention_days=30,
                    allow_message_logging=True,
                ),
            )
        )

        # 2. Pro Tier Preset
        self.register_policy(
            TenantGovernancePolicy(
                tenant_id="pro_tier",
                tier=TenantPlanTier.PRO,
                model_policy=ModelPolicy(
                    allowed_models=["gpt-3.5-turbo", "gpt-4o", "llama-3-8b", "llama-3-70b", "mock-model"],
                    default_model="gpt-4o",
                    max_tokens_per_request=4096,
                ),
                tool_policy=ToolPolicy(
                    allowed_tools=["calculator", "weather", "web_search", "document_reader"],
                    blocked_tools=["delete_database", "execute_command"],
                ),
                spend_policy=SpendLimitPolicy(
                    max_cost_per_period=250.0,
                    max_tokens_per_period=2_500_000,
                ),
                data_retention_policy=DataRetentionPolicy(
                    retention_days=90,
                    allow_message_logging=True,
                ),
            )
        )

        # 3. Enterprise Tier Preset
        self.register_policy(
            TenantGovernancePolicy(
                tenant_id="enterprise_tier",
                tier=TenantPlanTier.ENTERPRISE,
                model_policy=ModelPolicy(
                    allowed_models=["*"],
                    default_model="gpt-4o",
                    max_tokens_per_request=8192,
                ),
                tool_policy=ToolPolicy(
                    allowed_tools=["*"],
                    blocked_tools=[],
                ),
                kb_policy=KBAccessPolicy(
                    allow_unrestricted=True,
                ),
                spend_policy=SpendLimitPolicy(
                    max_cost_per_period=5000.0,
                    max_tokens_per_period=50_000_000,
                ),
                data_retention_policy=DataRetentionPolicy(
                    retention_days=365,
                    allow_message_logging=True,
                ),
            )
        )

    def register_policy(self, policy: TenantGovernancePolicy):
        """Register or update a tenant's governance policy."""
        self._policies[policy.tenant_id] = policy
        logger.info(f"[GovernanceEngine] Registered governance policy for tenant '{policy.tenant_id}' (Tier: {policy.tier.value})")

    def get_policy(self, tenant_id: str) -> TenantGovernancePolicy:
        """Fetch policy for tenant or fallback to default policy."""
        if tenant_id in self._policies:
            return self._policies[tenant_id]
        # Return a copy of default policy with updated tenant_id
        default_p = self._policies["default"].model_copy(deep=True)
        default_p.tenant_id = tenant_id
        return default_p

    def evaluate_request(
        self,
        tenant_id: str,
        prompt: str,
        model: Optional[str] = None,
        requested_tools: Optional[List[str]] = None,
        knowledge_base_id: Optional[str] = None,
        estimated_max_tokens: int = 500,
    ) -> GovernanceEvaluationResult:
        """
        Evaluates an AI request against tenant governance policies.
        Validates:
        1. Model Access (Tier/Whitelist)
        2. Spend & Token Quota
        3. Tool Execution Authorization
        4. Knowledge Base RAG Access
        5. PII Redaction/Blocking
        6. Data Retention Mode
        """
        policy = self.get_policy(tenant_id)
        target_model = model or policy.model_policy.default_model

        # ── 1. Model Access Control ──
        if not self._is_model_allowed(target_model, policy.model_policy):
            reason = f"Model '{target_model}' is not allowed for tenant '{tenant_id}' (Plan: {policy.tier.value})."
            logger.warning(f"[GovernanceEngine] {reason}")
            return GovernanceEvaluationResult(
                allowed=False,
                tenant_id=tenant_id,
                denial_reason=reason,
                error_code="MODEL_NOT_ALLOWED",
                sanitized_prompt=prompt,
                applied_policies={"model": target_model, "tier": policy.tier.value},
            )

        # ── 2. Spend & Token Quota Check ──
        estimated_cost = self.spend_tracker.estimate_cost(target_model, estimated_max_tokens, estimated_max_tokens)
        quota_ok, quota_reason = self.spend_tracker.check_quota(
            tenant_id, policy.spend_policy, estimated_tokens=estimated_max_tokens
        )
        if not quota_ok:
            return GovernanceEvaluationResult(
                allowed=False,
                tenant_id=tenant_id,
                denial_reason=quota_reason,
                error_code="SPEND_LIMIT_EXCEEDED",
                sanitized_prompt=prompt,
                applied_policies={"spend": policy.spend_policy.dict()},
            )

        # ── 3. Tool Authorization Check ──
        if requested_tools:
            unauthorized_tools = [
                t for t in requested_tools
                if not self._is_tool_allowed(t, policy.tool_policy)
            ]
            if unauthorized_tools:
                reason = f"Tools {unauthorized_tools} are not permitted for tenant '{tenant_id}'."
                logger.warning(f"[GovernanceEngine] {reason}")
                return GovernanceEvaluationResult(
                    allowed=False,
                    tenant_id=tenant_id,
                    denial_reason=reason,
                    error_code="TOOL_NOT_ALLOWED",
                    sanitized_prompt=prompt,
                    applied_policies={"unauthorized_tools": unauthorized_tools},
                )

        # ── 4. Knowledge Base Authorization Check ──
        if knowledge_base_id:
            if not self._is_kb_allowed(knowledge_base_id, tenant_id, policy.kb_policy):
                reason = f"Knowledge base '{knowledge_base_id}' access denied for tenant '{tenant_id}'."
                logger.warning(f"[GovernanceEngine] {reason}")
                return GovernanceEvaluationResult(
                    allowed=False,
                    tenant_id=tenant_id,
                    denial_reason=reason,
                    error_code="KB_ACCESS_DENIED",
                    sanitized_prompt=prompt,
                    applied_policies={"knowledge_base_id": knowledge_base_id},
                )

        # ── 5. PII Inspection & Sanitization ──
        sanitized_prompt, pii_found, pii_matches = self.pii_sanitizer.inspect_and_sanitize(
            prompt, policy.pii_policy
        )
        if pii_found and policy.pii_policy.action == PIIAction.BLOCK:
            reason = f"Request contains sensitive PII ({', '.join(pii_matches)}) which is blocked by tenant governance policy."
            logger.warning(f"[GovernanceEngine] {reason}")
            return GovernanceEvaluationResult(
                allowed=False,
                tenant_id=tenant_id,
                denial_reason=reason,
                error_code="PII_BLOCKED",
                sanitized_prompt=prompt,
                pii_detected=True,
                pii_matches=pii_matches,
                applied_policies={"pii_action": PIIAction.BLOCK.value},
            )

        # ── 6. Data Retention Evaluation ──
        zero_retention = (
            policy.data_retention_policy.retention_days == 0
            or not policy.data_retention_policy.allow_message_logging
        )

        return GovernanceEvaluationResult(
            allowed=True,
            tenant_id=tenant_id,
            sanitized_prompt=sanitized_prompt,
            pii_detected=pii_found,
            pii_matches=pii_matches,
            zero_retention_mode=zero_retention,
            applied_policies={
                "model": target_model,
                "tier": policy.tier.value,
                "retention_days": policy.data_retention_policy.retention_days,
            },
        )

    def record_usage(self, tenant_id: str, model: str, input_tokens: int, output_tokens: int) -> float:
        """Record usage against tenant spend tracker."""
        return self.spend_tracker.record_usage(tenant_id, model, input_tokens, output_tokens)

    def _is_model_allowed(self, model: str, policy: ModelPolicy) -> bool:
        if "*" in policy.allowed_models:
            return True
        return model.lower() in [m.lower() for m in policy.allowed_models]

    def _is_tool_allowed(self, tool_name: str, policy: ToolPolicy) -> bool:
        if tool_name in policy.blocked_tools:
            return False
        if "*" in policy.allowed_tools:
            return True
        return tool_name.lower() in [t.lower() for t in policy.allowed_tools]

    def _is_kb_allowed(self, kb_id: str, tenant_id: str, policy: KBAccessPolicy) -> bool:
        if policy.allow_unrestricted:
            return True
        if kb_id in policy.allowed_knowledge_bases:
            return True
        # Tenant namespace auto-isolation check: e.g. "tenant_123_kb" or "kb_tenant_123"
        if tenant_id.lower() in kb_id.lower():
            return True
        if policy.allow_all_public and "public" in kb_id.lower():
            return True
        return False


# Global singleton governance engine
governance_engine = GovernanceEngine()
