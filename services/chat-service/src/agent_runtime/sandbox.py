import time
import asyncio
import inspect
import datetime
import logging
from typing import Dict, Any, List, Optional, Callable
from .models import ToolDefinition, ToolExecutionStatus, AuditLogEntry

logger = logging.getLogger(__name__)

class ExecutionSandbox:
    """Isolated execution environment for tools with timeouts, exception shielding, and audit logging."""

    def __init__(self, default_timeout_seconds: float = 5.0):
        self.default_timeout_seconds = default_timeout_seconds
        self._audit_trail: List[AuditLogEntry] = []
        self._max_audit_logs = 1000

    async def execute(
        self,
        tool_def: ToolDefinition,
        handler: Callable,
        sanitized_args: Dict[str, Any],
        call_id: str,
        tenant_id: str = "default",
        user_role: str = "member",
        user_id: Optional[str] = None,
        timeout: Optional[float] = None
    ) -> Dict[str, Any]:
        """Execute a tool handler inside an isolated sandbox with timeout and exception safety."""
        start_time = time.perf_counter()
        exec_timeout = timeout or self.default_timeout_seconds

        status = ToolExecutionStatus.SUCCESS
        output = None
        error_message = None

        try:
            # Execute handler with timeout safety
            if inspect.iscoroutinefunction(handler):
                output = await asyncio.wait_for(handler(**sanitized_args), timeout=exec_timeout)
            else:
                # Run synchronous handlers in thread pool executor to avoid blocking event loop
                loop = asyncio.get_event_loop()
                output = await asyncio.wait_for(
                    loop.run_in_executor(None, lambda: handler(**sanitized_args)),
                    timeout=exec_timeout
                )

        except asyncio.TimeoutError:
            status = ToolExecutionStatus.TIMEOUT
            error_message = f"Tool '{tool_def.name}' execution timed out after {exec_timeout} seconds."
            output = {"error": error_message, "status": "timeout"}
            logger.error(f"[ExecutionSandbox] {error_message}")

        except Exception as e:
            status = ToolExecutionStatus.EXECUTION_ERROR
            error_message = f"Unhandled exception in tool '{tool_def.name}': {str(e)}"
            output = {"error": str(e), "status": "error"}
            logger.error(f"[ExecutionSandbox] {error_message}", exc_info=True)

        execution_time_ms = round((time.perf_counter() - start_time) * 1000, 2)

        # Record audit log entry
        audit_entry = AuditLogEntry(
            call_id=call_id,
            tool_name=tool_def.name,
            tenant_id=tenant_id,
            user_id=user_id,
            user_role=user_role,
            input_args=sanitized_args,
            status=status,
            output=output if status == ToolExecutionStatus.SUCCESS else None,
            error_message=error_message,
            execution_time_ms=execution_time_ms,
            timestamp=datetime.datetime.utcnow().isoformat() + "Z"
        )
        self._record_audit_log(audit_entry)

        return {
            "status": status.value,
            "output": output,
            "error_message": error_message,
            "execution_time_ms": execution_time_ms
        }

    def record_security_failure(
        self,
        call_id: str,
        tool_name: str,
        tenant_id: str,
        user_role: str,
        user_id: Optional[str],
        input_args: Dict[str, Any],
        status: ToolExecutionStatus,
        error_message: str
    ):
        """Record explicit permission or policy failure audit log entry."""
        audit_entry = AuditLogEntry(
            call_id=call_id,
            tool_name=tool_name,
            tenant_id=tenant_id,
            user_id=user_id,
            user_role=user_role,
            input_args=input_args,
            status=status,
            output=None,
            error_message=error_message,
            execution_time_ms=0.0,
            timestamp=datetime.datetime.utcnow().isoformat() + "Z"
        )
        self._record_audit_log(audit_entry)

    def _record_audit_log(self, entry: AuditLogEntry):
        """Append log entry to audit buffer."""
        self._audit_trail.append(entry)
        if len(self._audit_trail) > self._max_audit_logs:
            self._audit_trail.pop(0)

    def get_audit_logs(
        self,
        tenant_id: Optional[str] = None,
        tool_name: Optional[str] = None,
        limit: int = 50
    ) -> List[AuditLogEntry]:
        """Retrieve recent audit logs with optional filtering."""
        logs = self._audit_trail
        if tenant_id:
            logs = [l for l in logs if l.tenant_id == tenant_id]
        if tool_name:
            logs = [l for l in logs if l.tool_name == tool_name]
        return list(reversed(logs[-limit:]))

    def clear_audit_logs(self):
        """Clear audit logs buffer."""
        self._audit_trail.clear()


execution_sandbox = ExecutionSandbox()
