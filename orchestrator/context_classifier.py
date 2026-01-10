"""
Context Classifier

Classifies user queries into procedural memory context types.
Uses simple keyword matching for deterministic, fast classification.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# Context type keywords
CONTEXT_KEYWORDS = {
    'filesystem': [
        'file', 'directory', 'folder', 'path', 'read', 'write', 'edit',
        'list', 'find', 'search', 'create', 'delete', 'move', 'copy',
        'readme', 'license', 'changelog', 'config', 'backup', '.txt',
        '.md', '.py', '.json', '.yaml', '.log'
    ],
    'web_retrieval': [
        'search', 'web', 'url', 'http', 'fetch', 'download', 'api',
        'request', 'website', 'page', 'scrape', 'crawl', 'wikipedia',
        'google', 'internet', 'online', 'browse'
    ],
    'tool_execution': [
        'run', 'execute', 'command', 'shell', 'bash', 'script', 'tool',
        'process', 'service', 'daemon', 'binary', 'program'
    ],
    'code_generation': [
        'write code', 'generate code', 'implement', 'function',
        'class', 'method', 'algorithm', 'program', 'script',
        'refactor', 'fix bug', 'debug'
    ],
    'data_processing': [
        'parse', 'analyze', 'process', 'transform', 'filter',
        'sort', 'aggregate', 'count', 'calculate', 'compute',
        'extract', 'data', 'csv', 'json', 'xml', 'database'
    ]
}


def classify_context(query: str) -> str:
    """
    Classify a query into a procedural memory context type.

    Uses keyword matching - fast, deterministic, no LLM needed.

    Args:
        query: User query string

    Returns:
        Context type string ('filesystem', 'web_retrieval', etc.)
        Returns 'general' if no specific match
    """
    query_lower = query.lower()

    # Count matches for each context type
    scores = {}
    for context_type, keywords in CONTEXT_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in query_lower)
        if score > 0:
            scores[context_type] = score

    if not scores:
        logger.debug(f"No context match for query, using 'general'")
        return 'general'

    # Return context with highest score
    best_context = max(scores.items(), key=lambda x: x[1])
    logger.debug(
        f"Classified query as '{best_context[0]}' "
        f"(score: {best_context[1]})"
    )

    return best_context[0]


def get_context_description(context_type: str) -> str:
    """Get human-readable description of context type."""
    descriptions = {
        'filesystem': "File and directory operations",
        'web_retrieval': "Web search and data fetching",
        'tool_execution': "Running commands and programs",
        'code_generation': "Writing or modifying code",
        'data_processing': "Parsing and analyzing data",
        'general': "General tasks"
    }
    return descriptions.get(context_type, "Unknown context")
