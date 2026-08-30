import re
import ipaddress
import logging
from urllib.parse import urlparse
from typing import Dict, Any, List, Optional, Set
from .models import PermissionDecision, ToolDefinition
from .registry import tool_registry

logger = logging.getLogger(__name__)

# Role hierarchy levels
ROLE_LEVELS = {
    "admin": 4,
    "developer": 3,
    "member": 2,
    "viewer": 1
}

# Dangerous tools requiring explicit human approval / admin confirmation
DANGEROUS_TOOLS: Set[str] = {
    "sql_query",
    "http_client",
    "system_info",
    "delete_database",
    "run_terminal_command"
}

class PermissionManager:
    """Manages role-based and tenant-based permissions for tools."""

    def __init__(self):
        # Tenant overrides: tenant_id -> list of blocked tools
        self._tenant_blocked_tools: Dict[str, Set[str]] = {}

    def set_tenant_blocked_tools(self, tenant_id: str, blocked_tools: List[str]):
        """Configure tenant specific tool bans."""
        self._tenant_blocked_tools[tenant_id] = set(blocked_tools)

    def check_permission(
        self,
        tool_name: str,
        user_role: str = "member",
        tenant_id: str = "default",
        tool_def: Optional[ToolDefinition] = None
    ) -> PermissionDecision:
        """Check if a tool call is permitted for the given role and tenant context."""
        
        # Fetch definition if not provided
        if not tool_def:
            tool_def = tool_registry.get_tool(tool_name)

        if not tool_def:
            return PermissionDecision(
                allowed=False,
                reason=f"Unknown tool '{tool_name}' not registered in tool registry."
            )

        # 1. Tenant restriction check
        blocked = self._tenant_blocked_tools.get(tenant_id, set())
        if tool_name in blocked:
            return PermissionDecision(
                allowed=False,
                reason=f"Tool '{tool_name}' is explicitly disabled for tenant '{tenant_id}'."
            )

        # 2. Role hierarchy check
        user_lvl = ROLE_LEVELS.get(user_role.lower(), 1)
        required_lvl = ROLE_LEVELS.get(tool_def.required_role.lower(), 3)

        if user_lvl < required_lvl:
            return PermissionDecision(
                allowed=False,
                reason=f"Insufficient role '{user_role}' for tool '{tool_name}'. Required role: '{tool_def.required_role}'."
            )

        # 3. Dangerous tool human approval requirement
        requires_approval = tool_def.dangerous or (tool_name in DANGEROUS_TOOLS)

        return PermissionDecision(
            allowed=True,
            reason=f"Tool '{tool_name}' permitted for role '{user_role}' in tenant '{tenant_id}'.",
            requires_approval=requires_approval
        )


class PolicyChecker:
    """Enforces fine-grained security policies on tool invocation payloads (SQL, HTTP, Payload limits)."""

    def __init__(self):
        # Disallowed SQL keywords/statements for sql_query tool
        self._banned_sql_pattern = re.compile(
            r"\b(DROP|DELETE|UPDATE|INSERT|ALTER|TRUNCATE|GRANT|REVOKE|EXEC|EXECUTE|CREATE|RENAME|REPLACE|MERGE|COPY)\b",
            re.IGNORECASE
        )
        # Private / SSRF IP subnets
        self._private_subnets = [
            ipaddress.ip_network("127.0.0.0/8"),
            ipaddress.ip_network("10.0.0.0/8"),
            ipaddress.ip_network("172.16.0.0/12"),
            ipaddress.ip_network("192.168.0.0/16"),
            ipaddress.ip_network("169.254.0.0/16"), # AWS IMDS / Cloud metadata
            ipaddress.ip_network("0.0.0.0/32"),
            ipaddress.ip_network("::1/128")
        ]

    def check_policy(self, tool_name: str, arguments: Dict[str, Any]) -> PermissionDecision:
        """Evaluate parameter payload against domain security policies."""
        
        # 1. Payload size policy (prevent Denial of Service / Memory Bombing)
        for key, val in arguments.items():
            if isinstance(val, str) and len(val) > 10000:
                return PermissionDecision(
                    allowed=False,
                    reason=f"Payload Policy Violation: Parameter '{key}' exceeds maximum allowed length of 10,000 characters."
                )

        # 2. Tool-specific policies
        if tool_name == "sql_query":
            return self._check_sql_policy(arguments.get("query", ""))
        
        elif tool_name == "http_client":
            return self._check_http_policy(arguments.get("url", ""))

        return PermissionDecision(allowed=True, reason="Payload policy checks passed.")

    def _check_sql_policy(self, query: str) -> PermissionDecision:
        """Enforce read-only SQL safety policy."""
        if not query or not query.strip():
            return PermissionDecision(allowed=False, reason="SQL Policy Violation: Empty query string.")

        clean_query = query.strip()

        # Disallow multi-statement execution
        if ";" in clean_query[:-1]:  # Allow trailing semicolon
            return PermissionDecision(
                allowed=False,
                reason="SQL Policy Violation: Multiple SQL statements separated by ';' are prohibited."
            )

        # Must start with SELECT or EXPLAIN or SHOW
        first_word = clean_query.split()[0].upper()
        if first_word not in ("SELECT", "EXPLAIN", "SHOW", "WITH"):
            return PermissionDecision(
                allowed=False,
                reason=f"SQL Policy Violation: Statement must begin with SELECT, EXPLAIN, WITH, or SHOW. Found: '{first_word}'."
            )

        # Check for banned mutating keywords
        match = self._banned_sql_pattern.search(clean_query)
        if match:
            return PermissionDecision(
                allowed=False,
                reason=f"SQL Policy Violation: Mutating SQL keyword '{match.group(0).upper()}' is strictly forbidden."
            )

        return PermissionDecision(allowed=True, reason="SQL safety policy passed.")

    def _check_http_policy(self, url: str) -> PermissionDecision:
        """Enforce anti-SSRF and URL safety policy."""
        if not url or not url.strip():
            return PermissionDecision(allowed=False, reason="HTTP Policy Violation: Empty URL.")

        try:
            parsed = urlparse(url)
        except Exception as e:
            return PermissionDecision(allowed=False, reason=f"HTTP Policy Violation: Malformed URL '{url}': {str(e)}")

        # Enforce valid scheme
        if parsed.scheme.lower() not in ("http", "https"):
            return PermissionDecision(
                allowed=False,
                reason=f"HTTP Policy Violation: Scheme '{parsed.scheme}' is prohibited. Only http/https are allowed."
            )

        hostname = parsed.hostname
        if not hostname:
            return PermissionDecision(allowed=False, reason="HTTP Policy Violation: Missing hostname.")

        # Check localhost / internal hostname aliases
        hostname_lower = hostname.lower()
        if hostname_lower in ("localhost", "local", "metadata.google.internal", "169.254.169.254"):
            return PermissionDecision(
                allowed=False,
                reason=f"HTTP Policy Violation: Request to internal/metadata target '{hostname}' is blocked."
            )

        # Resolve IP address check
        try:
            ip_obj = ipaddress.ip_address(hostname)
            for subnet in self._private_subnets:
                if ip_obj in subnet:
                    return PermissionDecision(
                        allowed=False,
                        reason=f"HTTP Policy Violation: Target IP '{hostname}' belongs to private/internal subnet {subnet}."
                    )
        except ValueError:
            # Hostname is a domain name (e.g. api.example.com), not an IP address
            pass

        return PermissionDecision(allowed=True, reason="HTTP SSRF safety policy passed.")


# Global instances
permission_manager = PermissionManager()
policy_checker = PolicyChecker()
