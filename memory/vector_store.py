"""
ChromaDB vector store wrapper for memory embeddings.

Handles all vector similarity search operations for memory retrieval.
"""

import chromadb
from chromadb.config import Settings
from typing import List, Dict, Any, Optional
import logging
from pathlib import Path
import uuid

logger = logging.getLogger(__name__)


class VectorStore:
    """
    Wrapper for ChromaDB vector store.

    Provides methods to add, search, and delete memory embeddings.
    Uses ChromaDB's persistent client for durability.
    """

    def __init__(self, persist_path: str):
        """
        Initialize ChromaDB client and collection.

        Args:
            persist_path: Path to ChromaDB persistence directory
        """
        self.persist_path = Path(persist_path)
        self.persist_path.mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB client with GPU support
        # Configure ONNX Runtime to use CUDA for embeddings
        chroma_settings = Settings(
            anonymized_telemetry=False,
            allow_reset=False,
            # Enable GPU for ONNX Runtime (embeddings)
            # This uses CUDA if onnxruntime-gpu is installed
        )

        self.client = chromadb.PersistentClient(
            path=str(self.persist_path),
            settings=chroma_settings
        )

        # Get or create collection for memories
        # Using cosine similarity for semantic search
        self.collection = self.client.get_or_create_collection(
            name="memories",
            metadata={"hnsw:space": "cosine"}  # Cosine similarity
        )

        logger.info(f"ChromaDB initialized at {self.persist_path}")
        logger.info(f"Collection 'memories' has {self.collection.count()} embeddings")

    def add_memory(
        self,
        memory_id: str,
        text: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Add a memory embedding to the vector store.

        Args:
            memory_id: Unique identifier for this memory (UUID)
            text: Memory text to embed
            metadata: Optional metadata (memory_type, confidence, user_id, etc.)

        Note: ChromaDB will automatically generate embeddings using its default
        embedding function (all-MiniLM-L6-v2 by default).

        IMPORTANT: For multi-user support, metadata should include 'user_id' as a string.
        """
        try:
            # Ensure metadata is serializable
            if metadata is None:
                metadata = {}

            # Convert any non-string values to strings for ChromaDB
            clean_metadata = {}
            for key, value in metadata.items():
                if isinstance(value, (int, float, str, bool)):
                    clean_metadata[key] = str(value) if not isinstance(value, str) else value

            self.collection.add(
                ids=[memory_id],
                documents=[text],
                metadatas=[clean_metadata]
            )

            logger.debug(f"Added embedding for memory {memory_id}")

        except Exception as e:
            logger.error(f"Error adding memory to vector store: {e}")
            raise

    def search(
        self,
        query: str,
        k: int = 10,
        where: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for similar memories using semantic similarity.

        Args:
            query: Query text to search for
            k: Number of results to return
            where: Optional metadata filters (e.g., {"memory_type": "identity", "user_id": "1"})

        Returns:
            List of dicts with:
            - id: Memory embedding ID
            - distance: Cosine distance (lower = more similar)
            - metadata: Memory metadata
            - document: Memory text

        IMPORTANT: For multi-user support, include {"user_id": str(user_id)} in where clause.
        """
        try:
            # ChromaDB's query method
            results = self.collection.query(
                query_texts=[query],
                n_results=k,
                where=where
            )

            # Format results
            formatted_results = []
            if results and results['ids'] and len(results['ids']) > 0:
                ids = results['ids'][0]
                distances = results['distances'][0]
                metadatas = results['metadatas'][0]
                documents = results['documents'][0]

                for i in range(len(ids)):
                    formatted_results.append({
                        'id': ids[i],
                        'distance': distances[i],
                        'metadata': metadatas[i] if metadatas else {},
                        'document': documents[i]
                    })

            logger.debug(f"Vector search returned {len(formatted_results)} results")
            return formatted_results

        except Exception as e:
            logger.error(f"Error searching vector store: {e}")
            raise

    def delete_memory(self, memory_id: str) -> None:
        """
        Remove a memory embedding from the vector store.

        Args:
            memory_id: Unique identifier of memory to delete
        """
        try:
            self.collection.delete(ids=[memory_id])
            logger.debug(f"Deleted embedding for memory {memory_id}")

        except Exception as e:
            logger.error(f"Error deleting memory from vector store: {e}")
            raise

    def update_metadata(
        self,
        memory_id: str,
        metadata: Dict[str, Any]
    ) -> None:
        """
        Update metadata for a memory without re-embedding.

        Args:
            memory_id: Memory embedding ID
            metadata: New metadata dict

        Note: This updates metadata only, not the embedding itself.
        If the memory text changes, you need to delete and re-add.
        """
        try:
            # Convert metadata values to strings
            clean_metadata = {}
            for key, value in metadata.items():
                if isinstance(value, (int, float, str, bool)):
                    clean_metadata[key] = str(value) if not isinstance(value, str) else value

            self.collection.update(
                ids=[memory_id],
                metadatas=[clean_metadata]
            )

            logger.debug(f"Updated metadata for memory {memory_id}")

        except Exception as e:
            logger.error(f"Error updating memory metadata: {e}")
            raise

    def get_memory(self, memory_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a specific memory by ID.

        Args:
            memory_id: Memory embedding ID

        Returns:
            Dict with id, metadata, document or None if not found
        """
        try:
            result = self.collection.get(
                ids=[memory_id],
                include=['metadatas', 'documents']
            )

            if result and result['ids'] and len(result['ids']) > 0:
                return {
                    'id': result['ids'][0],
                    'metadata': result['metadatas'][0] if result['metadatas'] else {},
                    'document': result['documents'][0] if result['documents'] else ''
                }
            return None

        except Exception as e:
            logger.error(f"Error retrieving memory from vector store: {e}")
            return None

    def count(self) -> int:
        """
        Get total number of embeddings in the collection.

        Returns:
            Count of memory embeddings
        """
        try:
            return self.collection.count()
        except Exception as e:
            logger.error(f"Error counting embeddings: {e}")
            return 0

    @staticmethod
    def generate_embedding_id() -> str:
        """
        Generate a unique ID for a new memory embedding.

        Returns:
            UUID string
        """
        return str(uuid.uuid4())
