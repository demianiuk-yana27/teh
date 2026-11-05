CREATE TABLE IF NOT EXISTS product_catalog (product_id TEXT PRIMARY KEY, sku TEXT, title TEXT NOT NULL, category TEXT, brand TEXT, description TEXT, image_url TEXT, product_url TEXT, updated_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS idx_product_catalog_sku ON product_catalog(sku);
CREATE TABLE IF NOT EXISTS product_knowledge (product_id TEXT PRIMARY KEY, faq_json TEXT NOT NULL DEFAULT '[]', instructions TEXT NOT NULL DEFAULT '', related_json TEXT NOT NULL DEFAULT '[]', updated_at TEXT NOT NULL);
