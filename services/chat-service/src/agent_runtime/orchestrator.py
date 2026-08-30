import json
import uuid
import logging
from typing import Dict, Any, List, Optional, AsyncGenerator
from .models import (
    AgentStepRecord,
    AgentRuntimeResponse,
    ToolCallProposal,
    ToolExecutionStatus,
    PermissionDecision,
    ValidationResult,
    AuditLogEntry
)
from .registry import tool_registry, ToolRegistry
from .permissions import permission_manager, policy_checker, PermissionManager, PolicyChecker
from .validation import schema_validator, SchemaValidator
from .sandbox import execution_sandbox, ExecutionSandbox
from .events import (
    AgentStreamEvent,
    AgentPlanEvent,
    ToolProposedEvent,
    ToolValidationEvent,
    ToolExecutionEvent,
    AgentDoneEvent
)

logger = logging.getLogger(__name__)

class AgentRuntime:
    """Planner/Orchestrator pattern for secure tool selection, validation, sandboxed execution, and multi-step reasoning."""

    def __init__(
        self,
        registry: Optional[ToolRegistry] = None,
        perm_mgr: Optional[PermissionManager] = None,
        policy_chk: Optional[PolicyChecker] = None,
        validator: Optional[SchemaValidator] = None,
        sandbox: Optional[ExecutionSandbox] = None,
        max_iterations: int = 5
    ):
        self.registry = registry or tool_registry
        self.perm_mgr = perm_mgr or permission_manager
        self.policy_chk = policy_chk or policy_checker
        self.validator = validator or schema_validator
        self.sandbox = sandbox or execution_sandbox
        self.max_iterations = max_iterations

    async def run(
        self,
        user_prompt: str,
        conversation_id: Optional[str] = None,
        tenant_id: str = "default",
        user_role: str = "member",
        user_id: Optional[str] = None
    ) -> AgentRuntimeResponse:
        """Run the full non-streaming ReAct agent loop."""
        conv_id = conversation_id or f"agent_conv_{uuid.uuid4().hex[:8]}"
        trajectory: List[AgentStepRecord] = []
        executed_tools: List[str] = []
        
        step_number = 1
        current_context = user_prompt
        final_answer = ""
        
        while step_number <= self.max_iterations:
            logger.info(f"[AgentRuntime] Starting step {step_number}/{self.max_iterations} for conv {conv_id}")
            
            # Step 1: Propose plan and tool action
            proposal_data = self._generate_llm_proposal(current_context, step_number, user_role)
            thought = proposal_data.get("thought", f"Analyzing step {step_number}")
            tool_proposal: Optional[ToolCallProposal] = proposal_data.get("tool_call")
            
            step_record = AgentStepRecord(
                step_number=step_number,
                plan_thought=thought,
                tool_call=tool_proposal
            )

            # If no tool is proposed, LLM has arrived at final answer
            if not tool_proposal:
                final_answer = proposal_data.get("final_answer", thought)
                trajectory.append(step_record)
                break

            call_id = tool_proposal.call_id
            tool_name = tool_proposal.name
            raw_args = tool_proposal.arguments

            # Step 2: Permission Check
            perm_decision = self.perm_mgr.check_permission(
                tool_name=tool_name,
                user_role=user_role,
                tenant_id=tenant_id
            )
            step_record.permission_decision = perm_decision

            if not perm_decision.allowed:
                step_record.execution_status = ToolExecutionStatus.PERMISSION_DENIED
                step_record.observation = f"[SECURITY REJECTION]: {perm_decision.reason}"
                self.sandbox.record_security_failure(
                    call_id=call_id,
                    tool_name=tool_name,
                    tenant_id=tenant_id,
                    user_role=user_role,
                    user_id=user_id,
                    input_args=raw_args,
                    status=ToolExecutionStatus.PERMISSION_DENIED,
                    error_message=perm_decision.reason
                )
                trajectory.append(step_record)
                current_context += f"\nObservation: {step_record.observation}"
                step_number += 1
                continue

            # Step 3: Policy Check
            pol_decision = self.policy_chk.check_policy(tool_name, raw_args)
            if not pol_decision.allowed:
                step_record.permission_decision = pol_decision
                step_record.execution_status = ToolExecutionStatus.POLICY_VIOLATION
                step_record.observation = f"[POLICY REJECTION]: {pol_decision.reason}"
                self.sandbox.record_security_failure(
                    call_id=call_id,
                    tool_name=tool_name,
                    tenant_id=tenant_id,
                    user_role=user_role,
                    user_id=user_id,
                    input_args=raw_args,
                    status=ToolExecutionStatus.POLICY_VIOLATION,
                    error_message=pol_decision.reason
                )
                trajectory.append(step_record)
                current_context += f"\nObservation: {step_record.observation}"
                step_number += 1
                continue

            # Step 4: Input Schema Validation
            tool_def = self.registry.get_tool(tool_name)
            val_result = self.validator.validate(tool_def, raw_args)
            step_record.validation_result = val_result

            if not val_result.valid:
                err_str = "; ".join(val_result.errors)
                step_record.execution_status = ToolExecutionStatus.VALIDATION_ERROR
                step_record.observation = f"[SCHEMA VALIDATION ERROR]: {err_str}"
                self.sandbox.record_security_failure(
                    call_id=call_id,
                    tool_name=tool_name,
                    tenant_id=tenant_id,
                    user_role=user_role,
                    user_id=user_id,
                    input_args=raw_args,
                    status=ToolExecutionStatus.VALIDATION_ERROR,
                    error_message=err_str
                )
                trajectory.append(step_record)
                current_context += f"\nObservation: {step_record.observation}"
                step_number += 1
                continue

            # Step 5: Execution Sandbox
            handler = self.registry.get_handler(tool_name)
            exec_result = await self.sandbox.execute(
                tool_def=tool_def,
                handler=handler,
                sanitized_args=val_result.sanitized_args,
                call_id=call_id,
                tenant_id=tenant_id,
                user_role=user_role,
                user_id=user_id
            )

            step_record.execution_status = ToolExecutionStatus(exec_result["status"])
            if exec_result["status"] == ToolExecutionStatus.SUCCESS.value:
                step_record.observation = json.dumps(exec_result["output"])
                executed_tools.append(tool_name)
            else:
                step_record.observation = f"[EXECUTION ERROR]: {exec_result['error_message']}"

            trajectory.append(step_record)
            current_context += f"\nObservation from tool '{tool_name}': {step_record.observation}"
            step_number += 1

        if not final_answer:
            final_answer = f"Agent finished after {step_number - 1} steps. Trajectory observed: " + "; ".join(
                [f"Step {t.step_number}: {t.observation[:60]}..." for t in trajectory if t.observation]
            )

        audit_logs = self.sandbox.get_audit_logs(tenant_id=tenant_id, limit=len(trajectory))

        return AgentRuntimeResponse(
            conversation_id=conv_id,
            final_response=final_answer,
            trajectory=trajectory,
            tools_executed=executed_tools,
            audit_logs=audit_logs,
            iterations_used=len(trajectory),
            status="completed"
        )

    async def run_stream(
        self,
        user_prompt: str,
        conversation_id: Optional[str] = None,
        tenant_id: str = "default",
        user_role: str = "member",
        user_id: Optional[str] = None
    ) -> AsyncGenerator[AgentStreamEvent, None]:
        """Stream the ReAct agent steps via AsyncGenerator events."""
        conv_id = conversation_id or f"agent_conv_{uuid.uuid4().hex[:8]}"
        step_number = 1
        current_context = user_prompt
        final_answer = ""

        while step_number <= self.max_iterations:
            proposal_data = self._generate_llm_proposal(current_context, step_number, user_role)
            thought = proposal_data.get("thought", f"Analyzing step {step_number}")
            tool_proposal: Optional[ToolCallProposal] = proposal_data.get("tool_call")

            yield AgentPlanEvent(step_number=step_number, thought=thought)

            if not tool_proposal:
                final_answer = proposal_data.get("final_answer", thought)
                yield AgentDoneEvent(final_response=final_answer, trajectory_length=step_number)
                return

            call_id = tool_proposal.call_id
            tool_name = tool_proposal.name
            raw_args = tool_proposal.arguments

            yield ToolProposedEvent(step_number=step_number, call_id=call_id, tool_name=tool_name, arguments=raw_args)

            # Permission check
            perm_decision = self.perm_mgr.check_permission(tool_name, user_role, tenant_id)
            if not perm_decision.allowed:
                yield ToolValidationEvent(step_number=step_number, call_id=call_id, tool_name=tool_name, allowed=False, reason=perm_decision.reason)
                self.sandbox.record_security_failure(call_id, tool_name, tenant_id, user_role, user_id, raw_args, ToolExecutionStatus.PERMISSION_DENIED, perm_decision.reason)
                current_context += f"\nObservation: [SECURITY REJECTION]: {perm_decision.reason}"
                step_number += 1
                continue

            # Policy check
            pol_decision = self.policy_chk.check_policy(tool_name, raw_args)
            if not pol_decision.allowed:
                yield ToolValidationEvent(step_number=step_number, call_id=call_id, tool_name=tool_name, allowed=False, reason=pol_decision.reason)
                self.sandbox.record_security_failure(call_id, tool_name, tenant_id, user_role, user_id, raw_args, ToolExecutionStatus.POLICY_VIOLATION, pol_decision.reason)
                current_context += f"\nObservation: [POLICY REJECTION]: {pol_decision.reason}"
                step_number += 1
                continue

            yield ToolValidationEvent(step_number=step_number, call_id=call_id, tool_name=tool_name, allowed=True, reason=perm_decision.reason)

            # Schema validation
            tool_def = self.registry.get_tool(tool_name)
            val_result = self.validator.validate(tool_def, raw_args)

            if not val_result.valid:
                err_str = "; ".join(val_result.errors)
                yield ToolExecutionEvent(step_number=step_number, call_id=call_id, tool_name=tool_name, status=ToolExecutionStatus.VALIDATION_ERROR.value, error=err_str)
                self.sandbox.record_security_failure(call_id, tool_name, tenant_id, user_role, user_id, raw_args, ToolExecutionStatus.VALIDATION_ERROR, err_str)
                current_context += f"\nObservation: [SCHEMA ERROR]: {err_str}"
                step_number += 1
                continue

            # Execution
            handler = self.registry.get_handler(tool_name)
            exec_res = await self.sandbox.execute(tool_def, handler, val_result.sanitized_args, call_id, tenant_id, user_role, user_id)

            yield ToolExecutionEvent(
                step_number=step_number,
                call_id=call_id,
                tool_name=tool_name,
                status=exec_res["status"],
                result=exec_res["output"],
                error=exec_res["error_message"],
                execution_time_ms=exec_res["execution_time_ms"]
            )

            obs_str = json.dumps(exec_res["output"]) if exec_res["status"] == "SUCCESS" else exec_res["error_message"]
            current_context += f"\nObservation from '{tool_name}': {obs_str}"
            step_number += 1

        if not final_answer:
            final_answer = "Completed maximum iterations."
        yield AgentDoneEvent(final_response=final_answer, trajectory_length=step_number - 1)

    def _generate_llm_proposal(self, prompt_context: str, step: int, user_role: str) -> Dict[str, Any]:
        """Intelligent planner parser that translates prompt intent into tool call proposals."""
        lowered = prompt_context.lower()
        call_id = f"call_{uuid.uuid4().hex[:8]}"

        # If observation from previous step is available, check if we can conclude
        if "observation" in lowered and step > 1:
            # We have tool observation, build final response
            if "calculator" in lowered or "result" in lowered:
                return {
                    "thought": "I have received the calculation result and can now answer the user.",
                    "final_answer": f"Based on the tool calculation: {prompt_context.split('Observation')[-1].strip()}"
                }
            elif "weather" in lowered:
                return {
                    "thought": "I have retrieved the weather information.",
                    "final_answer": f"Here is the weather forecast: {prompt_context.split('Observation')[-1].strip()}"
                }
            elif "sql_query" in lowered:
                return {
                    "thought": "I have executed the database query.",
                    "final_answer": f"Database query result: {prompt_context.split('Observation')[-1].strip()}"
                }
            elif "web_search" in lowered:
                return {
                    "thought": "I have completed the web search.",
                    "final_answer": f"Search results: {prompt_context.split('Observation')[-1].strip()}"
                }
            elif "http_client" in lowered:
                return {
                    "thought": "I have executed the HTTP request.",
                    "final_answer": f"HTTP response: {prompt_context.split('Observation')[-1].strip()}"
                }
            elif "rejection" in lowered.lower() or "error" in lowered.lower():
                return {
                    "thought": "The tool call was rejected or returned an error. Explaining to user.",
                    "final_answer": f"Request could not be processed due to: {prompt_context.split('Observation')[-1].strip()}"
                }

        # Step 1 Intent Matching

        # 1. Calculator intent
        if any(kw in lowered for kw in ["calculate", "math", "+", "*", "eval", "expression"]):
            import re
            expr_match = re.search(r"([\d\.\s\+\-\*\/\(\)]+)", prompt_context)
            expr = expr_match.group(1).strip() if expr_match else "2 + 2"
            return {
                "thought": f"The user asked for a mathematical calculation. I will call the 'calculator' tool with expression '{expr}'.",
                "tool_call": ToolCallProposal(
                    call_id=call_id,
                    name="calculator",
                    arguments={"expression": expr}
                )
            }

        # 2. Weather intent
        if "weather" in lowered or "temperature" in lowered or "forecast" in lowered:
            loc = "London"
            if "in " in lowered:
                loc = lowered.split("in ")[1].split()[0].title()
            return {
                "thought": f"The user requested weather for '{loc}'. I will call the 'weather' tool.",
                "tool_call": ToolCallProposal(
                    call_id=call_id,
                    name="weather",
                    arguments={"location": loc, "days": 1}
                )
            }

        # 3. SQL Query intent (Test SQL safety policy)
        if "drop table" in lowered or "delete from" in lowered or "select" in lowered or "sql" in lowered or "query database" in lowered:
            query = "SELECT * FROM users;"
            if "drop table" in lowered:
                query = "DROP TABLE users;"
            elif "delete from" in lowered:
                query = "DELETE FROM users WHERE active = false;"
            elif "select" in lowered:
                query = prompt_context[prompt_context.lower().find("select"):]
            return {
                "thought": "The user wants to execute a database query. Proposing 'sql_query' tool.",
                "tool_call": ToolCallProposal(
                    call_id=call_id,
                    name="sql_query",
                    arguments={"query": query}
                )
            }

        # 4. HTTP Client intent (Test HTTP SSRF policy)
        if "http" in lowered or "fetch url" in lowered or "api call" in lowered or "localhost" in lowered or "169.254" in lowered:
            target_url = "https://api.example.com/data"
            if "127.0.0.1" in lowered or "localhost" in lowered:
                target_url = "http://localhost:8080/admin"
            elif "169.254.169.254" in lowered:
                target_url = "http://169.254.169.254/latest/meta-data/"
            return {
                "thought": f"The user requested an HTTP request to '{target_url}'. Proposing 'http_client' tool.",
                "tool_call": ToolCallProposal(
                    call_id=call_id,
                    name="http_client",
                    arguments={"url": target_url, "method": "GET"}
                )
            }

        # 5. Web Search intent
        if "search" in lowered or "find online" in lowered or "google" in lowered:
            return {
                "thought": f"Searching web for query.",
                "tool_call": ToolCallProposal(
                    call_id=call_id,
                    name="web_search",
                    arguments={"query": prompt_context, "num_results": 2}
                )
            }

        # 6. Document Reader intent
        if "document" in lowered or "read doc" in lowered:
            return {
                "thought": "Reading enterprise document.",
                "tool_call": ToolCallProposal(
                    call_id=call_id,
                    name="document_reader",
                    arguments={"document_id": "doc_123"}
                )
            }

        # 7. System Info intent
        if "system info" in lowered or "metrics" in lowered or "cpu" in lowered:
            return {
                "thought": "Fetching platform system telemetry.",
                "tool_call": ToolCallProposal(
                    call_id=call_id,
                    name="system_info",
                    arguments={"metric": "all"}
                )
            }

        # Default direct answer
        return {
            "thought": "No tool call is required for this query. Responding directly to user.",
            "final_answer": f"I can assist you with your request: '{prompt_context}'. Let me know if you would like to run any calculations, database queries, or web searches!"
        }


# Global agent runtime orchestrator instance
agent_runtime = AgentRuntime()
