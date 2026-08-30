import ast
import operator
import logging
from typing import Dict, Any, List, Optional, Callable
from .models import ToolDefinition

logger = logging.getLogger(__name__)

# Safe math evaluator for calculator tool
_SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
    ast.Mod: operator.mod,
}

def _eval_expr(node):
    if isinstance(node, ast.Num):
        return node.n
    elif isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    elif isinstance(node, ast.BinOp):
        left = _eval_expr(node.left)
        right = _eval_expr(node.right)
        op_type = type(node.op)
        if op_type in _SAFE_OPERATORS:
            return _SAFE_OPERATORS[op_type](left, right)
        raise ValueError(f"Unsupported binary operator: {op_type.__name__}")
    elif isinstance(node, ast.UnaryOp):
        operand = _eval_expr(node.operand)
        op_type = type(node.op)
        if op_type in _SAFE_OPERATORS:
            return _SAFE_OPERATORS[op_type](operand)
        raise ValueError(f"Unsupported unary operator: {op_type.__name__}")
    else:
        raise ValueError(f"Unsupported AST node: {type(node).__name__}")

def safe_calculator_handler(expression: str) -> Dict[str, Any]:
    """Safely evaluate arithmetic expression."""
    try:
        parsed = ast.parse(expression, mode='eval')
        result = _eval_expr(parsed.body)
        return {"expression": expression, "result": result, "status": "success"}
    except Exception as e:
        return {"expression": expression, "error": f"Invalid expression: {str(e)}", "status": "error"}

async def weather_handler(location: str, days: int = 1) -> Dict[str, Any]:
    """Get weather forecast for a location."""
    return {
        "location": location,
        "days": days,
        "temperature": "22°C",
        "condition": "Partly Cloudy",
        "humidity": "55%",
        "wind_speed": "12 km/h"
    }

async def web_search_handler(query: str, num_results: int = 3) -> Dict[str, Any]:
    """Simulated web search handler."""
    return {
        "query": query,
        "results": [
            {
                "title": f"Result for {query} - 1",
                "snippet": f"Overview and documentation regarding {query}.",
                "url": f"https://example.com/search?q={query}"
            },
            {
                "title": f"Deep dive into {query}",
                "snippet": f"In-depth analysis and standard practices for {query}.",
                "url": f"https://example.org/topics/{query}"
            }
        ][:num_results]
    }

async def document_reader_handler(document_id: str, section: Optional[str] = None) -> Dict[str, Any]:
    """Simulated document reader handler."""
    return {
        "document_id": document_id,
        "section": section or "full",
        "content": f"Sample document content for ID '{document_id}' section '{section or 'main'}'. Contains enterprise metadata.",
        "length": 150
    }

async def sql_query_handler(query: str, database_name: Optional[str] = "default_db") -> Dict[str, Any]:
    """SQL Query tool handler (read-only execution)."""
    return {
        "database": database_name,
        "query": query,
        "rows_returned": 2,
        "data": [
            {"id": 1, "name": "Alice Smith", "role": "admin", "status": "active"},
            {"id": 2, "name": "Bob Jones", "role": "developer", "status": "active"}
        ]
    }

async def http_client_handler(url: str, method: str = "GET", payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """HTTP client tool handler."""
    return {
        "url": url,
        "method": method.upper(),
        "status_code": 200,
        "response_body": {"message": "Success", "url": url}
    }

async def system_info_handler(metric: Optional[str] = "all") -> Dict[str, Any]:
    """Get system telemetry status."""
    return {
        "metric": metric,
        "status": "healthy",
        "cpu_usage": "18.4%",
        "memory_usage": "42.1%",
        "active_connections": 128
    }


class ToolRegistry:
    """Central registry for storing, discovering, and exporting tool definitions and handlers."""

    def __init__(self):
        self._tools: Dict[str, ToolDefinition] = {}
        self._handlers: Dict[str, Callable] = {}
        self._register_default_tools()

    def register_tool(
        self,
        name: str,
        description: str,
        parameters_schema: Dict[str, Any],
        handler: Callable,
        required_role: str = "developer",
        dangerous: bool = False
    ):
        """Register a new tool definition and its executable handler."""
        tool_def = ToolDefinition(
            name=name,
            description=description,
            parameters_schema=parameters_schema,
            required_role=required_role,
            dangerous=dangerous
        )
        self._tools[name] = tool_def
        self._handlers[name] = handler
        logger.info(f"[ToolRegistry] Registered tool '{name}' (role: {required_role}, dangerous: {dangerous})")

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        return self._tools.get(name)

    def get_handler(self, name: str) -> Optional[Callable]:
        return self._handlers.get(name)

    def list_tools(self, user_role: Optional[str] = None) -> List[ToolDefinition]:
        """List all tools, optionally filtered by minimum required role hierarchy."""
        if not user_role:
            return list(self._tools.values())
        
        # Simple role hierarchy: admin > developer > member > viewer
        hierarchy = {"admin": 4, "developer": 3, "member": 2, "viewer": 1}
        user_level = hierarchy.get(user_role.lower(), 1)
        
        allowed = []
        for tool in self._tools.values():
            tool_level = hierarchy.get(tool.required_role.lower(), 1)
            if user_level >= tool_level:
                allowed.append(tool)
        return allowed

    def export_openai_schemas(self, user_role: Optional[str] = None) -> List[Dict[str, Any]]:
        """Export tools in OpenAI Function Calling format."""
        tools = self.list_tools(user_role)
        result = []
        for t in tools:
            result.append({
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters_schema
                }
            })
        return result

    def _register_default_tools(self):
        """Register built-in platform tools."""
        self.register_tool(
            name="calculator",
            description="Evaluate mathematical expressions safely.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "expression": {"type": "string", "description": "Arithmetic expression e.g. 15 * 4 + 10"}
                },
                "required": ["expression"]
            },
            handler=safe_calculator_handler,
            required_role="viewer",
            dangerous=False
        )

        self.register_tool(
            name="weather",
            description="Get current weather or forecast for a city.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City name, e.g. London, Tokyo"},
                    "days": {"type": "integer", "description": "Number of forecast days (1-7)"}
                },
                "required": ["location"]
            },
            handler=weather_handler,
            required_role="member",
            dangerous=False
        )

        self.register_tool(
            name="web_search",
            description="Search the web for up-to-date information.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query string"},
                    "num_results": {"type": "integer", "description": "Number of results to return (default 3)"}
                },
                "required": ["query"]
            },
            handler=web_search_handler,
            required_role="developer",
            dangerous=False
        )

        self.register_tool(
            name="document_reader",
            description="Read content from enterprise knowledge base documents.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "document_id": {"type": "string", "description": "Unique document ID"},
                    "section": {"type": "string", "description": "Specific section header (optional)"}
                },
                "required": ["document_id"]
            },
            handler=document_reader_handler,
            required_role="developer",
            dangerous=False
        )

        self.register_tool(
            name="sql_query",
            description="Execute read-only SQL queries against tenant database.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "SQL SELECT query string"},
                    "database_name": {"type": "string", "description": "Target database (optional)"}
                },
                "required": ["query"]
            },
            handler=sql_query_handler,
            required_role="developer",
            dangerous=True
        )

        self.register_tool(
            name="http_client",
            description="Send an HTTP request to external APIs.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Target HTTP/HTTPS URL"},
                    "method": {"type": "string", "enum": ["GET", "POST"], "description": "HTTP method"},
                    "payload": {"type": "object", "description": "Request body JSON payload (optional)"}
                },
                "required": ["url"]
            },
            handler=http_client_handler,
            required_role="admin",
            dangerous=True
        )

        self.register_tool(
            name="system_info",
            description="Fetch platform metrics and health system telemetry.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "metric": {"type": "string", "description": "Metric focus (cpu, memory, connections, all)"}
                },
                "required": []
            },
            handler=system_info_handler,
            required_role="admin",
            dangerous=True
        )

# Global tool registry instance
tool_registry = ToolRegistry()
