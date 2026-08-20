import logging
from typing import Dict, Set, List

logger = logging.getLogger(__name__)

# Role-based tool access matrix
ROLE_TOOL_PERMISSIONS: Dict[str, Set[str]] = {
    "admin": {"calculator", "weather", "web_search", "document_reader", "system_info"},
    "developer": {"calculator", "weather", "web_search", "document_reader"},
    "member": {"calculator", "weather"},
    "viewer": {"calculator"},
}

# Dangerous tools that require explicit confirmation/approval
DANGEROUS_TOOLS: Set[str] = {"delete_database", "send_email", "execute_command"}

class ToolPermissionManager:
    """RBAC and Safety Checker for tool invocation requests."""

    @staticmethod
    def is_tool_allowed(tool_name: str, role: str = "developer") -> bool:
        """Check if a given role has permission to run a tool."""
        allowed_tools = ROLE_TOOL_PERMISSIONS.get(role, ROLE_TOOL_PERMISSIONS["viewer"])
        if tool_name not in allowed_tools:
            logger.warning(f"[ToolPermissions] Denied tool '{tool_name}' for role '{role}'")
            return False
        return True

    @staticmethod
    def requires_approval(tool_name: str) -> bool:
        """Check if the tool execution is high-risk and requires human confirmation."""
        return tool_name in DANGEROUS_TOOLS

tool_permissions = ToolPermissionManager()
