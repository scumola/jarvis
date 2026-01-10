"""
Tool schema definitions.
Tools are the ONLY way LLMs can affect the system.
"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from enum import Enum


class ToolParameterType(str, Enum):
    """Supported parameter types for tools."""
    STRING = "string"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    ARRAY = "array"
    OBJECT = "object"


class ToolParameter(BaseModel):
    """Definition of a single tool parameter."""
    name: str
    type: ToolParameterType
    description: str
    required: bool = True
    default: Optional[Any] = None


class ToolSchema(BaseModel):
    """Complete schema for a tool."""
    name: str
    description: str
    parameters: List[ToolParameter]
    category: str  # e.g., "filesystem", "web", "analysis"
    requires_approval: bool = False  # Whether execution needs human approval
    dangerous: bool = False  # Whether this tool can modify system state


class ToolInvocation(BaseModel):
    """A request to invoke a tool."""
    tool_name: str
    parameters: Dict[str, Any]
    reasoning: Optional[str] = None  # Why the LLM wants to use this tool


class ToolResult(BaseModel):
    """Result of a tool execution."""
    success: bool
    output: Optional[Any] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
