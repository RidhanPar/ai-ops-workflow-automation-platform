import hashlib
import math
import re

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models import KnowledgeDocument

EMBEDDING_DIMENSIONS = 64


def local_embedding(value: str) -> list[float]:
    """Create a deterministic local embedding for zero-cost demo retrieval."""
    vector = [0.0] * EMBEDDING_DIMENSIONS
    for token in re.findall(r"[a-z0-9]+", value.lower()):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:2], "big") % EMBEDDING_DIMENSIONS
        vector[index] += 1 if digest[2] % 2 == 0 else -1
    norm = math.sqrt(sum(item * item for item in vector)) or 1
    return [round(item / norm, 6) for item in vector]


def cosine_similarity(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right, strict=False))


def add_knowledge_document(db: Session, title: str, content: str, tags: list[str]) -> KnowledgeDocument:
    embedding = local_embedding(f"{title} {content} {' '.join(tags)}")
    document = KnowledgeDocument(title=title, content=content, tags=tags, embedding=embedding)
    db.add(document)
    db.flush()
    if db.bind and db.bind.dialect.name == "postgresql":
        db.execute(
            text("UPDATE knowledge_documents SET embedding_vector = :embedding WHERE id = :id"),
            {"embedding": str(embedding), "id": document.id},
        )
    return document


def search_knowledge_base(db: Session, query: str, limit: int = 3) -> list[dict]:
    """Search PostgreSQL pgvector when available, with a portable local-vector fallback."""
    embedding = local_embedding(query)
    if db.bind and db.bind.dialect.name == "postgresql":
        rows = db.execute(
            text(
                "SELECT id, title, content, tags, 1 - (embedding_vector <=> :embedding) AS score "
                "FROM knowledge_documents ORDER BY embedding_vector <=> :embedding LIMIT :limit"
            ),
            {"embedding": str(embedding), "limit": limit},
        ).mappings()
        return [dict(row) for row in rows]

    documents = db.query(KnowledgeDocument).all()
    ranked = sorted(
        documents,
        key=lambda document: cosine_similarity(embedding, document.embedding or []),
        reverse=True,
    )
    return [
        {
            "id": document.id,
            "title": document.title,
            "content": document.content,
            "tags": document.tags,
            "score": round(cosine_similarity(embedding, document.embedding or []), 4),
        }
        for document in ranked[:limit]
    ]
