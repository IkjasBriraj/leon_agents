"""
Memory Manager — Dual-Memory Layer for AgentCraft

Manages three memory types using PostgreSQL + pgvector:

  1. Episodic Memory — Past interactions, run outcomes, step-by-step history
  2. Semantic Memory  — Knowledge base facts, documents, RAG chunks
  3. Profile Memory   — Agent preferences, rules, behavioral constraints

Core operations:
  - retrieve_relevant()  — Vector similarity search for context injection
  - store_episodic()     — Save run step as a retrievable episodic trace
  - store_semantic()     — Ingest and chunk a document into semantic memory
  - get_profile()        — Load an agent's profile memories

Memory retrieval pipeline:
  1. Generate embedding for the query text (Ollama nomic-embed-text)
  2. Execute pgvector cosine similarity search
  3. Filter by agent_id, memory_type, is_active, expires_at
  4. Return top-k results ranked by similarity score
  5. Update access_count + last_accessed for retrieved memories
"""

import uuid
from datetime import UTC, datetime
from typing import Any

import structlog
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.llm_client import get_embedding
from app.models.memory import Memory

log = structlog.get_logger()

# Max tokens per chunk for semantic memory (roughly 400 words)
CHUNK_SIZE = 1500  # characters
CHUNK_OVERLAP = 200  # characters overlap between chunks


# Minimal dataclass-like structure without import
class MemorySearchResult:
    def __init__(self, memory: Memory, score: float) -> None:
        self.memory = memory
        self.score = score

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.memory.id),
            "content": self.memory.content,
            "memory_type": self.memory.memory_type,
            "score": self.score,
            "metadata": self.memory.metadata_,
            "tags": self.memory.tags,
            "importance": self.memory.importance,
        }


class MemoryManager:
    """
    Unified interface for reading/writing all three memory types.

    Usage::

        mgr = MemoryManager(db, org_id=org_id, agent_id=agent_id)
        results = await mgr.retrieve_relevant("What did we find last time?", k=5)
        await mgr.store_episodic(
            content="Tool call succeeded: web_search returned 10 results",
            metadata={"run_id": ..., "step_index": 3, "outcome": "success"}
        )
    """

    def __init__(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        agent_id: uuid.UUID | None = None,
    ) -> None:
        self.db = db
        self.org_id = org_id
        self.agent_id = agent_id

    async def retrieve_relevant(
        self,
        query: str,
        k: int = 5,
        memory_types: list[str] | None = None,
        min_score: float = 0.6,
        tags: list[str] | None = None,
    ) -> list[MemorySearchResult]:
        """
        Find the k most semantically similar memories to the query.

        Process:
          1. Embed the query text
          2. pgvector cosine similarity search (HNSW index)
          3. Filter by type, agent, score, tags, is_active, expires_at
          4. Update access tracking for retrieved memories

        Args:
            query:        The text to search for similar memories
            k:            Number of results to return
            memory_types: Filter to specific types (e.g., ['episodic', 'semantic'])
            min_score:    Minimum cosine similarity score (0.0 to 1.0)
            tags:         Filter to memories with all these tags

        Returns:
            List of MemorySearchResult, sorted by relevance (highest first)
        """
        if not query.strip():
            return []

        # Generate query embedding
        query_embedding = await get_embedding(query)
        if not any(query_embedding):  # All zeros = embedding failed
            log.warning("memory.retrieve_skipped", reason="embedding_failed")
            return []

        # Build WHERE clause filters
        filters = [
            "m.org_id = :org_id",
            "m.is_active = true",
            "(m.expires_at IS NULL OR m.expires_at > NOW())",
        ]
        params: dict[str, Any] = {
            "org_id": str(self.org_id),
            "embedding": query_embedding,
            "k": k,
            "min_score": min_score,
        }

        if self.agent_id:
            filters.append("m.agent_id = :agent_id")
            params["agent_id"] = str(self.agent_id)

        if memory_types:
            filters.append("m.memory_type = ANY(:memory_types)")
            params["memory_types"] = memory_types

        if tags:
            filters.append("m.tags @> :tags")
            params["tags"] = tags

        where_clause = " AND ".join(filters)

        # pgvector cosine similarity: 1 - (embedding <=> query) = similarity
        # The <=> operator returns cosine DISTANCE; we convert to similarity
        sql = text(f"""
            SELECT
                m.id,
                1 - (m.embedding <=> :embedding::vector) AS score
            FROM memories m
            WHERE {where_clause}
                AND m.embedding IS NOT NULL
                AND 1 - (m.embedding <=> :embedding::vector) >= :min_score
            ORDER BY score DESC
            LIMIT :k
        """)

        try:
            result = await self.db.execute(sql, params)
            rows = result.fetchall()
        except Exception as exc:
            log.error("memory.retrieve_error", error=str(exc))
            return []

        if not rows:
            return []

        # Fetch full Memory objects
        memory_ids = [row.id for row in rows]
        scores = {row.id: row.score for row in rows}

        memories_result = await self.db.execute(
            select(Memory).where(Memory.id.in_(memory_ids))
        )
        memories = {m.id: m for m in memories_result.scalars().all()}

        # Build results, maintaining score order
        search_results = []
        memory_ids_to_update = []

        for row in rows:
            mem = memories.get(row.id)
            if mem:
                search_results.append(MemorySearchResult(memory=mem, score=scores[row.id]))
                memory_ids_to_update.append(row.id)

        # Update access tracking (fire and forget — don't await to avoid slowing retrieval)
        if memory_ids_to_update:
            await self.db.execute(
                update(Memory)
                .where(Memory.id.in_(memory_ids_to_update))
                .values(
                    access_count=Memory.access_count + 1,
                    last_accessed=datetime.now(UTC),
                )
            )

        log.info(
            "memory.retrieved",
            query_preview=query[:50],
            results=len(search_results),
            top_score=search_results[0].score if search_results else 0,
        )
        return search_results

    async def store_episodic(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
        importance: float = 0.5,
        tags: list[str] | None = None,
    ) -> Memory:
        """
        Store a run step/interaction as an episodic memory.

        Automatically generates an embedding for semantic retrieval.
        """
        embedding = await get_embedding(content)
        memory = Memory(
            org_id=self.org_id,
            agent_id=self.agent_id,
            memory_type="episodic",
            content=content,
            embedding=embedding,
            metadata_=metadata or {},
            importance=importance,
            tags=tags or [],
        )
        self.db.add(memory)
        await self.db.flush()  # Get ID without full commit
        log.debug("memory.stored_episodic", memory_id=str(memory.id))
        return memory

    async def store_semantic(
        self,
        content: str,
        metadata: dict[str, Any] | None = None,
        tags: list[str] | None = None,
        importance: float = 0.7,
    ) -> list[Memory]:
        """
        Chunk a document and store all chunks as semantic memories.

        Uses overlapping chunks of ~1500 chars to balance retrieval quality.
        Returns all created Memory objects.
        """
        chunks = self._chunk_text(content, CHUNK_SIZE, CHUNK_OVERLAP)
        memories = []

        for i, chunk in enumerate(chunks):
            chunk_meta = {**(metadata or {}), "chunk_index": i, "total_chunks": len(chunks)}
            embedding = await get_embedding(chunk)
            memory = Memory(
                org_id=self.org_id,
                agent_id=self.agent_id,
                memory_type="semantic",
                content=chunk,
                embedding=embedding,
                metadata_=chunk_meta,
                importance=importance,
                tags=tags or [],
            )
            self.db.add(memory)
            memories.append(memory)

        await self.db.flush()
        log.info("memory.stored_semantic", chunks=len(memories))
        return memories

    async def get_profile(self) -> list[Memory]:
        """Load all active profile memories for this agent."""
        if not self.agent_id:
            return []

        result = await self.db.execute(
            select(Memory)
            .where(
                Memory.agent_id == self.agent_id,
                Memory.memory_type == "profile",
                Memory.is_active == True,  # noqa: E712
            )
            .order_by(Memory.importance.desc())
        )
        return list(result.scalars().all())

    async def store_profile(
        self,
        content: str,
        category: str = "preference",
        importance: float = 0.8,
    ) -> Memory:
        """Store or update an agent profile rule/preference."""
        embedding = await get_embedding(content)
        memory = Memory(
            org_id=self.org_id,
            agent_id=self.agent_id,
            memory_type="profile",
            content=content,
            embedding=embedding,
            metadata_={"category": category},
            importance=importance,
            tags=["profile", category],
        )
        self.db.add(memory)
        await self.db.flush()
        return memory

    @staticmethod
    def _chunk_text(text: str, chunk_size: int, overlap: int) -> list[str]:
        """
        Split text into overlapping chunks.

        Simple character-based chunking. In production, use a
        token-aware splitter (e.g., via tiktoken) for better boundaries.
        """
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            start += chunk_size - overlap

        return chunks
