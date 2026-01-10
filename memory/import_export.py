"""
Memory Import/Export System

Provides functionality to backup and restore memories to/from JSON files.
Handles both vector embeddings (ChromaDB) and metadata (MySQL).
"""

import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from pathlib import Path

from .schemas import Memory, MemoryType, MemoryStatus, MemoryCreatedBy

logger = logging.getLogger(__name__)


class MemoryExporter:
    """
    Export memories to JSON format.

    Includes metadata, relationships, and vector embeddings.
    """

    def __init__(self, vector_store, metadata_store):
        """
        Initialize exporter.

        Args:
            vector_store: VectorStore instance
            metadata_store: MetadataStore instance
        """
        self.vector_store = vector_store
        self.metadata_store = metadata_store

    def export_all(
        self,
        output_path: str,
        include_archived: bool = False,
        include_relationships: bool = True,
        include_audit_log: bool = False
    ) -> Dict[str, Any]:
        """
        Export all memories to JSON file.

        Args:
            output_path: Path to output JSON file
            include_archived: Include archived/superseded memories
            include_relationships: Include memory relationships
            include_audit_log: Include audit log (can be large)

        Returns:
            Dict with export statistics
        """
        try:
            logger.info(f"Starting memory export to {output_path}")

            # Get memories from MySQL
            if include_archived:
                memories = self.metadata_store.filter_memories(limit=None)
            else:
                memories = self.metadata_store.filter_memories(
                    status=MemoryStatus.ACTIVE,
                    limit=None
                )

            logger.info(f"Found {len(memories)} memories to export")

            # Convert to dict format
            memories_data = []
            for mem in memories:
                mem_dict = self._memory_to_dict(mem)

                # Get vector embedding from ChromaDB
                vector_data = self.vector_store.get_memory(mem.embedding_id)
                if vector_data:
                    mem_dict['vector_metadata'] = vector_data.get('metadata', {})
                    mem_dict['vector_document'] = vector_data.get('document', '')

                memories_data.append(mem_dict)

            # Build export data
            export_data = {
                'metadata': {
                    'export_date': datetime.now().isoformat(),
                    'total_memories': len(memories_data),
                    'include_archived': include_archived,
                    'include_relationships': include_relationships,
                    'include_audit_log': include_audit_log,
                    'version': '1.0'
                },
                'memories': memories_data
            }

            # Add relationships if requested
            if include_relationships:
                relationships = self.metadata_store.get_all_relationships()
                export_data['relationships'] = [
                    {
                        'id': r.id,
                        'memory_id': r.memory_id,
                        'related_memory_id': r.related_memory_id,
                        'relationship_type': r.relationship_type.value if hasattr(r.relationship_type, 'value') else str(r.relationship_type),
                        'created_at': r.created_at.isoformat() if r.created_at else None
                    }
                    for r in relationships
                ]
                logger.info(f"Exported {len(relationships)} relationships")

            # Add audit log if requested (can be large)
            if include_audit_log:
                audit_logs = self.metadata_store.get_all_audit_logs()
                export_data['audit_logs'] = [
                    {
                        'id': log.id,
                        'memory_id': log.memory_id,
                        'operation': log.operation.value if hasattr(log.operation, 'value') else str(log.operation),
                        'details': log.details,
                        'performed_at': log.performed_at.isoformat() if log.performed_at else None
                    }
                    for log in audit_logs
                ]
                logger.info(f"Exported {len(audit_logs)} audit log entries")

            # Write to file
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)

            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            file_size = output_file.stat().st_size
            logger.info(f"Export complete: {file_size} bytes written to {output_path}")

            return {
                'success': True,
                'memories_exported': len(memories_data),
                'relationships_exported': len(export_data.get('relationships', [])),
                'audit_logs_exported': len(export_data.get('audit_logs', [])),
                'file_path': str(output_file),
                'file_size_bytes': file_size
            }

        except Exception as e:
            logger.error(f"Error exporting memories: {e}")
            raise

    def _memory_to_dict(self, memory: Memory) -> Dict[str, Any]:
        """Convert Memory object to dictionary."""
        return {
            'id': memory.id,
            'memory_text': memory.memory_text,
            'memory_type': str(memory.memory_type),
            'embedding_id': memory.embedding_id,
            'confidence': memory.confidence,
            'importance': memory.importance,
            'decay_score': memory.decay_score,
            'source_query': memory.source_query,
            'source_context': memory.source_context,
            'created_by': str(memory.created_by),
            'created_at': memory.created_at.isoformat() if memory.created_at else None,
            'last_accessed_at': memory.last_accessed_at.isoformat() if memory.last_accessed_at else None,
            'access_count': memory.access_count,
            'status': str(memory.status),
            'superseded_by': memory.superseded_by
        }


class MemoryImporter:
    """
    Import memories from JSON format.

    Restores both metadata and vector embeddings.
    """

    def __init__(self, vector_store, metadata_store):
        """
        Initialize importer.

        Args:
            vector_store: VectorStore instance
            metadata_store: MetadataStore instance
        """
        self.vector_store = vector_store
        self.metadata_store = metadata_store

    def import_all(
        self,
        input_path: str,
        skip_existing: bool = True,
        restore_relationships: bool = True
    ) -> Dict[str, Any]:
        """
        Import memories from JSON file.

        Args:
            input_path: Path to input JSON file
            skip_existing: Skip memories that already exist (by embedding_id)
            restore_relationships: Restore memory relationships

        Returns:
            Dict with import statistics
        """
        try:
            logger.info(f"Starting memory import from {input_path}")

            # Read JSON file
            input_file = Path(input_path)
            if not input_file.exists():
                raise FileNotFoundError(f"Import file not found: {input_path}")

            with open(input_file, 'r', encoding='utf-8') as f:
                import_data = json.load(f)

            logger.info(f"Loaded import file (version {import_data['metadata'].get('version', 'unknown')})")

            memories_data = import_data.get('memories', [])
            relationships_data = import_data.get('relationships', [])

            # Track statistics
            stats = {
                'total_in_file': len(memories_data),
                'imported': 0,
                'skipped': 0,
                'errors': [],
                'relationships_imported': 0
            }

            # Map old IDs to new IDs for relationship restoration
            id_mapping = {}

            # Import memories
            for mem_data in memories_data:
                try:
                    old_id = mem_data['id']
                    embedding_id = mem_data['embedding_id']

                    # Check if already exists
                    if skip_existing:
                        existing = self.vector_store.get_memory(embedding_id)
                        if existing:
                            logger.debug(f"Skipping existing memory {embedding_id}")
                            stats['skipped'] += 1
                            # Still map ID in case relationships need it
                            existing_meta = self.metadata_store.get_memory_by_embedding_id(embedding_id)
                            if existing_meta:
                                id_mapping[old_id] = existing_meta.id
                            continue

                    # Import to MySQL
                    new_id = self._import_memory_metadata(mem_data)
                    id_mapping[old_id] = new_id

                    # Import to ChromaDB
                    self.vector_store.add_memory(
                        memory_id=embedding_id,
                        text=mem_data['vector_document'],
                        metadata=mem_data.get('vector_metadata', {})
                    )

                    stats['imported'] += 1
                    logger.debug(f"Imported memory {new_id} (was {old_id})")

                except Exception as e:
                    logger.error(f"Error importing memory {mem_data.get('id')}: {e}")
                    stats['errors'].append(str(e))

            # Import relationships if requested
            if restore_relationships and relationships_data:
                logger.info(f"Restoring {len(relationships_data)} relationships")
                for rel_data in relationships_data:
                    try:
                        old_mem_id = rel_data['memory_id']
                        old_rel_id = rel_data['related_memory_id']

                        # Map old IDs to new IDs
                        new_mem_id = id_mapping.get(old_mem_id)
                        new_rel_id = id_mapping.get(old_rel_id)

                        if new_mem_id and new_rel_id:
                            from .schemas import RelationshipType
                            self.metadata_store.create_relationship(
                                memory_id=new_mem_id,
                                related_memory_id=new_rel_id,
                                relationship_type=RelationshipType(rel_data['relationship_type'])
                            )
                            stats['relationships_imported'] += 1
                        else:
                            logger.warning(f"Skipping relationship - memories not found")

                    except Exception as e:
                        logger.error(f"Error restoring relationship: {e}")
                        stats['errors'].append(str(e))

            logger.info(
                f"Import complete: {stats['imported']} imported, "
                f"{stats['skipped']} skipped, {len(stats['errors'])} errors"
            )

            stats['success'] = True
            return stats

        except Exception as e:
            logger.error(f"Error importing memories: {e}")
            raise

    def _import_memory_metadata(self, mem_data: Dict[str, Any]) -> int:
        """
        Import memory metadata to MySQL.

        Returns:
            New memory ID
        """
        # Convert dict back to Memory object
        memory = Memory(
            memory_text=mem_data['memory_text'],
            memory_type=MemoryType(mem_data['memory_type']),
            embedding_id=mem_data['embedding_id'],
            confidence=mem_data['confidence'],
            importance=mem_data['importance'],
            decay_score=mem_data['decay_score'],
            source_query=mem_data.get('source_query'),
            source_context=mem_data.get('source_context'),
            created_by=MemoryCreatedBy(mem_data['created_by']),
            status=MemoryStatus(mem_data['status']),
            access_count=mem_data.get('access_count', 0),
            superseded_by=mem_data.get('superseded_by')
        )

        # Insert and return new ID
        new_id = self.metadata_store.insert_memory(memory)
        return new_id
