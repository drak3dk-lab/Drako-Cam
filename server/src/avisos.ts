import type { Env } from "./tipos";

export function formatearHora(unix: number): string {
  try {
    const texto = new Intl.DateTimeFormat("es-ES", {
      timeZone: "Europe/Bucharest",
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hourCycle: "h23",
    }).format(new Date(unix * 1000));
    return `${texto} (Europe/Bucharest)`;
  } catch {
    return `${new Date(unix * 1000).toISOString()} (Europe/Bucharest)`;
  }
}

export function textoDuracion(segundos: number): string {
  const total = Math.max(0, Math.floor(segundos));
  const horas = Math.floor(total / 3600);
  const minutos = Math.floor((total % 3600) / 60);
  const resto = total % 60;
  if (horas > 0) return `${horas} h ${minutos} min`;
  if (minutos > 0) return `${minutos} min ${resto} s`;
  return `${resto} s`;
}

export function textoLugar(ciudad: string, pais: string): string {
  if (ciudad && pais) return `${ciudad}, ${pais}`;
  return ciudad || pais || "ubicación no disponible";
}

export function textoInicio(datos: {
  persona: string;
  equipo: string;
  ciudad: string;
  pais: string;
  ip: string;
  ahora: number;
}): string {
  return [
    "Drako Cam — sesión iniciada",
    `Persona: ${datos.persona}`,
    `Equipo: ${datos.equipo}`,
    `Lugar: ${textoLugar(datos.ciudad, datos.pais)}`,
    `IP: ${datos.ip || "no disponible"}`,
    `Hora: ${formatearHora(datos.ahora)}`,
  ].join("\n");
}

export function textoCierre(datos: {
  persona: string;
  equipo: string;
  duracion: number;
  ahora: number;
}): string {
  return [
    "Drako Cam — sesión cerrada",
    `Persona: ${datos.persona}`,
    `Equipo: ${datos.equipo}`,
    `Duración: ${textoDuracion(datos.duracion)}`,
    `Hora de cierre: ${formatearHora(datos.ahora)}`,
  ].join("\n");
}

export function textoCorte(datos: {
  persona: string;
  equipo: string;
  duracion: number;
  ahora: number;
}): string {
  return [
    "Drako Cam — sesión cortada",
    "Motivo: código revocado",
    `Persona: ${datos.persona}`,
    `Equipo: ${datos.equipo}`,
    `Duración: ${textoDuracion(datos.duracion)}`,
    `Hora: ${formatearHora(datos.ahora)}`,
  ].join("\n");
}

export function textoRechazo(datos: {
  motivo: string;
  codigo: string;
  equipo: string;
  ciudad: string;
  pais: string;
  ip: string;
  ahora: number;
}): string {
  const motivos: Record<string, string> = {
    desconocido: "código desconocido",
    revocado: "código revocado",
    otro_equipo: "código ligado a otro equipo",
    mal_formato: "código o huella no válidos",
  };
  return [
    "Drako Cam — código rechazado",
    `Motivo: ${motivos[datos.motivo] || datos.motivo}`,
    `Código: ${datos.codigo || "no indicado"}`,
    `Equipo: ${datos.equipo || "desconocido"}`,
    `Lugar: ${textoLugar(datos.ciudad, datos.pais)}`,
    `IP: ${datos.ip || "no disponible"}`,
    `Hora: ${formatearHora(datos.ahora)}`,
  ].join("\n");
}

export function tokenPareceValido(token: string): boolean {
  return token.length >= 20 && token.length <= 200 && /^[0-9]+:[A-Za-z0-9_-]+$/.test(token);
}

export async function enviarTelegram(env: Env, texto: string): Promise<void> {
  const token = (env.TELEGRAM_BOT_TOKEN || "").trim();
  const chat = (env.TELEGRAM_ADMIN_CHAT_ID || "").trim();
  if (!token || !chat || !texto || !tokenPareceValido(token)) return;
  try {
    await fetch(`https://api.telegram.org/bot${token}/sendMessage`, {
      method: "POST",
      headers: { "content-type": "application/json; charset=utf-8" },
      body: JSON.stringify({ chat_id: chat, text: texto.slice(0, 4000) }),
    });
  } catch {
    // El acceso no depende de que Telegram conteste.
  }
}

export function dejarAviso(ctx: ExecutionContext, env: Env, texto: string): void {
  ctx.waitUntil(enviarTelegram(env, texto));
}
