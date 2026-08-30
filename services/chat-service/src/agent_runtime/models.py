from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from enum import Enum

class ToolExecutionStatus(str, Enum):
    SUCCESS = "SUCCESS"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    POLICY_VIOLATION = "POLICY_VIOLATION"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    TIMEOUT = "TIMEOUT"
    EXECUTION_ERROR = "EXECUTION_ERROR"

class PermissionDecision(BaseModel):
    allowed: bool
    reason: str
    requires_approval: bool = False

class ValidationResult(BaseModel):
    valid: bool
    sanitized_args: Dict[str, Any] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)

class ToolDefinition(BaseModel):
    name: str
    description: str
    parameters_schema: Dict[str, Any]
    required_role: str = "developer"
    dangerous: bool = False

    class Config:
        arbitrary_types_allowed = True

class ToolCallProposal(BaseModel):
    call_id: str
    name: str
    arguments: Dict[str, Any]

class AuditLogEntry(BaseModel):
    call_id: str
    tool_name: str
    tenant_id: str
    user_id: Optional[str] = None
    user_role: str
    input_args: Dict[str, Any]
    status: ToolExecutionStatus
    output: Optional[Any] = None
    error_message: Optional[str] = None
    execution_time_ms: float
    timestamp: str

class AgentStepRecord(BaseModel):
    step_number: int
    plan_thought: str
    tool_call: Optional[ToolCallProposal] = None
    permission_decision: Optional[PermissionDecision] = None
    validation_result: Optional[ValidationResult] = None
    execution_status: Optional[ToolExecutionStatus] = None
    observation: Optional[str] = None

class AgentRuntimeResponse(BaseModel):
    conversation_id: str
    final_response: str
    trajectory: List[AgentStepRecord] = Field(default_factory=list)
    tools_executed: List[str] = Field(default_factory=list)
    audit_logs: List[AuditLogEntry] = Field(default_factory=list)
    iterations_used: int
    status: str = "completed"
