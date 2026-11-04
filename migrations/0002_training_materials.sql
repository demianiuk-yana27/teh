CREATE TABLE IF NOT EXISTS training_materials (
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 title TEXT NOT NULL,
 summary TEXT NOT NULL DEFAULT '',
 blocks TEXT NOT NULL DEFAULT '[]',
 status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft','published')),
 created_at TEXT NOT NULL,
 updated_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_training_materials_status ON training_materials(status,updated_at);
