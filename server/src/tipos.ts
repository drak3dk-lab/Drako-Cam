export interface Env {
  DB: D1Database;
  SIGNING_SEED?: string;
  TELEGRAM_BOT_TOKEN?: string;
  TELEGRAM_ADMIN_CHAT_ID?: string;
  TELEGRAM_WEBHOOK_SECRET?: string;
  GRACIA_HORAS?: string;
  LATIDO_SEGUNDOS?: string;
  SESION_ACTIVA_SECS?: string;
  LIMITE_INTENTOS?: string;
  LIMITE_SOLICITUDES?: string;
  /** Solo en pruebas. En producción no existe y las cabeceras de prueba se ignoran. */
  MODO_PRUEBA?: string;
  TEST_MIGRATIONS?: unknown;
}

export interface Carga {
  v: 1;
  accion: string;
  ok: boolean;
  motivo: string;
  mensaje: string;
  persona: string;
  codigo_hash: string;
  huella: string;
  sesion: string;
  estado: string;
  emitido: number;
  expira: number;
  latido_segundos: number;
  gracia_horas: number;
}

export interface Lugar {
  ip: string;
  pais: string;
  ciudad: string;
  ahora: number;
}

export interface Persona {
  codigo: string;
  nombre: string;
  creado_en: number;
  revocado_en: number | null;
  huella: string | null;
  equipo: string | null;
  oficina?: string | null;
}

export interface Sesion {
  id: string;
  codigo: string;
  nombre: string;
  equipo: string;
  huella: string;
  ip: string;
  pais: string;
  ciudad: string;
  inicio: number;
  fin: number | null;
  ultimo_latido: number;
  duracion_segundos: number | null;
  motivo_cierre: string | null;
  oficina?: string | null;
}

export interface Solicitud {
  id: string;
  nombre: string;
  oficina: string;
  equipo: string;
  huella: string;
  ip: string;
  pais: string;
  ciudad: string;
  creada_en: number;
  estado: string;
  codigo: string | null;
  cerrada_en: number | null;
}

export interface Firmante {
  semilla: Uint8Array;
  publica: Uint8Array;
}
