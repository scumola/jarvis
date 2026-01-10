"""
Tool registry - manages available tools and their metadata.
The orchestrator is the ONLY thing that writes to this registry.
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional, Callable
from .schema import ToolSchema, ToolInvocation, ToolResult

logger = logging.getLogger(__name__)


class ToolRegistry:
    """
    Registry of available tools.
    - Tools must be explicitly registered
    - LLMs never access this directly
    - Orchestrator uses this to validate and execute tools
    """

    def __init__(self, registry_path: str):
        self.registry_path = Path(registry_path)
        self.tools: Dict[str, ToolSchema] = {}
        self.implementations: Dict[str, Callable] = {}
        self._load_registry()

    def _load_registry(self):
        """Load tool registry from disk."""
        if self.registry_path.exists():
            try:
                with open(self.registry_path, 'r') as f:
                    data = json.load(f)
                    for tool_data in data.get('tools', []):
                        schema = ToolSchema(**tool_data)
                        self.tools[schema.name] = schema
                logger.info(f"Loaded {len(self.tools)} tools from registry")
            except Exception as e:
                logger.error(f"Failed to load registry: {e}")
        else:
            logger.info("No existing registry found, starting fresh")

    def _save_registry(self):
        """Persist tool registry to disk."""
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            'tools': [tool.model_dump() for tool in self.tools.values()]
        }
        with open(self.registry_path, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved {len(self.tools)} tools to registry")

    def register_tool(self, schema: ToolSchema, implementation: Callable):
        """
        Register a new tool.

        Args:
            schema: Tool schema definition
            implementation: Python function that implements the tool
        """
        if schema.name in self.tools:
            logger.warning(f"Tool {schema.name} already registered, overwriting")

        self.tools[schema.name] = schema
        self.implementations[schema.name] = implementation
        self._save_registry()
        logger.info(f"Registered tool: {schema.name}")

    def get_tool_schema(self, name: str) -> Optional[ToolSchema]:
        """Get schema for a specific tool."""
        return self.tools.get(name)

    def list_tools(self) -> List[ToolSchema]:
        """List all available tools."""
        return list(self.tools.values())

    def get_implementation(self, name: str) -> Optional[Callable]:
        """Get the implementation function for a tool."""
        return self.implementations.get(name)

    def validate_invocation(self, invocation: ToolInvocation) -> tuple[bool, Optional[str]]:
        """
        Validate a tool invocation request.

        Returns:
            (is_valid, error_message)
        """
        tool = self.tools.get(invocation.tool_name)
        if not tool:
            return False, f"Unknown tool: {invocation.tool_name}"

        # Check required parameters
        for param in tool.parameters:
            if param.required and param.name not in invocation.parameters:
                return False, f"Missing required parameter: {param.name}"

        # Check for unexpected parameters
        expected_params = {p.name for p in tool.parameters}
        provided_params = set(invocation.parameters.keys())
        unexpected = provided_params - expected_params
        if unexpected:
            return False, f"Unexpected parameters: {unexpected}"

        return True, None

    def get_tools_for_llm(self) -> List[Dict]:
        """
        Get tool definitions in a format suitable for LLM context.
        This is what the LLM sees when choosing tools.
        """
        tools_info = []
        for tool in self.tools.values():
            tool_info = {
                'name': tool.name,
                'description': tool.description,
                'parameters': [
                    {
                        'name': p.name,
                        'type': p.type,
                        'description': p.description,
                        'required': p.required,
                    }
                    for p in tool.parameters
                ]
            }
            tools_info.append(tool_info)
        return tools_info
