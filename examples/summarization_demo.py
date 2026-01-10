#!/usr/bin/env python3
"""
Conversation Summarization Demo

Demonstrates automatic conversation summarization that prevents token limit issues
while preserving context and enabling long-running conversations.
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import yaml
from orchestrator import Orchestrator


def simulate_long_conversation(orchestrator: Orchestrator):
    """Simulate a long conversation that triggers summarization."""

    print("\n" + "="*70)
    print("SIMULATING LONG CONVERSATION")
    print("="*70)
    print("\nThis demo simulates a lengthy conversation to trigger automatic")
    print("summarization. Watch for the summarization trigger message!")
    print("="*70)

    # User ID for testing (Steve - master user)
    user_id = 3

    # Simulate a series of interactions that will accumulate context
    interactions = [
        "Hello! I'm working on a Python project called SuperCalculator.",
        "The project is located at /home/steve/projects/supercalc.",
        "I need to add a feature for complex number arithmetic.",
        "Can you help me understand how Python handles complex numbers?",
        "Great! Now I want to add matrix operations too.",
        "What libraries would you recommend for matrix math?",
        "I think I'll use NumPy. Can you explain how to install it?",
        "Perfect! Now I need to create a configuration file for the app.",
        "The config should be in YAML format with settings for precision.",
        "I also want to add logging to track all calculations.",
        "The log format should include timestamps and operation types.",
        "Can you suggest a good directory structure for this project?",
        "I'm thinking about adding a GUI using tkinter.",
        "What are the pros and cons of tkinter vs PyQt?",
        "Let's go with tkinter for simplicity. How do I start?",
        "I need the GUI to have a calculator-style button layout.",
        "Also need a display area for showing calculation results.",
        "Can we add keyboard shortcuts for common operations?",
        "I want to support both light and dark themes.",
        "How do I implement theme switching in tkinter?",
    ]

    print(f"\nStarting conversation with {len(interactions)} interactions...")
    print("(Summarization typically triggers around interaction 12-15)\n")

    for i, message in enumerate(interactions, 1):
        print(f"\n{'─'*70}")
        print(f"[Interaction {i}/{len(interactions)}]")
        print(f"User: {message}")
        print(f"{'─'*70}")

        # Process the message
        result = orchestrator.process_user_input(message, user_id=user_id)

        # Show abbreviated response
        response = result['response']
        if len(response) > 200:
            response = response[:200] + "..."
        print(f"Jarvis: {response}")

        # Check if summarization happened (visible in logs or persona state)
        if orchestrator.persona_llm.conversation_summary:
            print("\n🔄 SUMMARIZATION TRIGGERED!")
            print(f"   History size: {len(orchestrator.persona_llm.conversation_history)} messages")
            print(f"   Summary length: {len(orchestrator.persona_llm.conversation_summary)} chars")
            print("\nSummary preview:")
            print("─" * 70)
            summary_preview = orchestrator.persona_llm.conversation_summary[:400]
            if len(orchestrator.persona_llm.conversation_summary) > 400:
                summary_preview += "\n... [truncated for display]"
            print(summary_preview)
            print("─" * 70)
            print("\nContinuing conversation with condensed history...\n")

        # Small delay for readability
        import time
        time.sleep(0.5)

    print("\n" + "="*70)
    print("CONVERSATION COMPLETE")
    print("="*70)

    # Final state
    print(f"\nFinal conversation state:")
    print(f"  • Summary exists: {orchestrator.persona_llm.conversation_summary is not None}")
    print(f"  • History size: {len(orchestrator.persona_llm.conversation_history)} messages")

    if orchestrator.persona_llm.conversation_summary:
        print(f"  • Summary length: {len(orchestrator.persona_llm.conversation_summary)} chars")
        print("\n📄 Full Summary:")
        print("="*70)
        print(orchestrator.persona_llm.conversation_summary)
        print("="*70)

    # Test that context is preserved
    print("\n" + "="*70)
    print("TESTING CONTEXT PRESERVATION")
    print("="*70)
    print("\nAsking about earlier conversation topics to verify context is preserved...")

    test_questions = [
        "What was the name of my Python project?",
        "What library did I decide to use for matrix math?",
        "What GUI framework did we choose?"
    ]

    for question in test_questions:
        print(f"\n❓ User: {question}")
        result = orchestrator.process_user_input(question, user_id=user_id)
        print(f"✅ Jarvis: {result['response']}")


def show_configuration():
    """Display current summarization configuration."""
    print("\n" + "="*70)
    print("CURRENT SUMMARIZATION CONFIGURATION")
    print("="*70)

    with open('config/config.yaml') as f:
        config = yaml.safe_load(f)

    summ_config = config.get('summarization', {})

    print(f"\nEnabled: {summ_config.get('enabled', True)}")
    print(f"Max Tokens: {summ_config.get('max_tokens', 8000)}")
    print(f"Trigger Threshold: {summ_config.get('trigger_threshold', 0.7) * 100:.0f}% of max")
    print(f"Preserve Recent: {summ_config.get('preserve_recent', 6)} messages")

    print("\nHow it works:")
    print("  1. System estimates conversation token count (~4 chars per token)")
    print(f"  2. At {summ_config.get('trigger_threshold', 0.7) * 100:.0f}% of {summ_config.get('max_tokens', 8000)} tokens, summarization triggers")
    print(f"  3. Older messages are condensed into a summary")
    print(f"  4. Last {summ_config.get('preserve_recent', 6)} messages remain intact")
    print("  5. Future responses use: summary + recent messages")
    print("\nBenefits:")
    print("  ✓ Prevents context window overflow")
    print("  ✓ Enables indefinitely long conversations")
    print("  ✓ Preserves critical context and decisions")
    print("  ✓ Reduces token usage for long sessions")


def main():
    print("\n" + "="*70)
    print("CONVERSATION SUMMARIZATION DEMO")
    print("="*70)
    print("\nThis demo shows how Jarvis automatically manages long conversations")
    print("through intelligent summarization.")
    print("="*70)

    # Show configuration
    show_configuration()

    # Load config
    with open('config/config.yaml') as f:
        config = yaml.safe_load(f)

    # Verify summarization is enabled
    if not config.get('summarization', {}).get('enabled', True):
        print("\n⚠️  WARNING: Summarization is disabled in config!")
        print("Enable it in config/config.yaml to see this demo work.")
        return

    # Initialize orchestrator
    print("\nInitializing Jarvis with summarization support...")
    orchestrator = Orchestrator(config)

    # Get user confirmation
    print("\n" + "="*70)
    response = input("\nRun long conversation simulation? (yes/no) [yes]: ").strip().lower()

    if response in ['n', 'no']:
        print("\nDemo cancelled.")
        return

    # Run simulation
    simulate_long_conversation(orchestrator)

    print("\n" + "="*70)
    print("DEMO COMPLETE")
    print("="*70)
    print("\nKey Takeaways:")
    print("  ✅ Jarvis automatically detects when conversations get too long")
    print("  ✅ Older messages are intelligently summarized")
    print("  ✅ Recent messages stay intact for immediate context")
    print("  ✅ Context is preserved across summarization boundary")
    print("  ✅ Users can have arbitrarily long conversations")
    print("\nJarvis can now handle extended sessions without context loss! 🎉")
    print()


if __name__ == "__main__":
    main()
