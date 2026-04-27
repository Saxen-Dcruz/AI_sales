-- Migration 007: product knowledge entries
-- Sales team can add/update product data (warranty, compatibility, pricing, etc.)
-- that gets embedded into pgvector so RAG can answer customer questions.
-- Rollback: DROP TABLE IF EXISTS product_knowledge_entries;

CREATE TABLE IF NOT EXISTS product_knowledge_entries (
    id          UUID PRIMARY KEY,
    product_id  UUID NOT NULL REFERENCES products(id) ON DELETE CASCADE,
    category    VARCHAR NOT NULL,
    content     TEXT NOT NULL,
    vector_doc_id VARCHAR,
    added_by    VARCHAR,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_product_knowledge_product_id ON product_knowledge_entries(product_id);
