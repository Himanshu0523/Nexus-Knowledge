import time
import logging
from typing import Dict, Any, Tuple, Optional
from .models import SpendLimitPolicy

logger = logging.getLogger(__name__)

# Standard LLM Pricing per 1,000,000 tokens (USD)
# (input_price_per_1M, output_price_per_1M)
MODEL_PRICING_PER_1M: Dict[str, Tuple[float, float]] = {
    "gpt-4o": (2.50, 10.00),
    "gpt-4-turbo": (10.00, 30.00),
    "gpt-4": (30.00, 60.00),
    "gpt-3.5-turbo": (0.50, 1.50),
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-3-haiku": (0.25, 1.25),
    "llama-3-8b": (0.15, 0.15),
    "llama-3-70b": (0.90, 0.90),
    "mock-model": (0.00, 0.00),
}
DEFAULT_PRICING_PER_1M = (1.00, 2.00)


class TenantUsageRecord:
    def __init__(self, tenant_id: str):
        self.tenant_id = tenant_id
        self.total_input_tokens: int = 0
        self.total_output_tokens: int = 0
        self.total_cost_usd: float = 0.0
        self.request_count: int = 0
        self.period_start_time: float = time.time()

    def reset_if_period_expired(self, period_seconds: int):
        now = time.time()
        if now - self.period_start_time >= period_seconds:
            logger.info(f"[SpendTracker] Period expired for tenant {self.tenant_id}. Resetting usage metrics.")
            self.total_input_tokens = 0
            self.total_output_tokens = 0
            self.total_cost_usd = 0.0
            self.request_count = 0
            self.period_start_time = now


class SpendTracker:
    """
    Real-time spend and token quota manager for tenant AI Governance.
    Tracks token consumption, dollar cost, and request frequencies per tenant.
    """

    def __init__(self):
        self._tenant_records: Dict[str, TenantUsageRecord] = {}

    def get_or_create_record(self, tenant_id: str) -> TenantUsageRecord:
        if tenant_id not in self._tenant_records:
            self._tenant_records[tenant_id] = TenantUsageRecord(tenant_id)
        return self._tenant_records[tenant_id]

    def estimate_cost(self, model: str, input_tokens: int, output_tokens: int) -> float:
        """Calculate estimated USD cost based on model pricing matrix."""
        input_price, output_price = MODEL_PRICING_PER_1M.get(
            model.lower(), DEFAULT_PRICING_PER_1M
        )
        input_cost = (input_tokens / 1_000_000.0) * input_price
        output_cost = (output_tokens / 1_000_000.0) * output_price
        return round(input_cost + output_cost, 6)

    def check_quota(
        self, tenant_id: str, policy: SpendLimitPolicy, estimated_tokens: int = 0
    ) -> Tuple[bool, str]:
        """
        Check if the request exceeds tenant spend limits or token budgets.
        Returns (is_allowed, error_reason).
        """
        record = self.get_or_create_record(tenant_id)
        record.reset_if_period_expired(policy.period_seconds)

        current_tokens = record.total_input_tokens + record.total_output_tokens
        if (current_tokens + estimated_tokens) > policy.max_tokens_per_period:
            msg = (
                f"Token quota exceeded for tenant '{tenant_id}'. "
                f"Used: {current_tokens}, Request est: {estimated_tokens}, Limit: {policy.max_tokens_per_period}"
            )
            logger.warning(f"[SpendTracker] {msg}")
            return False, msg

        if record.total_cost_usd >= policy.max_cost_per_period:
            msg = (
                f"Spend limit ($ USD) exceeded for tenant '{tenant_id}'. "
                f"Spent: ${record.total_cost_usd:.4f}, Limit: ${policy.max_cost_per_period:.2f}"
            )
            logger.warning(f"[SpendTracker] {msg}")
            return False, msg

        return True, ""

    def record_usage(
        self, tenant_id: str, model: str, input_tokens: int, output_tokens: int
    ) -> float:
        """Record token usage and update cumulative spend. Returns cost of this request."""
        record = self.get_or_create_record(tenant_id)
        cost = self.estimate_cost(model, input_tokens, output_tokens)

        record.total_input_tokens += input_tokens
        record.total_output_tokens += output_tokens
        record.total_cost_usd += cost
        record.request_count += 1

        logger.info(
            f"[SpendTracker] Tenant '{tenant_id}' used {input_tokens}in/{output_tokens}out tokens on {model} "
            f"(Cost: ${cost:.6f}, Total Spent: ${record.total_cost_usd:.4f})"
        )
        return cost

    def check_budget_threshold(
        self, tenant_id: str, policy: SpendLimitPolicy
    ) -> Optional[str]:
        """
        Check if tenant has crossed the 80% proactive warning threshold or 100% hard limit.
        Returns 'warning' (>= 80%), 'exceeded' (>= 100%), or None.
        """
        record = self.get_or_create_record(tenant_id)
        current_tokens = record.total_input_tokens + record.total_output_tokens

        token_ratio = current_tokens / max(policy.max_tokens_per_period, 1)
        cost_ratio = record.total_cost_usd / max(policy.max_cost_per_period, 0.001)

        highest_ratio = max(token_ratio, cost_ratio)

        if highest_ratio >= 1.0:
            return "exceeded"
        elif highest_ratio >= 0.80:
            return "warning"
        return None

    def get_usage(self, tenant_id: str) -> Dict[str, Any]:
        """Retrieve current usage metrics for a tenant."""
        record = self.get_or_create_record(tenant_id)
        return {
            "tenant_id": tenant_id,
            "total_input_tokens": record.total_input_tokens,
            "total_output_tokens": record.total_output_tokens,
            "total_tokens": record.total_input_tokens + record.total_output_tokens,
            "total_cost_usd": round(record.total_cost_usd, 4),
            "request_count": record.request_count,
            "period_start_time": record.period_start_time,
        }
