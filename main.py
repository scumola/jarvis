#!/usr/bin/env python3
"""
Jarvis - Local Voice-Driven Agent

Main entry point for the system.
"""

import os
import sys
import yaml
import logging
import atexit
from pathlib import Path

# Import readline for command history (up/down arrows)
try:
    import readline
    READLINE_AVAILABLE = True
except ImportError:
    READLINE_AVAILABLE = False

from orchestrator import Orchestrator


def setup_history():
    """Setup command history with readline for up/down arrow support."""
    if not READLINE_AVAILABLE:
        return

    # History file location
    history_file = Path.home() / ".jarvis_history"

    # Load existing history
    if history_file.exists():
        try:
            readline.read_history_file(str(history_file))
        except Exception as e:
            logging.warning(f"Could not load history: {e}")

    # Set history length
    readline.set_history_length(1000)

    # Save history on exit
    def save_history():
        try:
            readline.write_history_file(str(history_file))
        except Exception as e:
            logging.error(f"Could not save history: {e}")

    atexit.register(save_history)


def setup_logging(config: dict):
    """Configure logging for the application."""
    log_config = config.get('logging', {})
    log_level = getattr(logging, log_config.get('level', 'INFO'))
    log_path = log_config.get('path', 'logs/jarvis.log')

    # Create logs directory if needed
    Path(log_path).parent.mkdir(parents=True, exist_ok=True)

    # Configure logging
    handlers = []

    # File handler
    file_handler = logging.FileHandler(log_path)
    file_handler.setLevel(log_level)
    handlers.append(file_handler)

    # Console handler
    if log_config.get('console', True):
        console_handler = logging.StreamHandler()
        console_handler.setLevel(log_level)
        handlers.append(console_handler)

    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=handlers
    )


def load_config(config_path: str = 'config/config.yaml') -> dict:
    """Load configuration from YAML file."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def text_interface(orchestrator: Orchestrator):
    """
    Simple text-based interface for testing.
    Later, this will be replaced with voice I/O.
    """
    # Setup command history (up/down arrows)
    setup_history()

    # CLI uses steve user (ID 3) for master access
    # Note: ID 1 is system user (for old memories), ID 2 is alice (API test user)
    CLI_USER_ID = 3

    print("="*60)
    print("JARVIS - Local Voice-Driven Agent")
    print("="*60)
    print("Text interface active (voice I/O coming soon)")
    if READLINE_AVAILABLE:
        print("Command history enabled (use ↑/↓ arrows)")
    print("Commands:")
    print("  /reset  - Reset conversation history")
    print("  /quit   - Exit")
    print("="*60)
    print()

    while True:
        try:
            # Get user input
            user_input = input("\n\033[1;34mYou:\033[0m ").strip()

            if not user_input:
                continue

            # Handle commands
            if user_input == '/quit':
                print("Goodbye!")
                break
            elif user_input == '/reset':
                orchestrator.reset_conversation()
                print("Conversation reset.")
                continue

            # Process through orchestrator (CLI uses system user ID 1)
            result = orchestrator.process_user_input(user_input, user_id=CLI_USER_ID)

            # Display response
            print(f"\n\033[1;32mJarvis:\033[0m {result['response']}")

            # Show any actions taken (for debugging)
            if result.get('actions_taken'):
                print(f"\n\033[1;33m[Actions executed: {len(result['actions_taken'])}]\033[0m")

            # Show verification info if available
            verification = result.get('verification')
            if verification:
                verified = verification.get('verified', False)
                confidence = verification.get('confidence', 'unknown')
                if verified:
                    print(f"\033[1;32m✓ Verified ({confidence} confidence)\033[0m")
                else:
                    print(f"\033[1;31m✗ Verification failed ({confidence} confidence)\033[0m")
                    if verification.get('max_retries_reached'):
                        print(f"\033[1;31m  (Max retries reached)\033[0m")

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as e:
            logging.error(f"Error in main loop: {e}", exc_info=True)
            print(f"\n\033[1;31mError: {e}\033[0m")


def main():
    """Main entry point."""
    # Load configuration
    config = load_config()

    # Setup logging
    setup_logging(config)

    logger = logging.getLogger(__name__)
    logger.info("Starting Jarvis...")

    # Create orchestrator
    orchestrator = Orchestrator(config)

    # Start text interface
    try:
        text_interface(orchestrator)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == '__main__':
    main()
