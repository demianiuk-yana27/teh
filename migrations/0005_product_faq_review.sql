CREATE TABLE IF NOT EXISTS product_faq_review (
 id TEXT PRIMARY KEY,
 sku TEXT NOT NULL DEFAULT '',
 product_id TEXT,
 question TEXT NOT NULL,
 answer TEXT NOT NULL,
 original_question TEXT NOT NULL DEFAULT '',
 original_answer TEXT NOT NULL DEFAULT '',
 source_question_id TEXT NOT NULL DEFAULT '',
 source_answer_id TEXT NOT NULL DEFAULT '',
 source_date TEXT NOT NULL DEFAULT '',
 status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','approved','rejected')),
 created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
 reviewed_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_product_faq_review_status ON product_faq_review(status);
CREATE INDEX IF NOT EXISTS idx_product_faq_review_sku ON product_faq_review(sku);
