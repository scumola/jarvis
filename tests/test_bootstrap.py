#!/usr/bin/env python3
"""
Quick test to verify the bootstrap system works.
"""

import sys
import yaml
import logging

# Add project root to path
sys.path.insert(0, '.')

from orchestrator import Orchestrator

def test_bootstrap():
    """Test basic orchestrator functionality."""
    print("Testing Jarvis Bootstrap System...")
    print("=" * 60)

    # Load config
    with open('config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    # Setup minimal logging
    logging.basicConfig(level=logging.INFO)

    # Create orchestrator
    print("\n1. Creating orchestrator...")
    orchestrator = Orchestrator(config)
    print("   ✓ Orchestrator created")

    # Check tools are registered
    print("\n2. Checking tool registry...")
    tools = orchestrator.tool_registry.list_tools()
    print(f"   ✓ {len(tools)} tools registered:")
    for tool in tools:
        print(f"     - {tool.name}: {tool.description}")

    # Test LLM connection
    print("\n3. Testing LLM connection...")
    try:
        import requests
        response = requests.get(
            f"http://{config['ollama']['host']}:{config['ollama']['port']}/api/tags",
            timeout=5
        )
        if response.status_code == 200:
            models = response.json().get('models', [])
            model_names = [m['name'] for m in models]
            print(f"   ✓ Connected to Ollama")
            print(f"   ✓ Available models: {', '.join(model_names)}")

            # Check if our model is available
            expected_model = config['ollama']['model']
            if any(expected_model in name for name in model_names):
                print(f"   ✓ Model '{expected_model}' is available")
            else:
                print(f"   ⚠ Warning: Model '{expected_model}' not found")
                print(f"     Available: {model_names}")
        else:
            print(f"   ✗ Failed to connect to Ollama (status {response.status_code})")
    except Exception as e:
        print(f"   ✗ Error connecting to Ollama: {e}")

    print("\n" + "=" * 60)
    print("Bootstrap test complete!")
    print("\nTo run Jarvis interactively:")
    print("  ./venv/bin/python main.py")
    print()

if __name__ == '__main__':
    test_bootstrap()
