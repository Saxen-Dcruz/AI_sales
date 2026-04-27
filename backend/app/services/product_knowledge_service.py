import logging
from uuid import UUID

from langchain_core.documents import Document
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_postgres import PGVector
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.product import Product
from app.models.product_knowledge import ProductKnowledge

logger = logging.getLogger("rdl_app_logger")

VALID_CATEGORIES = {"warranty", "compatibility", "pricing", "technical", "general"}


def _flush_rag_cache() -> None:
    """Flush the RAG retrieval cache (Redis DB 1) so new knowledge is picked up immediately."""
    try:
        import redis
        r = redis.Redis(host=settings.REDIS_HOST, port=settings.REDIS_PORT, db=1)
        r.flushdb()
        logger.info("[KNOWLEDGE] RAG retrieval cache flushed after knowledge update")
    except Exception as e:
        logger.warning(f"[KNOWLEDGE] Failed to flush RAG cache: {e}")


def _get_vectorstore() -> PGVector:
    conn = settings.DATABASE_URL.replace("postgresql+psycopg_async://", "postgresql+psycopg://").replace("postgresql://", "postgresql+psycopg://")
    return PGVector(
        embeddings=GoogleGenerativeAIEmbeddings(
            model=settings.AGENT.rag.embedding_model,
            google_api_key=settings.GOOGLE_API_KEY or None,
        ),
        collection_name="product_embeddings",
        connection=conn,
        use_jsonb=True,
    )


def add_entry(
    db: Session,
    product_id: UUID,
    category: str,
    content: str,
    added_by: str | None = None,
) -> ProductKnowledge:
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise ValueError("Product not found")

    entry = ProductKnowledge(
        product_id=product_id,
        category=category,
        content=content,
        added_by=added_by,
    )
    db.add(entry)
    db.flush()

    doc_id = f"{product_id}_knowledge_{entry.id}"
    doc = Document(
        page_content=(
            f"Product Name: {product.name}\n"
            f"Section: {category.title()}\n\n"
            f"{content}"
        ),
        metadata={
            "product_id": str(product_id),
            "product_name": product.name,
            "chunk_type": f"knowledge_{category}",
        },
    )
    try:
        _get_vectorstore().add_documents([doc], ids=[doc_id])
        entry.vector_doc_id = doc_id
        logger.info(f"[KNOWLEDGE] Embedded entry {doc_id} for product {product.name}")
    except Exception as e:
        logger.error(f"[KNOWLEDGE] Failed to embed entry for {product.name}: {e}", exc_info=True)

    db.commit()
    _flush_rag_cache()
    db.refresh(entry)
    return entry


def update_entry(
    db: Session,
    entry_id: UUID,
    category: str | None,
    content: str | None,
) -> ProductKnowledge:
    entry = db.query(ProductKnowledge).filter(ProductKnowledge.id == entry_id).first()
    if not entry:
        raise ValueError("Entry not found")

    product = db.query(Product).filter(Product.id == entry.product_id).first()

    if category:
        entry.category = category
    if content:
        entry.content = content

    # Re-embed with updated content
    if category or content:
        doc_id = entry.vector_doc_id or f"{entry.product_id}_knowledge_{entry.id}"
        doc = Document(
            page_content=(
                f"Product Name: {product.name}\n"
                f"Section: {entry.category.title()}\n\n"
                f"{entry.content}"
            ),
            metadata={
                "product_id": str(entry.product_id),
                "product_name": product.name,
                "chunk_type": f"knowledge_{entry.category}",
            },
        )
        try:
            vs = _get_vectorstore()
            if entry.vector_doc_id:
                vs.delete(ids=[entry.vector_doc_id])
            vs.add_documents([doc], ids=[doc_id])
            entry.vector_doc_id = doc_id
            logger.info(f"[KNOWLEDGE] Re-embedded entry {doc_id}")
        except Exception as e:
            logger.error(f"[KNOWLEDGE] Failed to re-embed entry {entry.id}: {e}", exc_info=True)

    db.commit()
    _flush_rag_cache()
    db.refresh(entry)
    return entry


def delete_entry(db: Session, entry_id: UUID) -> None:
    entry = db.query(ProductKnowledge).filter(ProductKnowledge.id == entry_id).first()
    if not entry:
        raise ValueError("Entry not found")

    if entry.vector_doc_id:
        try:
            _get_vectorstore().delete(ids=[entry.vector_doc_id])
            logger.info(f"[KNOWLEDGE] Deleted vector doc {entry.vector_doc_id}")
        except Exception as e:
            logger.warning(f"[KNOWLEDGE] Failed to delete vector doc {entry.vector_doc_id}: {e}")

    db.delete(entry)
    db.commit()
    _flush_rag_cache()


def update_coverage_score(db: Session, product_id_str: str) -> None:
    """Recompute and persist the coverage score for a product based on gap resolution rate."""
    from sqlalchemy import text
    from app.models.product import Product
    from uuid import UUID
    try:
        rows = db.execute(text("""
            SELECT
                COUNT(*) AS total,
                SUM(CASE WHEN (gap->>'resolved')::boolean THEN 1 ELSE 0 END) AS resolved
            FROM (
                SELECT jsonb_array_elements(followup_gaps::jsonb) AS gap
                FROM emails WHERE followup_gaps IS NOT NULL
                  AND followup_gaps::jsonb @> ('[{"product_id":"' || :pid || '"}]')::jsonb
                UNION ALL
                SELECT jsonb_array_elements(followup_gaps::jsonb) AS gap
                FROM calls WHERE followup_gaps IS NOT NULL
                  AND followup_gaps::jsonb @> ('[{"product_id":"' || :pid || '"}]')::jsonb
            ) sub
        """), {"pid": product_id_str}).fetchone()
        if rows and rows.total:
            score = round(rows.resolved / rows.total * 100, 1)
            db.execute(text("UPDATE products SET coverage_score = :score WHERE id = :pid::uuid"),
                       {"score": score, "pid": product_id_str})
            db.commit()
    except Exception as e:
        logger.warning(f"[KNOWLEDGE] Coverage score update failed: {e}")


def list_entries(db: Session, product_id: UUID) -> list[ProductKnowledge]:
    return (
        db.query(ProductKnowledge)
        .filter(ProductKnowledge.product_id == product_id)
        .order_by(ProductKnowledge.created_at.desc())
        .all()
    )
