"""
Memory System Package

Provides long-term memory with RAG (Retrieval-Augmented Generation)
using ChromaDB for vector embeddings and MySQL for structured metadata.
"""

from .manager import MemoryManager
from .consolidation import MemoryConsolidator, auto_consolidate
from .import_export import MemoryExporter, MemoryImporter
from .schemas import (
    Memory,
    MemoryProposal,
    MemoryType,
    MemoryStatus,
    MemoryContext,
    MemoryCreatedBy,
    RelationshipType,
    AuditOperation
)

__all__ = [
    'MemoryManager',
    'MemoryConsolidator',
    'auto_consolidate',
    'MemoryExporter',
    'MemoryImporter',
    'Memory',
    'MemoryProposal',
    'MemoryType',
    'MemoryStatus',
    'MemoryContext',
    'MemoryCreatedBy',
    'RelationshipType',
    'AuditOperation'
]
