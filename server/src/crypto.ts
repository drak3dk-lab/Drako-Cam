import type { Carga, Firmante } from "./tipos";

const ALFABETO = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
const PREFIJO_PKCS8 = Uint8Array.from([
  0x30, 0x2e, 0x02, 0x01, 0x00, 0x30, 0x05, 0x06, 0x03, 0x2b, 0x65, 0x70, 0x04, 0x22, 0x04, 0x20,
]);

export function canonico(valor: unknown): string {
  return JSON.stringify(ordenar(valor));
}

function ordenar(valor: unknown): unknown {
  if (Array.isArray(valor)) return valor.map(ordenar);
  if (valor && typeof valor === "object") {
    const salida: Record<string, unknown> = {};
    for (const clave of Object.keys(valor as Record<string, unknown>).sort()) {
      const item = (valor as Record<string, unknown>)[clave];
      if (item !== undefined) salida[clave] = ordenar(item);
    }
    return salida;
  }
  return valor;
}

export function normalizarCodigo(bruto: unknown): string | null {
  if (typeof bruto !== "string") return null;
  const limpio = bruto.toUpperCase().replace(/[\s-]+/g, "");
  if (!/^DRAKO[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{16}$/.test(limpio)) return null;
  const cuerpo = limpio.slice(5);
  return `DRAKO-${cuerpo.slice(0, 4)}-${cuerpo.slice(4, 8)}-${cuerpo.slice(8, 12)}-${cuerpo.slice(12, 16)}`;
}

export function generarCodigo(): string {
  const bytes = new Uint8Array(16);
  crypto.getRandomValues(bytes);
  let cuerpo = "";
  for (let i = 0; i < bytes.length; i += 1) {
    cuerpo += ALFABETO[bytes[i] % ALFABETO.length];
  }
  return `DRAKO-${cuerpo.slice(0, 4)}-${cuerpo.slice(4, 8)}-${cuerpo.slice(8, 12)}-${cuerpo.slice(12, 16)}`;
}

export function normalizarHuella(bruto: unknown): string | null {
  if (typeof bruto !== "string") return null;
  const texto = bruto.trim().toLowerCase();
  return /^[0-9a-f]{64}$/.test(texto) ? texto : null;
}

export async function sha256Hex(texto: string): Promise<string> {
  const datos = new TextEncoder().encode(texto);
  const hash = await crypto.subtle.digest("SHA-256", datos);
  return [...new Uint8Array(hash)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export function entero(valor: string | undefined, defecto: number, minimo: number, maximo: number): number {
  const numero = Number(valor);
  if (!Number.isFinite(numero)) return defecto;
  return Math.min(maximo, Math.max(minimo, Math.floor(numero)));
}

export function limpiarTexto(valor: unknown, maximo: number): string {
  if (typeof valor !== "string") return "";
  return valor.replace(/[\u0000-\u001f]/g, " ").replace(/\s+/g, " ").trim().slice(0, maximo);
}

export function limpiarNombre(valor: unknown): string | null {
  const nombre = limpiarTexto(valor, 80);
  if (!nombre || nombre.startsWith("/")) return null;
  return nombre;
}

function concatenar(a: Uint8Array, b: Uint8Array): Uint8Array {
  const salida = new Uint8Array(a.length + b.length);
  salida.set(a, 0);
  salida.set(b, a.length);
  return salida;
}

export function base64ABytes(texto: string): Uint8Array {
  const binario = atob(texto.trim());
  const salida = new Uint8Array(binario.length);
  for (let i = 0; i < binario.length; i += 1) salida[i] = binario.charCodeAt(i);
  return salida;
}

export function bytesABase64(bytes: Uint8Array): string {
  let binario = "";
  for (const byte of bytes) binario += String.fromCharCode(byte);
  return btoa(binario);
}

function base64urlABytes(texto: string): Uint8Array {
  const relleno = texto.length % 4 === 0 ? "" : "=".repeat(4 - (texto.length % 4));
  return base64ABytes(texto.replace(/-/g, "+").replace(/_/g, "/") + relleno);
}

export async function prepararFirmante(semillaB64: string | undefined): Promise<Firmante> {
  if (!semillaB64 || !semillaB64.trim()) {
    throw new Error("semilla");
  }
  const semilla = base64ABytes(semillaB64.trim());
  if (semilla.length !== 32) throw new Error("semilla");
  const pkcs8 = concatenar(PREFIJO_PKCS8, semilla);
  const clave = await crypto.subtle.importKey("pkcs8", pkcs8, { name: "Ed25519" }, true, ["sign"]);
  const jwk = (await crypto.subtle.exportKey("jwk", clave)) as JsonWebKey;
  if (!jwk.x) throw new Error("semilla");
  return { semilla, publica: base64urlABytes(jwk.x) };
}

export async function firmarCarga(firmante: Firmante, carga: Carga): Promise<string> {
  const pkcs8 = concatenar(PREFIJO_PKCS8, firmante.semilla);
  const clave = await crypto.subtle.importKey("pkcs8", pkcs8, { name: "Ed25519" }, false, ["sign"]);
  const datos = new TextEncoder().encode(canonico(carga));
  const firma = new Uint8Array(await crypto.subtle.sign({ name: "Ed25519" }, clave, datos));
  return bytesABase64(firma);
}

export function iguales(a: string, b: string): boolean {
  const encoder = new TextEncoder();
  const aa = encoder.encode(a);
  const bb = encoder.encode(b);
  const n = Math.max(aa.length, bb.length);
  let diff = aa.length ^ bb.length;
  for (let i = 0; i < n; i += 1) diff |= (aa[i] || 0) ^ (bb[i] || 0);
  return diff === 0;
}
