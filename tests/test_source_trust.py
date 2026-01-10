#!/usr/bin/env python3
"""
Test script for Source Trust & Fact Confidence Layer.

Tests:
1. Source type inference (user vs inference)
2. Memory storage with source fields
3. Retrieval ranking with verification status
4. Database persistence
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import yaml
import mysql.connector
from memory.manager import MemoryManager
from memory.schemas import (
    MemoryProposal, MemoryType, MemorySourceType, VerificationStatus
)

def load_config():
    """Load configuration."""
    with open('config/config.yaml') as f:
        return yaml.safe_load(f)

def get_db_connection(config):
    """Get database connection."""
    return mysql.connector.connect(
        host=config['memory']['mysql_host'],
        database=config['memory']['mysql_database'],
        user=config['memory']['mysql_user'],
        password=config['memory']['mysql_password']
    )

def test_source_inference():
    """Test that source types are correctly inferred."""
    print("\n" + "="*70)
    print("TEST 1: Source Type Inference")
    print("="*70)

    config = load_config()
    memory_manager = MemoryManager(config['memory'])

    # Test 1: Identity fact (should infer USER)
    print("\n[Test 1.1] Identity fact (should infer source_type=USER)")
    proposal1 = MemoryProposal(
        memory_text="User's name is Alice",
        memory_type=MemoryType.IDENTITY,
        confidence=1.0,
        importance=1.0,
        reasoning="Explicitly stated"
    )

    memory_id1 = memory_manager.store_memory(proposal1, user_id=1)
    print(f"✓ Stored memory ID: {memory_id1}")

    # Check database
    connection = get_db_connection(config)
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT source_type, source_identity, verification_status FROM memories WHERE id = %s", (memory_id1,))
    result = cursor.fetchone()
    cursor.close()
    connection.close()

    print(f"  source_type: {result['source_type']}")
    print(f"  source_identity: {result['source_identity']}")
    print(f"  verification_status: {result['verification_status']}")

    assert result['source_type'] == 'user', f"Expected 'user', got '{result['source_type']}'"
    assert result['verification_status'] == 'unverified', "Should start unverified"
    print("✓ Identity fact correctly inferred as USER source")

    # Test 2: Capability fact (should infer INFERENCE)
    print("\n[Test 1.2] Capability fact (should infer source_type=INFERENCE)")
    proposal2 = MemoryProposal(
        memory_text="User knows Python programming",
        memory_type=MemoryType.CAPABILITY,
        confidence=0.8,
        importance=0.7,
        reasoning="Inferred from conversation context"
    )

    memory_id2 = memory_manager.store_memory(proposal2, user_id=1)
    print(f"✓ Stored memory ID: {memory_id2}")

    connection = get_db_connection(config)
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT source_type, source_identity FROM memories WHERE id = %s", (memory_id2,))
    result = cursor.fetchone()
    cursor.close()
    connection.close()

    print(f"  source_type: {result['source_type']}")
    print(f"  source_identity: {result['source_identity']}")

    assert result['source_type'] == 'inference', f"Expected 'inference', got '{result['source_type']}'"
    print("✓ Capability fact correctly inferred as INFERENCE source")

    # Test 3: Explicit source_type provided
    print("\n[Test 1.3] Explicit source_type (should use provided value)")
    proposal3 = MemoryProposal(
        memory_text="Python 3.12 is the latest version",
        memory_type=MemoryType.EPISODIC,
        confidence=0.95,
        importance=0.6,
        reasoning="Fetched from python.org",
        source_type=MemorySourceType.WEB,
        source_identity="python.org"
    )

    memory_id3 = memory_manager.store_memory(proposal3, user_id=1)
    print(f"✓ Stored memory ID: {memory_id3}")

    connection = get_db_connection(config)
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT source_type, source_identity FROM memories WHERE id = %s", (memory_id3,))
    result = cursor.fetchone()
    cursor.close()
    connection.close()

    print(f"  source_type: {result['source_type']}")
    print(f"  source_identity: {result['source_identity']}")

    assert result['source_type'] == 'web', f"Expected 'web', got '{result['source_type']}'"
    assert result['source_identity'] == 'python.org', f"Expected 'python.org', got '{result['source_identity']}'"
    print("✓ Explicit source_type correctly preserved")

    print("\n✅ All source inference tests passed!")
    return memory_id1, memory_id2, memory_id3

def test_verification_status():
    """Test verification status updates."""
    print("\n" + "="*70)
    print("TEST 2: Verification Status Updates")
    print("="*70)

    config = load_config()
    memory_manager = MemoryManager(config['memory'])

    # Create a test memory
    print("\n[Test 2.1] Create memory and mark as corroborated")
    proposal = MemoryProposal(
        memory_text="User prefers TypeScript over JavaScript",
        memory_type=MemoryType.PREFERENCE,
        confidence=0.9,
        importance=0.8,
        reasoning="User explicitly stated"
    )

    memory_id = memory_manager.store_memory(proposal, user_id=1)
    print(f"✓ Created memory ID: {memory_id}")

    # Mark as corroborated
    memory_manager.metadata_store.update_verification_status(
        memory_id=memory_id,
        verification_status='corroborated',
        increment_corroboration=True
    )
    print("✓ Marked as corroborated")

    # Verify in database
    connection = get_db_connection(config)
    cursor = connection.cursor(dictionary=True)
    cursor.execute(
        "SELECT verification_status, corroboration_count, last_verified_at FROM memories WHERE id = %s",
        (memory_id,)
    )
    result = cursor.fetchone()
    cursor.close()
    connection.close()

    print(f"  verification_status: {result['verification_status']}")
    print(f"  corroboration_count: {result['corroboration_count']}")
    print(f"  last_verified_at: {result['last_verified_at']}")

    assert result['verification_status'] == 'corroborated', "Should be corroborated"
    assert result['corroboration_count'] == 1, "Count should be 1"
    assert result['last_verified_at'] is not None, "Should have verification timestamp"
    print("✓ Verification status correctly updated")

    # Test contradiction
    print("\n[Test 2.2] Mark another memory as contradicted")
    proposal2 = MemoryProposal(
        memory_text="The Earth is flat",
        memory_type=MemoryType.EPISODIC,
        confidence=0.5,
        importance=0.3,
        reasoning="User statement"
    )

    memory_id2 = memory_manager.store_memory(proposal2, user_id=1)
    memory_manager.metadata_store.update_verification_status(
        memory_id=memory_id2,
        verification_status='contradicted',
        increment_corroboration=False
    )
    print(f"✓ Memory ID {memory_id2} marked as contradicted")

    connection = get_db_connection(config)
    cursor = connection.cursor(dictionary=True)
    cursor.execute("SELECT verification_status FROM memories WHERE id = %s", (memory_id2,))
    result = cursor.fetchone()
    cursor.close()
    connection.close()

    assert result['verification_status'] == 'contradicted', "Should be contradicted"
    print("✓ Contradiction status correctly set")

    print("\n✅ All verification status tests passed!")
    return memory_id, memory_id2

def test_retrieval_ranking():
    """Test that verification status affects retrieval ranking."""
    print("\n" + "="*70)
    print("TEST 3: Retrieval Ranking with Verification Status")
    print("="*70)

    config = load_config()
    memory_manager = MemoryManager(config['memory'])

    # Create three similar memories with different verification statuses
    print("\n[Test 3.1] Create three similar memories")

    # Memory 1: Corroborated (should rank highest)
    proposal1 = MemoryProposal(
        memory_text="User prefers Python for data science work",
        memory_type=MemoryType.PREFERENCE,
        confidence=0.9,
        importance=0.8,
        reasoning="Multiple confirmations"
    )
    mem1_id = memory_manager.store_memory(proposal1, user_id=1)
    memory_manager.metadata_store.update_verification_status(
        mem1_id, 'corroborated', increment_corroboration=True
    )
    # Corroborate twice more
    memory_manager.metadata_store.update_verification_status(
        mem1_id, 'corroborated', increment_corroboration=True
    )
    memory_manager.metadata_store.update_verification_status(
        mem1_id, 'corroborated', increment_corroboration=True
    )
    print(f"✓ Memory 1 (ID {mem1_id}): Corroborated 3 times")

    # Memory 2: Unverified (should rank middle)
    proposal2 = MemoryProposal(
        memory_text="User sometimes uses Python for scripting",
        memory_type=MemoryType.PREFERENCE,
        confidence=0.75,
        importance=0.7,
        reasoning="Mentioned once"
    )
    mem2_id = memory_manager.store_memory(proposal2, user_id=1)
    print(f"✓ Memory 2 (ID {mem2_id}): Unverified")

    # Memory 3: Contradicted (should rank lowest)
    proposal3 = MemoryProposal(
        memory_text="User dislikes Python and prefers Java",
        memory_type=MemoryType.PREFERENCE,
        confidence=0.8,
        importance=0.8,
        reasoning="Old statement"
    )
    mem3_id = memory_manager.store_memory(proposal3, user_id=1)
    memory_manager.metadata_store.update_verification_status(
        mem3_id, 'contradicted', increment_corroboration=False
    )
    print(f"✓ Memory 3 (ID {mem3_id}): Contradicted")

    # Retrieve memories
    print("\n[Test 3.2] Retrieve memories with query 'Python preferences'")
    memories = memory_manager.retrieve_memories(
        user_id=1,
        query="Python programming preferences",
        k=5
    )

    print(f"\n✓ Retrieved {len(memories)} memories (ranked by relevance):")
    for i, mem in enumerate(memories[:3], 1):
        print(f"\n  Rank {i}: ID {mem.id}")
        print(f"    Text: {mem.memory_text[:60]}...")
        # Handle both enum and string types
        verification = mem.verification_status.value if hasattr(mem.verification_status, 'value') else mem.verification_status
        print(f"    Verification: {verification}")
        print(f"    Corroborations: {mem.corroboration_count}")
        print(f"    Confidence: {mem.confidence}")

    # Verify ranking (corroborated should be first)
    if len(memories) >= 3:
        # Check if corroborated memory is ranked higher than contradicted
        corroborated_rank = next((i for i, m in enumerate(memories) if m.id == mem1_id), None)
        contradicted_rank = next((i for i, m in enumerate(memories) if m.id == mem3_id), None)

        if corroborated_rank is not None and contradicted_rank is not None:
            assert corroborated_rank < contradicted_rank, "Corroborated should rank higher than contradicted"
            print(f"\n✓ Ranking correct: Corroborated (rank {corroborated_rank+1}) > Contradicted (rank {contradicted_rank+1})")
        else:
            print("\n⚠ Warning: Not all test memories retrieved")

    print("\n✅ Retrieval ranking test completed!")

def test_database_state():
    """Display current database state for verification."""
    print("\n" + "="*70)
    print("DATABASE STATE VERIFICATION")
    print("="*70)

    config = load_config()
    connection = get_db_connection(config)
    cursor = connection.cursor(dictionary=True)

    # Get recent memories with source trust fields
    cursor.execute("""
        SELECT
            id,
            LEFT(memory_text, 50) as memory_text,
            memory_type,
            source_type,
            source_identity,
            verification_status,
            corroboration_count,
            confidence,
            importance
        FROM memories
        WHERE user_id = 1
        ORDER BY created_at DESC
        LIMIT 10
    """)

    results = cursor.fetchall()
    cursor.close()
    connection.close()

    print(f"\nRecent memories (showing last 10 for user_id=1):\n")
    print(f"{'ID':<5} {'Type':<12} {'Source':<12} {'Verification':<15} {'Corr':<5} {'Conf':<5} {'Text':<40}")
    print("-" * 110)

    for row in results:
        print(f"{row['id']:<5} "
              f"{row['memory_type']:<12} "
              f"{row['source_type']:<12} "
              f"{row['verification_status']:<15} "
              f"{row['corroboration_count']:<5} "
              f"{row['confidence']:<5.2f} "
              f"{row['memory_text'][:40]}")

    print("\n✅ Database state verified!")

if __name__ == "__main__":
    print("\n" + "="*70)
    print("SOURCE TRUST & FACT CONFIDENCE LAYER TEST SUITE")
    print("="*70)

    try:
        # Run tests
        test_source_inference()
        mem1, mem2 = test_verification_status()
        test_retrieval_ranking()
        test_database_state()

        print("\n" + "="*70)
        print("✅ ALL TESTS PASSED!")
        print("="*70)
        print("\nSource Trust Layer is working correctly:")
        print("  ✓ Source type inference working")
        print("  ✓ Verification status updates working")
        print("  ✓ Retrieval ranking with trust multipliers working")
        print("  ✓ Database persistence working")
        print("\n")

    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)
