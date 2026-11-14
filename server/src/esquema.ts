/** Igual que `migrations/0001_inicio.sql`. Las pruebas lo aplican en D1 local. */
export const ESQUEMA = `
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
`;

/** Igual que `migrations/0002_solicitudes.sql`. */
export const ESQUEMA_SOLICITUDES = `
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
`;

/** Igual que `migrations/0004_reasignar.sql`. */
export const ESQUEMA_REASIGNAR = `
ALTER TABLE solicitudes ADD COLUMN tipo TEXT NOT NULL DEFAULT 'acceso';
`;

/** Igual que `migrations/0003_bot_estado.sql`. */
export const ESQUEMA_BOT = `
CREATE TABLE IF NOT EXISTS bot_estado (
  chat_id TEXT PRIMARY KEY,
  paso TEXT NOT NULL,
  expira_en INTEGER NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_bot_estado_expira ON bot_estado (expira_en);
`;
