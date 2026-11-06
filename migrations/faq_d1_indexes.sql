-- Apply once to the Cloudflare D1 database after checking existing indexes.
-- Speeds up FAQ classification, import and status filtering.
CREATE INDEX IF NOT EXISTS idx_product_catalog_sku ON product_catalog(sku);
CREATE INDEX IF NOT EXISTS idx_product_faq_review_status_id ON product_faq_review(status, id);
CREATE INDEX IF NOT EXISTS idx_product_faq_review_status_created ON product_faq_review(status, created_at, id);
