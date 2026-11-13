ALTER TABLE personas ADD COLUMN oficina TEXT NOT NULL DEFAULT '';
ALTER TABLE sesiones ADD COLUMN oficina TEXT NOT NULL DEFAULT '';

CREATE TABLE IF NOT EXISTS solicitudes (
  id TEXT PRIMARY KEY,
  nombre TEXT NOT NULL,
  oficina TEXT NOT NULL,
  equipo TEXT NOT NULL,
  huella TEXT NOT NULL,
  ip TEXT NOT NULL DEFAULT '',
  pais TEXT NOT NULL DEFAULT '',
  ciudad TEXT NOT NULL DEFAULT '',
  creada_en INTEGER NOT NULL,
  estado TEXT NOT NULL DEFAULT 'pendiente',
  codigo TEXT,
  cerrada_en INTEGER
);

CREATE INDEX IF NOT EXISTS idx_solicitudes_ip ON solicitudes (ip, creada_en);
CREATE INDEX IF NOT EXISTS idx_solicitudes_huella ON solicitudes (huella, estado);
