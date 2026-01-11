"""
Model Specifications Registry

Hard-coded context window sizes for supported LLM models.
Automatically determines the correct token limit based on model name.

Sources:
- Llama 3.1: https://ai.meta.com/blog/meta-llama-3-1/ (128K tokens)
- Qwen 2.5/3: https://qwenlm.github.io/blog/qwen2.5-1m/ (128K-1M tokens)
"""

import re
import logging
from typing import Optional

logger = logging.getLogger(__name__)


# Model specifications: model_name_pattern -> context_window_size (in tokens)
MODEL_SPECS = {
    # Llama Models
    # Llama 3.1 and 3.2: 128K tokens (all sizes)
    r"llama3\.1.*": 128_000,
    r"llama3\.2.*": 128_000,
    r"llama-3\.1.*": 128_000,
    r"llama-3\.2.*": 128_000,

    # Llama 3.0 (earlier): 8K tokens
    r"llama3:.*": 8_000,
    r"llama-3:.*": 8_000,

    # Qwen Models
    # Qwen 2.5-1M: 1M tokens (7B, 14B)
    r"qwen2\.5.*1m.*": 1_000_000,
    r"qwen2\.5.*-1m.*": 1_000_000,

    # Qwen 2.5 standard: 128K tokens
    r"qwen2\.5.*": 128_000,
    r"qwen-2\.5.*": 128_000,

    # Qwen3 standard: 262K tokens (native), extendable to 1M
    # Using 262K as the safe default for standard Qwen3 models
    r"qwen3.*": 262_000,
    r"qwen-3.*": 262_000,

    # Qwen2 (older): 32K tokens
    r"qwen2:.*": 32_000,
    r"qwen:.*": 32_000,
}

# Default fallback for unknown models (conservative estimate)
DEFAULT_CONTEXT_WINDOW = 8_000


def get_context_window(model_name: str) -> int:
    """
    Get the context window size for a given model name.

    Supports Ollama-style model names (e.g., "llama3.1:8b", "qwen3:14b")
    and standard model names (e.g., "llama-3.1-8b-instruct").

    Args:
        model_name: Name of the model (case-insensitive)

    Returns:
        Context window size in tokens

    Examples:
        >>> get_context_window("llama3.1:8b")
        128000
        >>> get_context_window("qwen3:8b")
        262000
        >>> get_context_window("qwen2.5-14b-instruct-1m")
        1000000
        >>> get_context_window("unknown-model")
        8000  # Default fallback
    """
    model_lower = model_name.lower()

    # Try to match against known patterns
    for pattern, context_size in MODEL_SPECS.items():
        if re.search(pattern, model_lower):
            logger.info(
                f"Model '{model_name}' matched pattern '{pattern}': "
                f"{context_size:,} token context window"
            )
            return context_size

    # No match found - use default
    logger.warning(
        f"Unknown model '{model_name}'. Using default context window: "
        f"{DEFAULT_CONTEXT_WINDOW:,} tokens. "
        f"Consider adding this model to MODEL_SPECS in memory/model_specs.py"
    )
    return DEFAULT_CONTEXT_WINDOW


def get_recommended_memory_budget(model_name: str) -> dict:
    """
    Get recommended memory budget settings for a given model.

    Returns optimal values for:
    - max_total_tokens: Total context window
    - memory_budget_percentage: % of context to reserve for memories
    - hard_cap_memories: Maximum number of memories to retrieve

    Args:
        model_name: Name of the model

    Returns:
        Dict with recommended budget configuration

    Logic:
    - Small context (<=8K): 15% for memories, cap at 10
    - Medium context (<=128K): 10% for memories, cap at 20
    - Large context (>128K): 5% for memories, cap at 30
    """
    context_window = get_context_window(model_name)

    if context_window <= 8_000:
        # Small context: conservative memory allocation
        return {
            'max_total_tokens': context_window,
            'memory_budget_percentage': 0.15,  # 15%
            'hard_cap_memories': 10,
            'avg_memory_tokens': 50,
        }
    elif context_window <= 128_000:
        # Medium context: balanced allocation
        return {
            'max_total_tokens': context_window,
            'memory_budget_percentage': 0.10,  # 10%
            'hard_cap_memories': 20,
            'avg_memory_tokens': 50,
        }
    else:
        # Large context (262K-1M): generous allocation
        return {
            'max_total_tokens': context_window,
            'memory_budget_percentage': 0.05,  # 5%
            'hard_cap_memories': 30,
            'avg_memory_tokens': 50,
        }


def get_model_info(model_name: str) -> dict:
    """
    Get comprehensive information about a model.

    Args:
        model_name: Name of the model

    Returns:
        Dict with model information
    """
    context_window = get_context_window(model_name)
    budget_config = get_recommended_memory_budget(model_name)

    return {
        'model_name': model_name,
        'context_window': context_window,
        'context_window_formatted': f"{context_window:,} tokens",
        'recommended_budget': budget_config,
        'memory_budget_tokens': int(context_window * budget_config['memory_budget_percentage']),
    }


if __name__ == "__main__":
    # Test cases
    test_models = [
        "llama3.1:8b",
        "llama3.1:70b",
        "llama3.2:11b",
        "qwen3:8b",
        "qwen3:14b",
        "qwen2.5-14b-instruct-1m",
        "qwen2.5:7b",
        "llama3:8b",  # older version
        "unknown-model:42b",
    ]

    print("Model Context Window Tests:")
    print("=" * 80)
    for model in test_models:
        info = get_model_info(model)
        print(f"\n{model}:")
        print(f"  Context Window: {info['context_window_formatted']}")
        print(f"  Memory Budget: {info['memory_budget_tokens']:,} tokens "
              f"({info['recommended_budget']['memory_budget_percentage']*100:.0f}%)")
        print(f"  Max Memories: {info['recommended_budget']['hard_cap_memories']}")
