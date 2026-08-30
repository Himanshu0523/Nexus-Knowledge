import pytest
import asyncio
from src.agent_runtime import (
    tool_registry,
    ToolRegistry,
    permission_manager,
    PermissionManager,
    policy_checker,
    PolicyChecker,
    schema_validator,
    SchemaValidator,
    execution_sandbox,
    ExecutionSandbox,
    agent_runtime,
    AgentRuntime,
    ToolExecutionStatus,
    ToolDefinition
)

@pytest.mark.asyncio
async def test_tool_registry_registration():
    registry = ToolRegistry()
    tools = registry.list_tools()
    assert len(tools) >= 7
    names = [t.name for t in tools]
    assert "calculator" in names
    assert "weather" in names
    assert "sql_query" in names
    assert "http_client" in names

    schemas = registry.export_openai_schemas(user_role="admin")
    assert len(schemas) >= 7
    calc_schema = next(s for s in schemas if s["function"]["name"] == "calculator")
    assert calc_schema["type"] == "function"
    assert "expression" in calc_schema["function"]["parameters"]["properties"]

@pytest.mark.asyncio
async def test_permission_manager():
    perm_mgr = PermissionManager()
    
    # Viewer role trying to use admin tool (http_client) -> Denied
    res = perm_mgr.check_permission(tool_name="http_client", user_role="viewer", tenant_id="tenant1")
    assert not res.allowed
    assert "Insufficient role" in res.reason

    # Developer role using developer tool (sql_query) -> Allowed, requires approval because dangerous
    res_dev = perm_mgr.check_permission(tool_name="sql_query", user_role="developer", tenant_id="tenant1")
    assert res_dev.allowed
    assert res_dev.requires_approval

    # Tenant blocking tool
    perm_mgr.set_tenant_blocked_tools("tenant1", ["weather"])
    res_blocked = perm_mgr.check_permission(tool_name="weather", user_role="developer", tenant_id="tenant1")
    assert not res_blocked.allowed
    assert "explicitly disabled" in res_blocked.reason

@pytest.mark.asyncio
async def test_policy_checker_sql():
    chk = PolicyChecker()

    # Valid SELECT query
    res1 = chk.check_policy("sql_query", {"query": "SELECT id, name FROM users WHERE active = true;"})
    assert res1.allowed

    # Mutating DROP query -> Rejected
    res2 = chk.check_policy("sql_query", {"query": "DROP TABLE users;"})
    assert not res2.allowed
    assert "SQL Policy Violation" in res2.reason

    # Mutating DELETE query -> Rejected
    res3 = chk.check_policy("sql_query", {"query": "DELETE FROM users WHERE 1=1;"})
    assert not res3.allowed

    # Multi-statement query -> Rejected
    res4 = chk.check_policy("sql_query", {"query": "SELECT 1; SELECT 2;"})
    assert not res4.allowed

@pytest.mark.asyncio
async def test_policy_checker_http():
    chk = PolicyChecker()

    # Valid external HTTPS URL
    res1 = chk.check_policy("http_client", {"url": "https://api.github.com/zen"})
    assert res1.allowed

    # Localhost SSRF -> Rejected
    res2 = chk.check_policy("http_client", {"url": "http://localhost:8000/metrics"})
    assert not res2.allowed
    assert "HTTP Policy Violation" in res2.reason

    # Cloud Metadata SSRF IP -> Rejected
    res3 = chk.check_policy("http_client", {"url": "http://169.254.169.254/latest/meta-data/"})
    assert not res3.allowed
    assert "private/internal subnet" in res3.reason or "internal/metadata target" in res3.reason

    # Non-HTTP protocol (file://) -> Rejected
    res4 = chk.check_policy("http_client", {"url": "file:///etc/passwd"})
    assert not res4.allowed

@pytest.mark.asyncio
async def test_schema_validator():
    val = SchemaValidator()
    tool_def = ToolDefinition(
        name="test_tool",
        description="test",
        parameters_schema={
            "type": "object",
            "properties": {
                "count": {"type": "integer"},
                "name": {"type": "string"},
                "active": {"type": "boolean"}
            },
            "required": ["count", "name"]
        }
    )

    # Valid inputs with type casting
    res1 = val.validate(tool_def, {"count": "10", "name": "test_bot", "active": "true"})
    assert res1.valid
    assert res1.sanitized_args["count"] == 10
    assert res1.sanitized_args["active"] is True

    # Missing required argument
    res2 = val.validate(tool_def, {"count": 5})
    assert not res2.valid
    assert any("Missing required" in e for e in res2.errors)

@pytest.mark.asyncio
async def test_execution_sandbox_timeout_and_errors():
    sandbox = ExecutionSandbox(default_timeout_seconds=0.2)

    # Fast tool handler
    async def fast_handler(msg: str):
        return {"response": f"Hello {msg}"}

    tool_def = ToolDefinition(name="fast", description="fast", parameters_schema={})
    res1 = await sandbox.execute(tool_def, fast_handler, {"msg": "World"}, call_id="c1")
    assert res1["status"] == ToolExecutionStatus.SUCCESS.value
    assert res1["output"] == {"response": "Hello World"}

    # Slow tool handler triggering timeout
    async def slow_handler():
        await asyncio.sleep(1.0)
        return "done"

    slow_def = ToolDefinition(name="slow", description="slow", parameters_schema={})
    res2 = await sandbox.execute(slow_def, slow_handler, {}, call_id="c2")
    assert res2["status"] == ToolExecutionStatus.TIMEOUT.value
    assert "timed out" in res2["error_message"]

    # Check audit logs recorded
    logs = sandbox.get_audit_logs()
    assert len(logs) >= 2

@pytest.mark.asyncio
async def test_agent_runtime_react_calculator():
    runtime = AgentRuntime()
    response = await runtime.run(
        user_prompt="Please calculate 15 * 4 + 10",
        tenant_id="tenant_a",
        user_role="member"
    )
    assert response.status == "completed"
    assert "calculator" in response.tools_executed
    assert response.iterations_used >= 1
    assert "70" in response.final_response

@pytest.mark.asyncio
async def test_agent_runtime_sql_rejection():
    runtime = AgentRuntime()
    response = await runtime.run(
        user_prompt="Run query DROP TABLE users;",
        tenant_id="tenant_a",
        user_role="admin"
    )
    assert response.status == "completed"
    assert len(response.trajectory) >= 1
    # Check that policy or permission rejection occurred
    rejection_step = response.trajectory[0]
    assert rejection_step.execution_status in (ToolExecutionStatus.POLICY_VIOLATION, ToolExecutionStatus.PERMISSION_DENIED)
    assert "REJECTION" in rejection_step.observation

@pytest.mark.asyncio
async def test_agent_runtime_http_ssrf_rejection():
    runtime = AgentRuntime()
    response = await runtime.run(
        user_prompt="Fetch URL http://169.254.169.254/latest/meta-data/",
        tenant_id="tenant_a",
        user_role="admin"
    )
    assert response.status == "completed"
    assert len(response.trajectory) >= 1
    rejection_step = response.trajectory[0]
    assert rejection_step.execution_status == ToolExecutionStatus.POLICY_VIOLATION
    assert "POLICY REJECTION" in rejection_step.observation

@pytest.mark.asyncio
async def test_agent_runtime_streaming():
    runtime = AgentRuntime()
    events = []
    async for event in runtime.run_stream(user_prompt="calculate 100 / 5", user_role="member"):
        events.append(event)
    
    types = [e.event_type for e in events]
    assert "agent_plan" in types
    assert "tool_proposed" in types
    assert "tool_validation" in types
    assert "tool_execution" in types
    assert "agent_done" in types
