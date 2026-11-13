CREATE TABLE IF NOT EXISTS bot_estado (
  chat_id TEXT PRIMARY KEY,
  paso TEXT NOT NULL,
  expira_en INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_bot_estado_expira ON bot_estado (expira_en);
