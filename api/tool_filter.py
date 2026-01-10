"""
Tool Access Control for API users.

Implements role-based access control for tools, restricting API users to
read-only and non-destructive operations while allowing master users full access.
"""

from typing import List, Dict, Set
import logging

logger = logging.getLogger(__name__)

# Tools that are ALLOWED for API users (whitelist approach)
# These are read-only and non-destructive operations
API_USER_ALLOWED_TOOLS: Set[str] = {
    # File read operations
    'read_file',
    'list_directory',
    'find_files',
    'grep',
    'head',
    'tail',
    'wc',
    'diff',  # Compare files (read-only)

    # Information retrieval
    'fetch_url',
    'web_search',
    'get_news_headlines',
    'get_datetime',
    'get_weather',

    # System information (read-only)
    'get_system_info',
    'get_process_info',

    # Backups are read-only
    'list_backups',
    'view_backup',

    # Memory operations (scoped to user)
    'search_memories',
    'list_memories',
}

# Tools that are BLOCKED for API users (destructive operations)
# This is for documentation purposes - the whitelist above is what's enforced
API_USER_BLOCKED_TOOLS: Set[str] = {
    # File write operations
    'write_file',
    'edit_file',
    'delete_file',
    'create_directory',
    'delete_directory',
    'move_file',
    'copy_file',

    # Backup restoration (modifies filesystem)
    'restore_backup',
    'create_backup',

    # System operations
    'execute_command',
    'run_script',
    'install_package',
    'kill_process',

    # Any other destructive operations
    'git_commit',
    'git_push',
    'deploy_application',
}


def filter_tools_for_user(tools: List[Dict], user_role: str) -> List[Dict]:
    """
    Filter available tools based on user role.

    Args:
        tools: Full list of available tools (list of dicts with 'name', 'description', etc.)
        user_role: User role ('master' or 'api_user')

    Returns:
        Filtered list of tools based on role

    Example:
        >>> all_tools = [
        ...     {'name': 'read_file', 'description': '...'},
        ...     {'name': 'write_file', 'description': '...'}
        ... ]
        >>> filtered = filter_tools_for_user(all_tools, 'api_user')
        >>> len(filtered)
        1
        >>> filtered[0]['name']
        'read_file'
    """
    if user_role == 'master':
        # Master has access to everything
        logger.debug(f"Master role: Allowing all {len(tools)} tools")
        return tools

    # API users get only allowed tools
    filtered = []
    for tool in tools:
        tool_name = tool.get('name', '')
        if tool_name in API_USER_ALLOWED_TOOLS:
            filtered.append(tool)
        else:
            logger.debug(f"Blocked tool '{tool_name}' for API user")

    logger.info(f"API user role: Filtered to {len(filtered)} allowed tools (from {len(tools)} total)")
    return filtered


def is_tool_allowed(tool_name: str, user_role: str) -> bool:
    """
    Check if a specific tool is allowed for a user role.

    This is used at runtime to verify tool execution attempts.

    Args:
        tool_name: Name of the tool to check
        user_role: User role ('master' or 'api_user')

    Returns:
        True if allowed, False otherwise

    Example:
        >>> is_tool_allowed('read_file', 'api_user')
        True
        >>> is_tool_allowed('write_file', 'api_user')
        False
        >>> is_tool_allowed('write_file', 'master')
        True
    """
    if user_role == 'master':
        return True

    return tool_name in API_USER_ALLOWED_TOOLS


def get_allowed_tools() -> Set[str]:
    """
    Get the set of tools allowed for API users.

    Returns:
        Set of tool names allowed for API users
    """
    return API_USER_ALLOWED_TOOLS.copy()


def get_blocked_tools() -> Set[str]:
    """
    Get the set of tools blocked for API users.

    Returns:
        Set of tool names blocked for API users
    """
    return API_USER_BLOCKED_TOOLS.copy()


def get_tool_access_summary() -> Dict[str, List[str]]:
    """
    Get a summary of tool access control.

    Returns:
        Dict with 'allowed' and 'blocked' lists
    """
    return {
        'allowed': sorted(list(API_USER_ALLOWED_TOOLS)),
        'blocked': sorted(list(API_USER_BLOCKED_TOOLS))
    }
