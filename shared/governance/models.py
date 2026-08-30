from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class TenantPlanTier(str, Enum):
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"
    CUSTOM = "custom"


class PIIAction(str, Enum):
    SCRUB = "scrub"      # Replace PII with placeholder tag, e.g. [REDACTED_EMAIL]
    BLOCK = "block"      # Reject request if PII detected
    LOG_ONLY = "log_only"# Log PII match but pass text through


class PIIType(str, Enum):
    EMAIL = "email"
    PHONE = "phone"
    SSN = "ssn"
    CREDIT_CARD = "credit_card"
    API_KEY = "api_key"
    IP_ADDRESS = "ip_address"
    CUSTOM = "custom"


class PIIPolicy(BaseModel):
    enabled: bool = True
    action: PIIAction = PIIAction.SCRUB
    pii_types: List[PIIType] = Field(
        default_factory=lambda: [
            PIIType.EMAIL, PIIType.PHONE, PIIType.SSN, 
            PIIType.CREDIT_CARD, PIIType.API_KEY, PIIType.IP_ADDRESS
        ]
    )
    custom_regexes: List[str] = Field(default_factory=list)


class ModelPolicy(BaseModel):
    allowed_models: List[str] = Field(
        default_factory=lambda: ["gpt-3.5-turbo", "llama-3-8b", "mock-model"]
    )  # Supports exact names or "*"
    default_model: str = "gpt-3.5-turbo"
    max_tokens_per_request: int = 4096


class ToolPolicy(BaseModel):
    allowed_tools: List[str] = Field(
        default_factory=lambda: ["calculator", "weather", "web_search", "document_reader"]
    )  # Supports exact names or "*"
    blocked_tools: List[str] = Field(default_factory=list)


class KBAccessPolicy(BaseModel):
    allowed_knowledge_bases: List[str] = Field(default_factory=list)  # KB / collection IDs
    allow_all_public: bool = True
    allow_unrestricted: bool = False


class SpendLimitPolicy(BaseModel):
    max_cost_per_period: float = 100.0  # Dollars USD per period
    max_tokens_per_period: int = 1_000_000
    period_seconds: int = 2_592_000  # Default: 30 days in seconds


class DataRetentionPolicy(BaseModel):
    retention_days: int = 30  # 0 = zero-data-retention (do not persist message text)
    allow_message_logging: bool = True
    allow_model_training_use: bool = False


class TenantGovernancePolicy(BaseModel):
    tenant_id: str
    tier: TenantPlanTier = TenantPlanTier.STARTER
    pii_policy: PIIPolicy = Field(default_factory=PIIPolicy)
    model_policy: ModelPolicy = Field(default_factory=ModelPolicy)
    tool_policy: ToolPolicy = Field(default_factory=ToolPolicy)
    kb_policy: KBAccessPolicy = Field(default_factory=KBAccessPolicy)
    spend_policy: SpendLimitPolicy = Field(default_factory=SpendLimitPolicy)
    data_retention_policy: DataRetentionPolicy = Field(default_factory=DataRetentionPolicy)


class GovernanceEvaluationResult(BaseModel):
    allowed: bool
    tenant_id: str
    denial_reason: Optional[str] = None
    error_code: Optional[str] = None  # e.g. MODEL_NOT_ALLOWED, SPEND_LIMIT_EXCEEDED, PII_BLOCKED, TOOL_NOT_ALLOWED, KB_ACCESS_DENIED
    sanitized_prompt: str
    applied_policies: Dict[str, Any] = Field(default_factory=dict)
    pii_detected: bool = False
    pii_matches: List[str] = Field(default_factory=list)
    zero_retention_mode: bool = False
