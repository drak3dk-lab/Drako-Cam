CREATE TABLE IF NOT EXISTS personas (
  codigo TEXT PRIMARY KEY,
  nombre TEXT NOT NULL,
  creado_en INTEGER NOT NULL,
  revocado_en INTEGER,
  huella TEXT,
  equipo TEXT
);

CREATE TABLE IF NOT EXISTS sesiones (
  id TEXT PRIMARY KEY,
  codigo TEXT NOT NULL,
  nombre TEXT NOT NULL,
  equipo TEXT NOT NULL,
  huella TEXT NOT NULL,
  ip TEXT NOT NULL DEFAULT '',
  pais TEXT NOT NULL DEFAULT '',
  ciudad TEXT NOT NULL DEFAULT '',
  inicio INTEGER NOT NULL,
  fin INTEGER,
  ultimo_latido INTEGER NOT NULL,
  duracion_segundos INTEGER,
  motivo_cierre TEXT
);

CREATE INDEX IF NOT EXISTS idx_sesiones_codigo ON sesiones (codigo, inicio);
CREATE INDEX IF NOT EXISTS idx_sesiones_abiertas ON sesiones (codigo, fin);

CREATE TABLE IF NOT EXISTS intentos (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  codigo TEXT NOT NULL DEFAULT '',
  motivo TEXT NOT NULL,
  equipo TEXT NOT NULL DEFAULT '',
  huella TEXT NOT NULL DEFAULT '',
  ip TEXT NOT NULL DEFAULT '',
  pais TEXT NOT NULL DEFAULT '',
  ciudad TEXT NOT NULL DEFAULT '',
  momento INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_intentos_ip ON intentos (ip, momento);
