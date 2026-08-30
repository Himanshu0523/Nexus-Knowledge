from typing import Dict, Any, Optional
import time

class AgentStreamEvent:
    """Base class for SSE Agent Runtime events."""
    def __init__(self, event_type: str, data: Dict[str, Any]):
        self.event_type = event_type
        self.data = data
        self.timestamp = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.event_type,
            "timestamp": self.timestamp,
            "data": self.data
        }

class AgentPlanEvent(AgentStreamEvent):
    def __init__(self, step_number: int, thought: str):
        super().__init__("agent_plan", {
            "step_number": step_number,
            "thought": thought
        })

class ToolProposedEvent(AgentStreamEvent):
    def __init__(self, step_number: int, call_id: str, tool_name: str, arguments: Dict[str, Any]):
        super().__init__("tool_proposed", {
            "step_number": step_number,
            "call_id": call_id,
            "tool_name": tool_name,
            "arguments": arguments
        })

class ToolValidationEvent(AgentStreamEvent):
    def __init__(self, step_number: int, call_id: str, tool_name: str, allowed: bool, reason: str):
        super().__init__("tool_validation", {
            "step_number": step_number,
            "call_id": call_id,
            "tool_name": tool_name,
            "allowed": allowed,
            "reason": reason
        })

class ToolExecutionEvent(AgentStreamEvent):
    def __init__(self, step_number: int, call_id: str, tool_name: str, status: str, result: Optional[Any] = None, error: Optional[str] = None, execution_time_ms: float = 0.0):
        super().__init__("tool_execution", {
            "step_number": step_number,
            "call_id": call_id,
            "tool_name": tool_name,
            "status": status,
            "result": result,
            "error": error,
            "execution_time_ms": execution_time_ms
        })

class AgentDoneEvent(AgentStreamEvent):
    def __init__(self, final_response: str, trajectory_length: int):
        super().__init__("agent_done", {
            "final_response": final_response,
            "trajectory_length": trajectory_length
        })
