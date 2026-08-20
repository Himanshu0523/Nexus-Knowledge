from typing import Dict, Any
from fastapi import HTTPException, Request
import logging

logger = logging.getLogger(__name__)

class TenantResolver:
    """Resolve tenant from authentication context"""
    
    async def resolve_tenant(self, request: Request, auth_context: Dict[str, Any]) -> str:
        tenant_id = auth_context.get("tenant_id")
        
        if not tenant_id:
            raise HTTPException(
                status_code=401,
                detail={
                    "error": {
                        "code": "TENANT_NOT_FOUND",
                        "message": "Unable to resolve tenant"
                    }
                }
            )
        
        request.state.tenant_id = tenant_id
        request.state.user_id = auth_context.get("user_id")
        request.state.roles = auth_context.get("roles", [])
        return tenant_id
    
    def verify_tenant_access(self, requested_tenant: str, actual_tenant: str) -> bool:
        return requested_tenant == actual_tenant

tenant_resolver = TenantResolver()
