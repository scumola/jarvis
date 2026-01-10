#!/usr/bin/env python3
"""
Demo script to test Jarvis with example prompts.
"""

import sys
import yaml
import logging
from pathlib import Path

sys.path.insert(0, '.')

from orchestrator import Orchestrator


def setup_logging():
    """Setup minimal logging for demo."""
    logging.basicConfig(
        level=logging.WARNING,  # Quieter for demo
        format='%(levelname)s: %(message)s'
    )


def print_separator(title=None):
    """Print a nice separator."""
    if title:
        print(f"\n{'='*70}")
        print(f"  {title}")
        print('='*70)
    else:
        print('-'*70)


def run_prompt(orchestrator, prompt, prompt_num, total):
    """Run a single prompt and display results."""
    print_separator(f"Demo {prompt_num}/{total}")
    print(f"\n\033[1;34mPrompt:\033[0m {prompt}")
    print()

    try:
        result = orchestrator.process_user_input(prompt)

        print(f"\033[1;32mJarvis:\033[0m")
        print(result['response'])

        if result.get('actions_taken'):
            print(f"\n\033[1;33m[{len(result['actions_taken'])} action(s) executed]\033[0m")
            for action in result['actions_taken']:
                if action.get('success'):
                    print(f"  ✓ {action['tool_name']}")
                else:
                    print(f"  ✗ {action['tool_name']}: {action.get('error', 'Unknown error')}")

        print()

    except Exception as e:
        print(f"\033[1;31mError: {e}\033[0m\n")
        logging.error("Error processing prompt", exc_info=True)


def main():
    """Run the demo."""
    setup_logging()

    print("\n" + "="*70)
    print("  JARVIS DEMO - Testing Current Capabilities")
    print("="*70)
    print("\nInitializing Jarvis...")

    # Load config
    with open('config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    # Create orchestrator
    orchestrator = Orchestrator(config)
    print("✓ Jarvis initialized\n")

    # Demo prompts
    prompts = [
        "What files exist in the current directory?",
        "What tools do you currently have available?",
        "Read the DESIGN.md file and give me a brief summary of what your purpose is",
        "List all Python files in the tools directory",
        "Read the orchestrator/engine.py file and briefly explain what the orchestrator does",
    ]

    # Run each prompt
    for i, prompt in enumerate(prompts, 1):
        run_prompt(orchestrator, prompt, i, len(prompts))

        # Small pause between prompts for readability
        if i < len(prompts):
            input("\n\033[90m[Press Enter to continue to next demo...]\033[0m\n")

    print_separator("Demo Complete")
    print("\n\033[1;32m✓ All demos completed successfully!\033[0m")
    print("\nTo run Jarvis interactively:")
    print("  ./venv/bin/python main.py\n")


if __name__ == '__main__':
    main()
