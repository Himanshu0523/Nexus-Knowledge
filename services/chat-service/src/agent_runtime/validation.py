import logging
from typing import Dict, Any, List, Optional
from .models import ValidationResult, ToolDefinition

logger = logging.getLogger(__name__)

class SchemaValidator:
    """Validates and sanitizes tool arguments against declared JSON schema."""

    def validate(self, tool_def: ToolDefinition, arguments: Dict[str, Any]) -> ValidationResult:
        """Validate input arguments dictionary against tool schema."""
        errors: List[str] = []
        sanitized_args: Dict[str, Any] = {}

        schema = tool_def.parameters_schema or {}
        properties = schema.get("properties", {})
        required_fields = schema.get("required", [])

        # 1. Check for missing required fields
        for req in required_fields:
            if req not in arguments or arguments[req] is None:
                errors.append(f"Missing required parameter '{req}'.")

        # 2. Validate parameters and coerce safe types
        for param_name, param_value in arguments.items():
            if param_name not in properties:
                # Extra unknown argument: log warning and strip for safety
                logger.warning(f"[SchemaValidator] Stripping unknown arg '{param_name}' for tool '{tool_def.name}'")
                continue

            param_spec = properties[param_name]
            expected_type = param_spec.get("type")

            # Check type and perform safe casting if needed
            valid_type, casted_val, err_msg = self._check_and_cast(param_name, param_value, expected_type, param_spec)
            if not valid_type:
                errors.append(err_msg)
            else:
                sanitized_args[param_name] = casted_val

        # Copy any missing default properties if available
        for prop_name, prop_spec in properties.items():
            if prop_name not in sanitized_args and "default" in prop_spec:
                sanitized_args[prop_name] = prop_spec["default"]

        return ValidationResult(
            valid=len(errors) == 0,
            sanitized_args=sanitized_args,
            errors=errors
        )

    def _check_and_cast(self, name: str, value: Any, expected_type: Optional[str], spec: Dict[str, Any]):
        """Helper to validate type and enum constraints."""
        if value is None:
            return True, None, ""

        if expected_type == "string":
            if not isinstance(value, str):
                return False, None, f"Parameter '{name}' must be a string. Got {type(value).__name__}."
            
            # Check enum constraint if specified
            if "enum" in spec and value not in spec["enum"]:
                return False, None, f"Parameter '{name}' value '{value}' must be one of {spec['enum']}."
            return True, str(value), ""

        elif expected_type in ("integer", "number"):
            if expected_type == "integer":
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    return False, None, f"Parameter '{name}' must be an integer. Got {type(value).__name__}."
                try:
                    casted = int(value)
                    return True, casted, ""
                except (ValueError, TypeError):
                    return False, None, f"Parameter '{name}' cannot be cast to integer."
            else:
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    return False, None, f"Parameter '{name}' must be a number. Got {type(value).__name__}."
                return True, float(value), ""

        elif expected_type == "boolean":
            if not isinstance(value, bool):
                if isinstance(value, str):
                    if value.lower() in ("true", "1"):
                        return True, True, ""
                    elif value.lower() in ("false", "0"):
                        return True, False, ""
                return False, None, f"Parameter '{name}' must be a boolean. Got {type(value).__name__}."
            return True, value, ""

        elif expected_type == "object":
            if not isinstance(value, dict):
                return False, None, f"Parameter '{name}' must be an object/dict. Got {type(value).__name__}."
            return True, value, ""

        elif expected_type == "array":
            if not isinstance(value, list):
                return False, None, f"Parameter '{name}' must be an array/list. Got {type(value).__name__}."
            return True, value, ""

        # Default fallback if expected_type is unspecified
        return True, value, ""


schema_validator = SchemaValidator()
