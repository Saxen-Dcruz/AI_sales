-- Migration 001: Add source, token_tier, reranker_doc_count, user_id to rag_usage_logs
-- Safe to run multiple times (IF NOT EXISTS).
-- Rollback: see DROP statements at the bottom (commented out).

ALTER TABLE rag_usage_logs
    ADD COLUMN IF NOT EXISTS source              VARCHAR     NULL,
    ADD COLUMN IF NOT EXISTS token_tier          VARCHAR     NULL,
    ADD COLUMN IF NOT EXISTS reranker_doc_count  INTEGER     NULL,
    ADD COLUMN IF NOT EXISTS user_id             VARCHAR     NULL;

CREATE INDEX IF NOT EXISTS ix_rag_usage_logs_source  ON rag_usage_logs (source);
CREATE INDEX IF NOT EXISTS ix_rag_usage_logs_user_id ON rag_usage_logs (user_id);

-- ROLLBACK (run manually if needed):
-- ALTER TABLE rag_usage_logs
--     DROP COLUMN IF EXISTS source,
--     DROP COLUMN IF EXISTS token_tier,
--     DROP COLUMN IF EXISTS reranker_doc_count,
--     DROP COLUMN IF EXISTS user_id;
-- DROP INDEX IF EXISTS ix_rag_usage_logs_source;
-- DROP INDEX IF EXISTS ix_rag_usage_logs_user_id;
