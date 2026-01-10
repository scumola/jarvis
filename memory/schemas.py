"""
Pydantic schemas for the memory system.

Defines all data models used for memory storage, retrieval, and proposals.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class MemoryType(str, Enum):
    """Types of memories that can be stored."""
    IDENTITY = "identity"          # User facts: "My name is Steve"
    PREFERENCE = "preference"      # Likes/dislikes: "I prefer Python over Java"
    CAPABILITY = "capability"      # System abilities: "I can use find_files tool"
    PROJECT = "project"            # Current work: "Working on Jarvis memory system"
    EPISODIC = "episodic"          # Past events: "We discussed adding RAG on Jan 8"
    SOCIAL = "social"              # Communication style: "User prefers concise responses"


class MemoryStatus(str, Enum):
    """Status of a memory entry."""
    ACTIVE = "active"              # Currently active and retrievable
    ARCHIVED = "archived"          # Archived (decay_score < threshold)
    SUPERSEDED = "superseded"      # Replaced by a newer memory


class MemoryCreatedBy(str, Enum):
    """Source that created the memory."""
    CURATOR_LLM = "curator_llm"    # Created by Memory Curator LLM
    MANUAL = "manual"              # Manually created by user/admin
    SYSTEM = "system"              # Created by system processes


class MemorySourceType(str, Enum):
    """Type of source that provided this memory."""
    USER = "user"                  # Directly from user statement
    TOOL_OUTPUT = "tool_output"    # From tool execution result
    WEB = "web"                    # From web search or fetch
    INFERENCE = "inference"        # LLM inference/reasoning
    UNKNOWN = "unknown"            # Source not determined


class VerificationStatus(str, Enum):
    """Verification status of a memory fact."""
    UNVERIFIED = "unverified"      # Not yet verified
    CORROBORATED = "corroborated"  # Confirmed by multiple sources
    CONTRADICTED = "contradicted"  # Contradicted by other evidence
    DEPRECATED = "deprecated"      # Outdated or no longer relevant


class Memory(BaseModel):
    """
    Complete memory representation.

    Used for storing and retrieving memories from the database.
    """
    id: Optional[int] = None
    user_id: Optional[int] = Field(default=None, description="User ID who owns this memory (for multi-user isolation)")
    memory_text: str = Field(description="The actual memory content")
    memory_type: MemoryType = Field(description="Category of memory")
    embedding_id: str = Field(description="UUID for ChromaDB embedding")

    # Quality metrics
    confidence: float = Field(default=0.80, ge=0.0, le=1.0, description="LLM's confidence in this memory")
    importance: float = Field(default=0.50, ge=0.0, le=1.0, description="How critical this memory is")
    decay_score: float = Field(default=100.0, ge=0.0, le=100.0, description="Vitality score (decays over time)")

    # Source Trust & Provenance
    source_type: MemorySourceType = Field(default=MemorySourceType.UNKNOWN, description="Type of source")
    source_identity: Optional[str] = Field(default=None, description="Domain, tool name, model, or other identifier")
    source_query: Optional[str] = Field(default=None, description="Original user query")
    source_context: Optional[str] = Field(default=None, description="Conversation context")
    created_by: MemoryCreatedBy = Field(default=MemoryCreatedBy.CURATOR_LLM)

    # Verification & Trust
    verification_status: VerificationStatus = Field(default=VerificationStatus.UNVERIFIED, description="Verification state")
    corroboration_count: int = Field(default=0, ge=0, description="Number of corroborations")
    last_verified_at: Optional[datetime] = Field(default=None, description="When last verified")

    # Temporal metadata
    created_at: Optional[datetime] = None
    last_accessed_at: Optional[datetime] = None
    access_count: int = Field(default=0, ge=0)

    # Status
    status: MemoryStatus = Field(default=MemoryStatus.ACTIVE)
    superseded_by: Optional[int] = Field(default=None, description="ID of memory that replaced this one")

    class Config:
        use_enum_values = True


class MemoryProposal(BaseModel):
    """
    What MemoryCuratorLLM proposes to store.

    This is the output format from the curator LLM, before being
    validated and stored by the orchestrator.
    """
    memory_text: str = Field(description="What to remember")
    memory_type: MemoryType = Field(description="Type of memory")
    confidence: float = Field(ge=0.0, le=1.0, description="How confident the curator is")
    importance: float = Field(ge=0.0, le=1.0, description="How important this is for future")
    reasoning: str = Field(description="Why this should be remembered")

    # Source Trust (optional, defaults applied if not provided)
    source_type: Optional[MemorySourceType] = Field(default=None, description="Type of source for this fact")
    source_identity: Optional[str] = Field(default=None, description="Specific source identifier")

    class Config:
        use_enum_values = True


class MemoryContext(BaseModel):
    """
    Memory context injected into PersonaLLM.

    This is what gets passed to the LLM along with the user's query
    to provide relevant context from past interactions.
    """
    memories: List[Memory] = Field(default_factory=list, description="Retrieved memories")
    retrieval_query: str = Field(description="Query used for retrieval")
    total_retrieved: int = Field(ge=0, description="Total number of memories retrieved")


class RelationshipType(str, Enum):
    """Types of relationships between memories."""
    SUPERSEDES = "supersedes"      # New memory replaces old one
    CONTRADICTS = "contradicts"    # Memories conflict
    SUPPORTS = "supports"          # Memories reinforce each other
    RELATED = "related"            # General relationship


class MemoryRelationship(BaseModel):
    """
    Relationship between two memories.

    Used for tracking which memories supersede, contradict, or support
    each other.
    """
    id: Optional[int] = None
    memory_id: int = Field(description="Primary memory ID")
    related_memory_id: int = Field(description="Related memory ID")
    relationship_type: RelationshipType
    created_at: Optional[datetime] = None

    class Config:
        use_enum_values = True


class AuditOperation(str, Enum):
    """Types of operations that get audited."""
    CREATE = "create"
    RETRIEVE = "retrieve"
    UPDATE = "update"
    ARCHIVE = "archive"
    DECAY = "decay"


class MemoryAuditLog(BaseModel):
    """
    Audit log entry for memory operations.

    Tracks all operations performed on memories for debugging and compliance.
    """
    id: Optional[int] = None
    memory_id: Optional[int] = Field(default=None, description="Memory affected by operation")
    operation: AuditOperation
    details: Optional[Dict[str, Any]] = Field(default=None, description="Operation-specific details")
    performed_at: Optional[datetime] = None

    class Config:
        use_enum_values = True


class DecayUpdate(BaseModel):
    """
    Batch decay score update.

    Used when updating multiple memories' decay scores in a single operation.
    """
    memory_id: int
    old_decay_score: float
    new_decay_score: float
    reason: str = Field(description="Why decay was updated (time, access, etc.)")
