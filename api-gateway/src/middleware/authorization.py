from fastapi import HTTPException, Request
from typing import List, Optional
import logging

logger = logging.getLogger(__name__)

class AuthorizationMiddleware:
    """Handle authorization and RBAC"""
    
    def __init__(self):
        self.role_permissions = {
            "owner": ["*"],
            "admin": ["chat", "documents", "users", "analytics", "settings"],
            "developer": ["chat", "documents", "analytics"],
            "member": ["chat", "documents"],
            "viewer": ["chat"]
        }
        
        self.endpoint_permissions = {
            "/api/v1/chat": ["chat"],
            "/api/v1/chat/stream": ["chat"],
            "/api/v1/documents": ["documents"],
            "/api/v1/tools": ["chat"],
            "/api/v1/users": ["users"],
            "/api/v1/settings": ["settings"]
        }
    
    def check_permission(self, roles: List[str], required_permission: str) -> bool:
        for role in roles:
            permissions = self.role_permissions.get(role, [])
            if "*" in permissions or required_permission in permissions:
                return True
        return False
    
    def get_required_permission(self, path: str) -> Optional[str]:
        for endpoint, permissions in self.endpoint_permissions.items():
            if path.startswith(endpoint):
                return permissions[0]
        return None
    
    async def authorize_request(self, request: Request):
        roles = getattr(request.state, "roles", [])
        
        if not roles:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": {
                        "code": "FORBIDDEN",
                        "message": "No roles assigned"
                    }
                }
            )
        
        required_permission = self.get_required_permission(request.url.path)
        if required_permission:
            if not self.check_permission(roles, required_permission):
                raise HTTPException(
                    status_code=403,
                    detail={
                        "error": {
                            "code": "INSUFFICIENT_PERMISSIONS",
                            "message": f"Required permission: {required_permission}"
                        }
                    }
                )

authorization_middleware = AuthorizationMiddleware()
