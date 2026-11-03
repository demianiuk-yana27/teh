CREATE TABLE IF NOT EXISTS manager_tasks (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  title TEXT NOT NULL,
  description TEXT NOT NULL DEFAULT '',
  author TEXT NOT NULL,
  due_at TEXT,
  created_at TEXT NOT NULL,
  completed_at TEXT,
  completed_by TEXT
);
CREATE INDEX IF NOT EXISTS idx_manager_tasks_completed_due ON manager_tasks(completed_at,due_at);
