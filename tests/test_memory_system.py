#!/usr/bin/env python3
"""
Quick verification test for memory system integration.

Tests basic functionality without running full Jarvis.
"""

import sys
sys.path.insert(0, '.')

import yaml
from pathlib import Path

print("="*70)
print("Memory System Verification Test")
print("="*70)

# Test 1: Import modules
print("\n1. Testing module imports...")
try:
    from memory import MemoryManager, Memory, MemoryProposal, MemoryType
    from llm_roles import MemoryCuratorLLM
    print("  ✓ All memory modules imported successfully")
except ImportError as e:
    print(f"  ✗ Import error: {e}")
    sys.exit(1)

# Test 2: Load configuration
print("\n2. Loading configuration...")
try:
    with open('config/config.yaml', 'r') as f:
        config = yaml.safe_load(f)

    memory_config = config.get('memory', {})
    print(f"  ✓ Configuration loaded")
    print(f"    Memory enabled: {memory_config.get('enabled')}")
    print(f"    Vector DB path: {memory_config.get('vector_db_path')}")
    print(f"    MySQL host: {memory_config.get('mysql_host')}")
except Exception as e:
    print(f"  ✗ Config error: {e}")
    sys.exit(1)

# Test 3: Initialize Memory Manager
print("\n3. Initializing Memory Manager...")
try:
    memory_manager = MemoryManager(memory_config)
    print("  ✓ Memory Manager initialized")

    # Get statistics
    stats = memory_manager.get_statistics()
    print(f"    Total memories: {stats.get('total_memories', 0)}")
    print(f"    Vector store count: {stats.get('vector_store_count', 0)}")
except Exception as e:
    print(f"  ✗ Initialization error: {e}")
    sys.exit(1)

# Test 4: Test Memory Curator LLM
print("\n4. Testing Memory Curator LLM initialization...")
try:
    ollama_config = config.get('ollama', {})
    curator_llm = MemoryCuratorLLM(
        ollama_host=ollama_config.get('host', 'gpu'),
        ollama_port=ollama_config.get('port', 11434),
        model=ollama_config.get('model', 'qwen3:14b'),
        timeout=60
    )
    print("  ✓ Memory Curator LLM initialized")
except Exception as e:
    print(f"  ✗ Curator LLM error: {e}")
    sys.exit(1)

# Test 5: Test memory proposal
print("\n5. Creating test memory proposal...")
try:
    proposal = MemoryProposal(
        memory_text="Test memory: User's name is Steve",
        memory_type=MemoryType.IDENTITY,
        confidence=0.95,
        importance=0.9,
        reasoning="Test memory for verification"
    )
    print("  ✓ Memory proposal created successfully")
    print(f"    Text: {proposal.memory_text}")
    print(f"    Type: {proposal.memory_type}")
    print(f"    Confidence: {proposal.confidence}")
except Exception as e:
    print(f"  ✗ Proposal creation error: {e}")
    sys.exit(1)

# Test 6: Store and retrieve test memory
print("\n6. Testing memory storage and retrieval...")
try:
    # Store memory
    memory_id = memory_manager.store_memory(proposal)
    print(f"  ✓ Memory stored successfully (ID: {memory_id})")

    # Retrieve memories
    retrieved = memory_manager.retrieve_memories(
        query="What is the user's name?",
        k=5
    )
    print(f"  ✓ Retrieved {len(retrieved)} memories")

    if retrieved:
        print(f"    First memory: {retrieved[0].memory_text}")
        print(f"    Confidence: {retrieved[0].confidence}")
        print(f"    Decay score: {retrieved[0].decay_score}")
except Exception as e:
    print(f"  ✗ Storage/retrieval error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 7: Test ChromaDB collection
print("\n7. Verifying ChromaDB collection...")
try:
    vector_store = memory_manager.vector_store
    count = vector_store.count()
    print(f"  ✓ ChromaDB collection has {count} embeddings")
except Exception as e:
    print(f"  ✗ ChromaDB error: {e}")
    sys.exit(1)

print("\n" + "="*70)
print("✓ All verification tests passed!")
print("="*70)
print("\nMemory system is ready for use.")
print("You can now start Jarvis with: ./venv/bin/python main.py")
print("="*70)
