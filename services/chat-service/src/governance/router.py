from fastapi import APIRouter, HTTPException, Depends, status
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from shared.governance import (
    governance_engine,
    TenantGovernancePolicy,
    GovernanceEvaluationResult,
)

router = APIRouter(prefix="/governance", tags=["AI Governance"])


class GovernanceEvalRequest(BaseModel):
    tenant_id: str
    prompt: str
    model: Optional[str] = None
    requested_tools: Optional[List[str]] = None
    knowledge_base_id: Optional[str] = None


@router.get("/policies/{tenant_id}", response_model=TenantGovernancePolicy)
def get_tenant_policy(tenant_id: str):
    """Retrieve active AI Governance policy for a tenant."""
    return governance_engine.get_policy(tenant_id)


@router.post("/policies", response_model=TenantGovernancePolicy, status_code=status.HTTP_201_CREATED)
def set_tenant_policy(policy: TenantGovernancePolicy):
    """Register or update an AI Governance policy for a tenant."""
    governance_engine.register_policy(policy)
    return policy


@router.get("/usage/{tenant_id}")
def get_tenant_usage(tenant_id: str) -> Dict[str, Any]:
    """Retrieve real-time token usage and cumulative spend ($ USD) for a tenant."""
    return governance_engine.spend_tracker.get_usage(tenant_id)


@router.post("/evaluate", response_model=GovernanceEvaluationResult)
def evaluate_governance_request(req: GovernanceEvalRequest):
    """
    Dry-run evaluation of an AI prompt / model / tool request against tenant governance rules.
    """
    res = governance_engine.evaluate_request(
        tenant_id=req.tenant_id,
        prompt=req.prompt,
        model=req.model,
        requested_tools=req.requested_tools,
        knowledge_base_id=req.knowledge_base_id,
    )
    return res
