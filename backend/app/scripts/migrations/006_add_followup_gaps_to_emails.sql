-- Migration 006: add followup_gaps to emails table
-- Stores the list of questions the RAG pipeline could not answer, for dashboard display.
-- Rollback: ALTER TABLE emails DROP COLUMN IF EXISTS followup_gaps;

ALTER TABLE emails ADD COLUMN IF NOT EXISTS followup_gaps JSON DEFAULT NULL;
